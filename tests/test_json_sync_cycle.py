"""
Integration suite for the sync service finder+updater cycle with a STUBBED provider.

Runs standalone (no pytest required), matching this repo's plain-script convention:

    poetry run python tests/test_json_sync_cycle.py

Exits non-zero if any assertion fails. Uses an isolated temp DB and a fake provider
(no network) so it is fully deterministic and CI-safe.

Proves the end-to-end pipeline WITHOUT hitting a bookmaker:
  provider.fetch_live_matches -> service._match_finder -> converter -> local_client
  -> jsondb -> db.json   (record lands, correctly shaped)
and the ended transition:
  provider.fetch_match_detail(status="ended") -> service._match_updater
  -> service._remove_match -> local_client.delete_match -> record is gone.

Also asserts the converter output carries the exact field names/string-typed values
app.py reads (id, status, risk, time_second, league, team1/2, scores, url, ...).
"""
import os
import sys
import asyncio
import tempfile

# Isolate the store BEFORE importing horus modules.
_TMPDIR = tempfile.mkdtemp(prefix="qa_sync_cycle_")
DB = os.path.join(_TMPDIR, "db.json")
os.environ["JSON_DB_PATH"] = DB

from horus import jsondb  # noqa: E402
jsondb.JSON_DB_PATH = DB
from horus.models import MatchData  # noqa: E402
from horus.providers.base import BaseProvider  # noqa: E402
from horus.json_sync.local_client import JsonLocalClient  # noqa: E402
from horus.json_sync.service import JsonSyncService  # noqa: E402
from horus.json_sync.converter import MatchState, match_data_to_json  # noqa: E402

SOURCE = "1x"

_PASS = 0
_FAIL = 0
_FAILURES = []


def check(cond, msg):
    global _PASS, _FAIL
    if cond:
        _PASS += 1
    else:
        _FAIL += 1
        _FAILURES.append(msg)
        print(f"  FAIL: {msg}")


def _fresh_db():
    jsondb._save_atomic(jsondb._seed(), DB)


def _md(mid, status="h1", ts=600, home=0, away=0, pred=2.5):
    """Build a MatchData as if a provider had returned it. source='1xbet' so the
    updater routes it back to the same fake provider (matched by source_name)."""
    return MatchData(
        source="1xbet",
        source_match_id=mid,
        league="Test League",
        home_team=f"Home {mid}",
        away_team=f"Away {mid}",
        home_score=home,
        away_score=away,
        status=status,
        time_seconds=ts,
        total_prediction=pred,
        match_url=f"https://example.test/match/{mid}",
    )


class FakeProvider(BaseProvider):
    """Deterministic provider stub. Feeds canned live matches + detail responses."""

    source_name = "1xbet"

    def __init__(self):
        self._live = []                    # returned by fetch_live_matches
        self._detail = {}                  # {source_match_id: MatchData | None}

    def set_live(self, matches):
        self._live = matches

    def set_detail(self, mid, match_data):
        self._detail[mid] = match_data

    async def fetch_live_matches(self):
        return list(self._live)

    async def fetch_match_detail(self, match_id):
        return self._detail.get(match_id)


async def _one_cycle(coro_fn):
    """Drive exactly one iteration of an infinite loop coroutine.

    _match_finder / _match_updater are `while True:` loops that sleep at the end
    of each cycle. Running under a tiny timeout lets the first cycle body execute,
    then the terminal sleep is interrupted by the timeout — which we treat as the
    normal way to stop after one cycle.
    """
    try:
        await asyncio.wait_for(coro_fn(), timeout=0.3)
    except asyncio.TimeoutError:
        pass


async def test_finder_inserts_correctly_shaped_record():
    _fresh_db()
    provider = FakeProvider()
    provider.set_live([_md("777", status="h1", ts=600, home=0, away=0, pred=2.5)])
    svc = JsonSyncService(
        providers=[provider],
        json_client=JsonLocalClient(db_path=DB),
        source=SOURCE,
        finder_interval=0.05,
        updater_interval=0.05,
    )
    await svc._bootstrap_from_server()
    await _one_cycle(svc._match_finder)

    rows = jsondb.get_collection(SOURCE, DB)
    check(len(rows) == 1, "finder inserted exactly one record")
    if not rows:
        return
    rec = rows[0]
    # Shape / field-name / string-typing contract app.py depends on:
    check(rec.get("id") == "777", "record id == source_match_id ('777')")
    check(rec.get("status") == "on_going_h1", "status mapped h1 -> 'on_going_h1'")
    check(rec.get("team1") == "Home 777", "team1 == home_team")
    check(rec.get("team2") == "Away 777", "team2 == away_team")
    check(rec.get("league") == "Test League", "league passed through")
    check(rec.get("url") == "https://example.test/match/777", "url == match_url")
    check(rec.get("score") == "0 - 0", "score formatted 'H - A'")
    check(isinstance(rec.get("risk"), str), "risk is a STRING (app sorts on it)")
    check(isinstance(rec.get("time_second"), str), "time_second is a STRING")
    check(isinstance(rec.get("cur_prediction"), str), "cur_prediction is a STRING")
    check(rec.get("time_match") == "10:00", "time_match formatted MM:SS from 600s")


async def test_converter_shape_matches_app_reads():
    # Direct converter assertion (independent of the service) — locks the exact
    # field set app.py's covert_json_to_dataframe() reads.
    md = _md("888", status="ht", ts=2700, home=1, away=0, pred=3.0)
    out = match_data_to_json(md, MatchState())
    for key in ("id", "half", "time_second", "league", "team1", "team2",
                "team1_score", "team2_score", "time_match", "prediction",
                "cur_prediction", "scores", "score", "url", "status",
                "freeze_time", "risk"):
        check(key in out, f"converter output has key '{key}'")
    check(out["id"] == "888", "converter id == source_match_id")
    check(out["status"] == "half_time", "converter mapped ht -> 'half_time'")
    check(all(isinstance(out[k], str) for k in
              ("half", "time_second", "team1_score", "team2_score",
               "cur_prediction", "risk", "freeze_time")),
          "converter emits numeric-ish fields as strings")


async def test_updater_deletes_on_ended_transition():
    _fresh_db()
    provider = FakeProvider()
    live = _md("777", status="h2", ts=5400, home=1, away=1, pred=2.5)
    provider.set_live([live])
    svc = JsonSyncService(
        providers=[provider],
        json_client=JsonLocalClient(db_path=DB),
        source=SOURCE,
        finder_interval=0.05,
        updater_interval=0.05,
    )
    await svc._bootstrap_from_server()

    # 1) Finder discovers + inserts the live match.
    await _one_cycle(svc._match_finder)
    rows = jsondb.get_collection(SOURCE, DB)
    check(len(rows) == 1, "match present after finder cycle")
    check("777" in svc._live_matches, "match tracked in-memory after finder")

    # 2) Provider now reports the match as ENDED on the next detail fetch.
    provider.set_detail("777", _md("777", status="ended", ts=5700, home=1, away=1))

    # 3) Updater cycle observes the ended transition and removes the record.
    await _one_cycle(svc._match_updater)
    rows_after = jsondb.get_collection(SOURCE, DB)
    check(len(rows_after) == 0, "ended match was DELETED from the store")
    check("777" not in svc._live_matches, "ended match forgotten from in-memory tracking")
    check("777" not in svc._on_server, "ended match dropped from _on_server set")


async def test_updater_updates_live_record():
    _fresh_db()
    provider = FakeProvider()
    provider.set_live([_md("777", status="h1", ts=600, home=0, away=0, pred=2.5)])
    svc = JsonSyncService(
        providers=[provider],
        json_client=JsonLocalClient(db_path=DB),
        source=SOURCE,
        finder_interval=0.05,
        updater_interval=0.05,
    )
    await svc._bootstrap_from_server()
    await _one_cycle(svc._match_finder)

    # Provider reports progress: a goal + advanced clock, still live.
    provider.set_detail("777", _md("777", status="h2", ts=3000, home=1, away=0, pred=2.5))
    await _one_cycle(svc._match_updater)

    rows = jsondb.get_collection(SOURCE, DB)
    check(len(rows) == 1, "live match still present after updater cycle")
    if rows:
        rec = rows[0]
        check(rec.get("status") == "on_going_h2", "updater advanced status h1 -> on_going_h2")
        check(rec.get("score") == "1 - 0", "updater reflected the new score '1 - 0'")


async def test_run_fails_fast_on_loop_crash():
    """run() must NOT hang if one loop dies: it cancels the sibling and re-raises
    so the process exits and systemd Restart=always relaunches a clean pair.
    Regression guard for the TaskGroup->wait(FIRST_EXCEPTION) rewrite."""
    _fresh_db()
    provider = FakeProvider()
    svc = JsonSyncService(
        providers=[provider],
        json_client=JsonLocalClient(db_path=DB),
        source=SOURCE,
        finder_interval=0.05,
        updater_interval=0.05,
    )

    sentinel = RuntimeError("boom in finder")

    async def exploding_finder():
        raise sentinel

    # One loop dies immediately; the other is a normal infinite loop.
    svc._match_finder = exploding_finder  # type: ignore[assignment]

    raised = None
    try:
        # If run() hung (old gather behavior), wait_for would TimeoutError instead.
        await asyncio.wait_for(svc.run(), timeout=2.0)
    except asyncio.TimeoutError:
        raised = "TIMEOUT"
    except RuntimeError as e:
        raised = e

    check(raised is sentinel, "run() re-raised the crashing loop's exception (did not hang)")
    # The surviving updater task must have been cancelled, not left running/leaked.
    # Find the updater task by repr and assert it is done (cancelled), not pending.
    updater_task = next(
        (t for t in asyncio.all_tasks()
         if t is not asyncio.current_task() and "_match_updater" in repr(t)),
        None,
    )
    # If it's already gone from the loop's task set, it was cleaned up (also fine).
    check(
        updater_task is None or updater_task.done(),
        "run() cancelled the surviving loop (no leaked _match_updater task)",
    )


async def _run():
    tests = [
        test_finder_inserts_correctly_shaped_record,
        test_converter_shape_matches_app_reads,
        test_updater_updates_live_record,
        test_updater_deletes_on_ended_transition,
        test_run_fails_fast_on_loop_crash,
    ]
    for t in tests:
        print(f"- {t.__name__}")
        await t()


def main():
    asyncio.run(_run())
    print(f"\n{_PASS} passed, {_FAIL} failed")
    if _FAIL:
        for f in _FAILURES:
            print(f"  x {f}")
        sys.exit(1)
    print("OK: finder inserts correctly-shaped records; updater updates live and deletes ended")


if __name__ == "__main__":
    main()
