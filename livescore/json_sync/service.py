from __future__ import annotations

import asyncio
import time

import structlog

from livescore.json_sync.converter import (
    MatchState,
    capture_halftime,
    detect_goals,
    detect_red_cards,
    match_data_to_json,
    update_prediction,
    update_risk,
)
from livescore.json_sync.local_client import JsonLocalClient
from livescore.models import MatchData
from livescore.providers.base import BaseProvider

logger = structlog.get_logger(service="json_sync")

# Robust deletion tuning constants
NULL_DATA_ENDED_THRESHOLD = 3        # consecutive None responses from provider
FREEZE_TIME_ENDED_THRESHOLD = 5      # consecutive identical-ts polls at >= 5400s
FREEZE_TIME_NEAR90_THRESHOLD = 25    # consecutive identical-ts polls at >= 5395s
MISSING_FROM_FEED_THRESHOLD = 3      # finder cycles a tracked id is absent from live feed
HARD_TIME_CEILING_SECONDS = 6300     # clock >= 105:00 is treated as definitely-over
HARD_WALL_CLOCK_SECONDS = 2 * 60 * 60  # 2h of wall-clock tracking is the absolute cap
DELETE_RETRY_INTERVAL_SECONDS = 30.0  # backoff between failed delete retries


class JsonSyncService:
    """Fetches live matches from providers and syncs them to the JSON store.

    No database interaction — all state is held in-memory and in the JSON store
    (in ls-1x, an in-process file-backed store via ``JsonLocalClient``).
    """

    def __init__(
        self,
        providers: list[BaseProvider],
        json_client: JsonLocalClient,
        source: str = "1x",
        finder_interval: int = 30,
        updater_interval: int = 10,
    ) -> None:
        self.providers = providers
        self.json_client = json_client
        self.source = source
        self.finder_interval = finder_interval
        self.updater_interval = updater_interval
        self._provider_map: dict[str, BaseProvider] = {
            p.source_name: p for p in providers
        }
        # In-memory tracking of live matches: {source_match_id: MatchData}
        self._live_matches: dict[str, MatchData] = {}
        # Accumulated state per match: {source_match_id: MatchState}
        self._match_states: dict[str, MatchState] = {}
        # Track which matches are on the JSON store
        self._on_server: set[str] = set()
        # Freeze-time tracking (consecutive identical-ts polls at >= 5400)
        self._freeze_counts: dict[str, int] = {}
        # Consecutive None responses from provider.fetch_match_detail
        self._null_data_counts: dict[str, int] = {}
        # Consecutive finder cycles a tracked id was absent from fetch_live_matches
        self._missing_feed_counts: dict[str, int] = {}
        # Monotonic timestamp when we first started tracking a match
        self._first_seen: dict[str, float] = {}
        # Matches awaiting a successful DELETE — value is (reason, attempts, last_try_monotonic)
        self._pending_deletes: dict[str, tuple[str, int, float]] = {}

    async def run(self) -> None:
        logger.info(
            "json_sync_starting",
            providers=[p.source_name for p in self.providers],
            source=self.source,
        )
        await self._bootstrap_from_server()

        # The source repo used ``async with asyncio.TaskGroup()`` (Python 3.11+).
        # ls-1x targets Python 3.10, so this is a 3.10-safe equivalent that PRESERVES
        # TaskGroup's fail-fast semantics: both loops run concurrently; if either one
        # dies (both are ``while True:`` and swallow ordinary errors internally, so a
        # crash here means something fundamental), we cancel the sibling and re-raise
        # so ``run()``/``main()`` returns and the process exits — letting systemd's
        # ``Restart=always`` relaunch a clean, fully-healthy pair of loops. We do NOT
        # use ``gather(return_exceptions=True)`` because that would leave the survivor
        # looping forever in a silently-degraded half-service that never restarts.
        tasks = [
            asyncio.ensure_future(self._match_finder()),
            asyncio.ensure_future(self._match_updater()),
        ]
        names = {tasks[0]: "match_finder", tasks[1]: "match_updater"}
        try:
            done, pending = await asyncio.wait(
                tasks, return_when=asyncio.FIRST_EXCEPTION
            )
        except asyncio.CancelledError:
            # run() itself was cancelled (e.g. process shutdown) — cancel both loops.
            for t in tasks:
                t.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            raise

        # A loop finished (returned or raised). Cancel any still-running sibling so we
        # don't leak it, then surface the crash and let the process exit for a restart.
        for t in pending:
            t.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)

        crash: BaseException | None = None
        for t in done:
            exc = t.exception()
            if exc is not None:
                logger.error(
                    "json_sync_loop_crashed",
                    loop=names.get(t, "unknown"),
                    error=repr(exc),
                )
                crash = crash or exc
        if crash is not None:
            raise crash

    async def _bootstrap_from_server(self) -> None:
        """Seed in-memory state from whatever is already in the JSON store.

        Two side-effects worth knowing about:

        * Live (non-ended) matches are loaded into ``_live_matches`` /
          ``_match_states`` so the updater can resume managing them — this
          lets a fresh sync service pick up where a crashed one left off,
          and also absorbs matches left behind by the legacy autobet service.
        * Matches with ``status="ended"`` are *deleted* from the JSON store.
          The updater only deletes matches it personally observes transition
          live → ended, so any "ended" rows still present at startup are
          orphans (previous-process crash, out-of-band write) and would
          otherwise persist forever. Sweep them here.
        """
        existing = await self.json_client.get_all_matches(self.source)
        stale_ended_ids: list[str] = []
        for m in existing:
            mid = str(m.get("id", ""))
            if not mid:
                continue
            self._on_server.add(mid)
            status = str(m.get("status", ""))
            if status == "ended":
                stale_ended_ids.append(mid)
                continue
            # Create a minimal MatchData so the updater can fetch details
            # The source is always 1xbet for matches on the 1x collection
            self._live_matches[mid] = MatchData(
                source="1xbet",
                source_match_id=mid,
                league=str(m.get("league", "")),
                home_team=str(m.get("team1", "")),
                away_team=str(m.get("team2", "")),
                home_score=int(m.get("team1_score") or 0),
                away_score=int(m.get("team2_score") or 0),
                status={"on_going_h1": "h1", "half_time": "ht", "on_going_h2": "h2",
                        "not_started": "not_started"}.get(status, "h1"),
                time_seconds=int(m.get("time_second") or 0),
                total_prediction=float(m.get("cur_prediction") or 0) or None,
            )
            # Restore accumulated state from existing server data
            state = MatchState(
                prediction=str(m.get("prediction", "")),
                h2_prediction=str(m.get("h2_prediction", "")) if m.get("h2_prediction") else "",
                scores=str(m.get("scores", "")),
                h1_scores=str(m.get("h1_scores", "")),
                h2_scores=str(m.get("h2_scores", "")),
                h1_team1_score=str(m.get("h1_team1_score", "")),
                h1_team2_score=str(m.get("h1_team2_score", "")),
                h1_score=str(m.get("h1_score", "")),
                freeze_time=int(m.get("freeze_time") or 0),
                risk=int(m.get("risk") or 0),
            )
            self._match_states[mid] = state
            # We don't know the real first-seen time after a restart; treat
            # bootstrap-resumed matches as freshly observed so the hard
            # wall-clock ceiling still acts as a backstop, not as an instant
            # killer of legitimately-in-progress matches.
            self._first_seen[mid] = time.monotonic()

        logger.info(
            "json_sync_seeded",
            on_server=len(self._on_server),
            live_matches=len(self._live_matches),
            stale_ended=len(stale_ended_ids),
        )

        # Sweep orphaned "ended" matches discovered at startup.
        for mid in stale_ended_ids:
            await self._remove_match(mid, reason="stale_ended_at_startup")

    # ── Match Finder ─────────────────────────────────────────────────

    async def _refresh_server_ids(self) -> None:
        """Refresh _on_server from the JSON store to detect externally added matches.

        Also sweep any matches the store still has with status="ended" — those are
        orphans (left by a crashed/restarted sync service or written out-of-band)
        and should not stay in the store.
        """
        existing = await self.json_client.get_all_matches(self.source)
        self._on_server = {str(m.get("id", "")) for m in existing if m.get("id")}

        stale_ended: list[str] = []
        for m in existing:
            mid = str(m.get("id", ""))
            if not mid:
                continue
            if str(m.get("status", "")) == "ended":
                stale_ended.append(mid)
        for mid in stale_ended:
            await self._remove_match(mid, reason="stale_ended_in_finder")

    async def _match_finder(self) -> None:
        """Discover new live matches and sync them to the JSON store."""
        while True:
            # Refresh server state each cycle (like collector checks DB)
            await self._refresh_server_ids()

            # Collect every ID currently in *any* provider's live feed; we use the
            # union below to drive the orphan sweep.
            live_feed_ids: set[str] = set()

            for provider in self.providers:
                try:
                    matches = await provider.fetch_live_matches()
                    for match_data in matches:
                        mid = match_data.source_match_id
                        live_feed_ids.add(mid)
                        if mid in self._live_matches:
                            continue

                        # Initialize state for new match
                        self._live_matches[mid] = match_data
                        state = MatchState()
                        update_prediction(match_data, state)
                        update_risk(match_data, state)
                        self._match_states[mid] = state
                        self._first_seen[mid] = time.monotonic()

                        json_data = match_data_to_json(match_data, state)
                        if mid in self._on_server:
                            await self.json_client.put_match(self.source, mid, json_data)
                        else:
                            ok = await self.json_client.post_match(self.source, json_data)
                            if ok:
                                self._on_server.add(mid)
                        logger.info(
                            "json_sync_new_match",
                            match_id=mid,
                            home=match_data.home_team,
                            away=match_data.away_team,
                        )
                except Exception:
                    logger.exception("json_sync_finder_error", provider=provider.source_name)

            await self._sweep_orphans(live_feed_ids)
            await asyncio.sleep(self.finder_interval)

    async def _sweep_orphans(self, live_feed_ids: set[str]) -> None:
        """Catch matches that survived previous delete failures or were
        never observed transitioning to ended.

        A "tracked" match is anything in `_live_matches` (still being updated by
        us) plus anything in `_pending_deletes` (already marked for deletion and
        being retried). A match on the server that is not tracked AND not in
        any provider's current live feed is an orphan.

        We require ``MISSING_FROM_FEED_THRESHOLD`` consecutive finder cycles of
        absence before deleting, so a brief live-feed glitch can't wipe a
        legitimately in-progress match.
        """
        tracked = set(self._live_matches.keys()) | set(self._pending_deletes.keys())
        candidates = self._on_server - tracked - live_feed_ids

        # Reset counters for anything no longer a candidate (seen again or removed)
        for mid in list(self._missing_feed_counts.keys()):
            if mid not in candidates:
                self._missing_feed_counts.pop(mid, None)

        for mid in candidates:
            count = self._missing_feed_counts.get(mid, 0) + 1
            self._missing_feed_counts[mid] = count
            if count >= MISSING_FROM_FEED_THRESHOLD:
                logger.info(
                    "json_sync_orphan_detected",
                    match_id=mid,
                    missing_cycles=count,
                )
                await self._remove_match(mid, reason="orphan_missing_from_feed")

    # ── Match Updater ────────────────────────────────────────────────

    async def _match_updater(self) -> None:
        """Update existing matches and remove ended ones from the JSON store."""
        sem = asyncio.Semaphore(10)

        async def _update_one(source_match_id: str, prev_data: MatchData) -> None:
            async with sem:
                provider = self._provider_map.get(prev_data.source)
                if not provider:
                    return
                try:
                    data = await provider.fetch_match_detail(source_match_id)
                    if not data:
                        nc = self._null_data_counts.get(source_match_id, 0) + 1
                        self._null_data_counts[source_match_id] = nc
                        if nc >= NULL_DATA_ENDED_THRESHOLD:
                            await self._remove_match(source_match_id, reason="disappeared")
                        # Hard wall-clock backstop even while the provider is silent
                        elif self._wall_clock_expired(source_match_id):
                            await self._remove_match(
                                source_match_id, reason="wall_clock_ceiling"
                            )
                        return

                    # Provider responded: reset null-data counter
                    self._null_data_counts.pop(source_match_id, None)

                    # Carry sticky link/video fields forward when a detail
                    # response omits them (mirrors autobet preserving
                    # quick_events_url/h1_url/h2_url across compare cycles), so
                    # the QE Link doesn't flicker once the sub-game is known.
                    for _f in ("h1_url", "h2_url", "quick_events_url", "video"):
                        if not getattr(data, _f, None) and getattr(prev_data, _f, None):
                            object.__setattr__(data, _f, getattr(prev_data, _f))

                    ts = data.time_seconds or 0
                    prev_ts = prev_data.time_seconds or 0
                    state = self._match_states.get(source_match_id, MatchState())

                    # Freeze-time ended detection (separate counter from null-data)
                    if data.status == "h2" and ts >= 5400 and prev_ts == ts:
                        fc = self._freeze_counts.get(source_match_id, 0) + 1
                        self._freeze_counts[source_match_id] = fc
                        state.freeze_time = fc
                        if fc >= FREEZE_TIME_ENDED_THRESHOLD:
                            data.status = "ended"
                    elif data.status == "h2" and ts >= 5395 and prev_ts == ts:
                        fc = self._freeze_counts.get(source_match_id, 0) + 1
                        self._freeze_counts[source_match_id] = fc
                        state.freeze_time = fc
                        if fc >= FREEZE_TIME_NEAR90_THRESHOLD:
                            data.status = "ended"
                    elif data.status != "ended":
                        self._freeze_counts.pop(source_match_id, None)
                        state.freeze_time = 0

                    # Hard time-on-clock ceiling: if the provider keeps reporting
                    # an ever-advancing clock past 105:00, the match is over and
                    # we shouldn't be waiting on a freeze that will never come.
                    if data.status != "ended" and ts >= HARD_TIME_CEILING_SECONDS:
                        logger.info(
                            "json_sync_time_ceiling_ended",
                            match_id=source_match_id,
                            time_seconds=ts,
                        )
                        data.status = "ended"

                    # Hard wall-clock ceiling: independent of provider clock.
                    if (
                        data.status != "ended"
                        and self._wall_clock_expired(source_match_id)
                    ):
                        logger.info(
                            "json_sync_wall_clock_ended",
                            match_id=source_match_id,
                        )
                        data.status = "ended"

                    if data.status == "ended":
                        await self._remove_match(source_match_id, reason="ended")
                        return

                    # Update accumulated state
                    detect_goals(prev_data, data, state)
                    detect_red_cards(prev_data, data, state)
                    capture_halftime(prev_data, data, state)
                    update_prediction(data, state)
                    update_risk(data, state)

                    # Update in-memory state
                    self._live_matches[source_match_id] = data
                    self._match_states[source_match_id] = state

                    # PUT updated data to JSON store
                    json_data = match_data_to_json(data, state)
                    if source_match_id in self._on_server:
                        await self.json_client.put_match(
                            self.source, source_match_id, json_data,
                        )
                    else:
                        ok = await self.json_client.post_match(self.source, json_data)
                        if ok:
                            self._on_server.add(source_match_id)

                except Exception:
                    logger.exception("json_sync_update_error", match_id=source_match_id)

        while True:
            try:
                # Drive failed-delete retries on every updater cycle so a flaky
                # store doesn't permanently strand orphans.
                await self._retry_pending_deletes()

                # Snapshot current live matches to avoid mutation during iteration
                current = dict(self._live_matches)
                if current:
                    start = asyncio.get_event_loop().time()
                    await asyncio.gather(
                        *[_update_one(mid, md) for mid, md in current.items()],
                        return_exceptions=True,
                    )
                    elapsed = asyncio.get_event_loop().time() - start
                    sleep_time = max(0, self.updater_interval - elapsed)
                else:
                    sleep_time = self.updater_interval
            except Exception:
                logger.exception("json_sync_updater_cycle_error")
                sleep_time = self.updater_interval
            await asyncio.sleep(sleep_time)

    # ── Helpers ──────────────────────────────────────────────────────

    def _wall_clock_expired(self, source_match_id: str) -> bool:
        """True if we've been tracking this match longer than the hard cap."""
        first = self._first_seen.get(source_match_id)
        if first is None:
            return False
        return (time.monotonic() - first) >= HARD_WALL_CLOCK_SECONDS

    def _forget_match(self, source_match_id: str) -> None:
        """Drop *all* in-memory state for a match after a confirmed delete."""
        self._live_matches.pop(source_match_id, None)
        self._match_states.pop(source_match_id, None)
        self._freeze_counts.pop(source_match_id, None)
        self._null_data_counts.pop(source_match_id, None)
        self._missing_feed_counts.pop(source_match_id, None)
        self._first_seen.pop(source_match_id, None)
        self._pending_deletes.pop(source_match_id, None)

    async def _retry_pending_deletes(self) -> None:
        """Re-attempt DELETE for every match still in `_pending_deletes`.

        Uses a small backoff so we don't hammer a wedged store.
        """
        if not self._pending_deletes:
            return
        now = time.monotonic()
        # Snapshot to avoid mutation during iteration
        for mid, (reason, attempts, last_try) in list(self._pending_deletes.items()):
            if now - last_try < DELETE_RETRY_INTERVAL_SECONDS:
                continue
            ok = await self.json_client.delete_match(self.source, mid)
            if ok:
                self._on_server.discard(mid)
                logger.info(
                    "json_sync_removed",
                    match_id=mid,
                    reason=reason,
                    attempts=attempts + 1,
                )
                self._forget_match(mid)
            else:
                self._pending_deletes[mid] = (reason, attempts + 1, now)
                logger.warning(
                    "json_sync_delete_retry_failed",
                    match_id=mid,
                    reason=reason,
                    attempts=attempts + 1,
                )

    async def _remove_match(self, source_match_id: str, reason: str) -> None:
        """Atomic removal: only forget in-memory state once the DELETE lands.

        On failure the match goes into `_pending_deletes` and will be retried
        on every subsequent updater cycle. Crucially, `_live_matches` is
        cleared in either path so the regular updater stops PUTting stale
        data — but the match stays known to us via `_pending_deletes` until
        the store-side delete actually succeeds.
        """
        if source_match_id not in self._on_server:
            # Not on the server (or already removed) — just forget the local state.
            self._forget_match(source_match_id)
            return

        ok = await self.json_client.delete_match(self.source, source_match_id)
        if ok:
            self._on_server.discard(source_match_id)
            logger.info("json_sync_removed", match_id=source_match_id, reason=reason)
            self._forget_match(source_match_id)
            return

        # DELETE failed — stop updating it, but keep it pending for retry.
        self._live_matches.pop(source_match_id, None)
        self._match_states.pop(source_match_id, None)
        self._freeze_counts.pop(source_match_id, None)
        self._null_data_counts.pop(source_match_id, None)
        prior = self._pending_deletes.get(source_match_id)
        attempts = (prior[1] if prior else 0) + 1
        self._pending_deletes[source_match_id] = (reason, attempts, time.monotonic())
        logger.warning(
            "json_sync_delete_failed",
            match_id=source_match_id,
            reason=reason,
            attempts=attempts,
        )
