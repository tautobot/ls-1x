from __future__ import annotations

import re
from typing import Any

import httpx
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

from livescore.models import MatchData
from livescore.providers.base import BaseProvider

logger = structlog.get_logger()

ANTISPORTS = ",".join(str(i) for i in range(2, 79))

# Shared browser-like request headers for 1xBet endpoints. Extracted from the
# per-instance headers previously inlined in ``OneXBetProvider.__init__`` so the
# synchronous betting client (``livescore/betting/sync_client.py``) can reuse the
# exact same User-Agent/sec-ch-ua set without duplicating the string — single
# source of truth. The ``referer`` stays per-instance/per-call because it depends
# on ``base_url``.
DEFAULT_HEADERS: dict[str, str] = {
    "sec-ch-ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
    "sec-ch-ua-mobile": "?0",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "content-type": "application/json",
    "accept": "application/json, text/plain, */*",
    "x-requested-with": "XMLHttpRequest",
    "sec-ch-ua-platform": '"macOS"',
}

# Standings ID → field mapping
STANDINGS_MAP: dict[int, tuple[str, str]] = {
    29: ("home_possession", "away_possession"),
    45: ("home_attacks", "away_attacks"),
    58: ("home_dangerous_attacks", "away_dangerous_attacks"),
    59: ("home_shots_on_target", "away_shots_on_target"),
    60: ("home_shots_off_target", "away_shots_off_target"),
    26: ("home_corners", "away_corners"),
    47: ("home_offsides", "away_offsides"),
    70: ("home_yellow_cards", "away_yellow_cards"),
    71: ("home_red_cards", "away_red_cards"),
    92: ("home_free_kicks", "away_free_kicks"),
    94: ("home_goal_kicks", "away_goal_kicks"),
}

# Name-based mapping takes priority over ID (some leagues swap IDs)
STANDINGS_NAME_MAP: dict[str, tuple[str, str]] = {
    "possession %": ("home_possession", "away_possession"),
    "attacks": ("home_attacks", "away_attacks"),
    "dangerous attacks": ("home_dangerous_attacks", "away_dangerous_attacks"),
    "shots on target": ("home_shots_on_target", "away_shots_on_target"),
    "shots off target": ("home_shots_off_target", "away_shots_off_target"),
    "corner": ("home_corners", "away_corners"),
    "corners": ("home_corners", "away_corners"),
    "offsides": ("home_offsides", "away_offsides"),
    "yellow cards": ("home_yellow_cards", "away_yellow_cards"),
    "yellow card": ("home_yellow_cards", "away_yellow_cards"),
    "red card": ("home_red_cards", "away_red_cards"),
    "red cards": ("home_red_cards", "away_red_cards"),
    "free kicks": ("home_free_kicks", "away_free_kicks"),
    "goal kicks": ("home_goal_kicks", "away_goal_kicks"),
    "substitutions": ("home_substitutions", "away_substitutions"),
    "penalty": ("home_penalties_awarded", "away_penalties_awarded"),
    "penalties": ("home_penalties_awarded", "away_penalties_awarded"),
}

# Dot-path field mapping from raw API response
FIELD_MAP = {
    "I": "id",
    "LI": "league_id",
    "LE": "league",
    "O1E": "home_team",
    "O2E": "away_team",
    "SC.CP": "half",
    "SC.CPS": "half_text",
    "SC.TS": "time_seconds",
    "SC.FS.S1": "home_score",
    "SC.FS.S2": "away_score",
    "SC.ST": "standings_obj",
    "SC.S": "additional_info",
    "SC.I": "main_info",
    "AE": "games",
    "SG": "halfs",
    "GE": "event_odds",
}


def _get_nested(obj: dict, dotpath: str) -> Any:
    """Extract a value from a nested dict using dot-path notation."""
    parts = dotpath.split(".")
    current: Any = obj
    for part in parts:
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


_STOPPAGE_DIGITS = re.compile(r"\d+")


def _extract_stoppage(additional_info: Any) -> int | None:
    """Extract stoppage-time minutes from a 1x/8x ``SC.S`` array.

    The entry shape is ``{"Key": "AddTime", "Value": <minutes>}``. ``Value``
    is usually a string of digits like ``"3"`` but can be an int, padded
    (``" 3"``), or carry a leading sign (``"+3"``). We accept all of those
    and only return None when no digits can be found.
    """
    if not isinstance(additional_info, list):
        return None
    for info in additional_info:
        if not isinstance(info, dict) or info.get("Key") != "AddTime":
            continue
        raw = info.get("Value")
        if raw is None:
            return None
        if isinstance(raw, int):
            return raw
        match = _STOPPAGE_DIGITS.search(str(raw))
        if match:
            try:
                return int(match.group(0))
            except ValueError:
                return None
        return None
    return None


def _map_status(half: int, time_seconds: int, half_text: str | None = None) -> str:
    """Map raw 1xBet half/time values to match status.

    Ported from autobet onexbet.py:1881-1904 + compare_matches:2157-2160.
    Key: half=0/3 means post-match in 1xBet encoding.
    half=1 is H1, half=2 covers HT and H2.
    """
    # "Game Finished" text is definitive
    if half_text and str(half_text).lower() == "game finished":
        return "ended"
    # half 0 or 3 with time at 90min = ended
    if half in (0, 3) and time_seconds >= 5400:
        return "ended"
    # Not started
    if time_seconds == 0 and half == 0:
        return "not_started"
    # H1
    if half == 1 and time_seconds > 0:
        return "h1"
    if half == 1:
        return "h1"
    # Halftime: half=2 at exactly 0s or 2700s (45:00)
    if half == 2 and (time_seconds == 0 or time_seconds == 2700):
        return "ht"
    # H2: half=2 and time progressing (including stoppage time >= 5400)
    if half == 2 and time_seconds > 2700:
        return "h2"
    if half == 2:
        return "h2"
    return "not_started"


class OneXBetProvider(BaseProvider):
    source_name = "1xbet"

    def __init__(self, client: httpx.AsyncClient, settings: Any) -> None:
        self.client = client
        self.base_url = settings.x1_base_url
        # Cache of odds from live feed: {source_match_id: {odds fields}}
        self._odds_cache: dict[str, dict[str, float | None]] = {}
        # Cache of sub-game IDs: {source_match_id: [h1_sub_id, h2_sub_id]}
        self._subgame_cache: dict[str, list[str]] = {}
        # Reuse the shared header set; the ``referer`` is base_url-dependent so it
        # stays per-instance.
        self.headers = {**DEFAULT_HEADERS, "referer": f"{self.base_url}/en/live"}

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=4), reraise=True)
    async def _get(self, url: str) -> dict | None:
        resp = await self.client.get(url, headers=self.headers, timeout=10.0)
        if resp.status_code != 200:
            # Include a body snippet so an IP/geo block page (403/451/HTML/captcha)
            # is diagnosable from the logs instead of a bare status code.
            logger.warning(
                "x1_http_error", status=resp.status_code, url=url,
                content_type=resp.headers.get("content-type"),
                body=resp.text[:300],
            )
            return None
        try:
            return resp.json()
        except Exception:
            # A 200 that isn't JSON is typically an anti-bot / block interstitial.
            logger.warning(
                "x1_json_error", url=url,
                content_type=resp.headers.get("content-type"),
                body=resp.text[:300],
            )
            raise

    async def _get_live_count(self) -> int:
        url = (
            f"{self.base_url}/service-api/LiveFeed/GetSportsShortZip"
            f"?sports=1&lng=en&gr=820&country=43&antisports={ANTISPORTS}&virtualSports=true"
        )
        data = await self._get(url)
        if not data:
            return 50
        value = data.get("Value")
        if isinstance(value, list):
            for sport in value:
                if isinstance(sport, dict) and sport.get("I") == 1:
                    count = sport.get("C", 50)
                    return max(50, ((count // 10) + 1) * 10)
        return 50

    async def fetch_live_matches(self) -> list[MatchData]:
        try:
            num = await self._get_live_count()
            url = (
                f"{self.base_url}/service-api/LiveFeed/Get1x2_VZip"
                f"?sports=1&count={num}&lng=en&gr=503"
                f"&antisports={ANTISPORTS}"
                f"&mode=4&country=43&partner=25&virtualSports=true&noFilterBlockEvent=true"
            )
            data = await self._get(url)
            if not data:
                return []

            matches: list[MatchData] = []
            for entry in data.get("Value", []):
                if not isinstance(entry, dict):
                    continue
                # Filter: football only (CID=1), skip virtual/special
                if entry.get("CID") != 1:
                    continue
                mio = entry.get("MIO")
                if not mio or (isinstance(mio, dict) and "MaF" in mio):
                    continue
                try:
                    m = self._parse_entry(entry)
                    if m:
                        matches.append(m)
                        # Cache odds from live feed for use in fetch_match_detail
                        self._cache_odds(m)
                except Exception:
                    logger.exception("x1_parse_error", match_id=entry.get("I"))
            return matches
        except Exception:
            logger.exception("x1_fetch_live_error")
            return []

    async def fetch_match_detail(self, match_id: str) -> MatchData | None:
        try:
            # ``isSubGames=true`` is what makes GetGameZip return the ``SG``
            # ("halfs") array — the H1/H2 half sub-games and the "Quick events"
            # sub-game whose ids build the H1/H2/QE links. Without it the feed
            # omits ``SG`` entirely, so those links are always empty (autobet's
            # working detail fetch always sends ``isSubGames=true&GroupEvents=true``).
            # We keep ls-1x's existing ``topGroups=96,...`` so the G=96
            # goal-up-to-minute quick_markets keep parsing — autobet's URL drops
            # that group, but we don't need to give it up to gain SG.
            url = (
                f"{self.base_url}/service-api/LiveFeed/GetGameZip"
                f"?id={match_id}&lng=en&cfview=0&is498=true&from498=true"
                f"&isSubGames=true&GroupEvents=true"
                f"&topGroups=96,27,14,136,303,307,309,7961,275"
            )
            data = await self._get(url)
            if not data or not data.get("Value"):
                return None
            result = self._parse_entry(data["Value"])
            if result:
                self._merge_cached_odds(result)
            return result
        except Exception:
            logger.exception("x1_fetch_detail_error", match_id=match_id)
            return None

    async def fetch_game_events(self, match_id: str, count_events: int = 250) -> dict | None:
        """Fetch the v3 ``gameEvents`` feed for a single match (per-match markets).

        READ-ONLY, no auth required — the v3 feed returns 200 with no
        cookies/x-hd (see scratchpad/v3_findings.md). Returns the raw response
        dict (``id``, ``scores``, ``eventGroups``, ``subGamesForMainGame``,
        ``marketEventsCount``, ...) or ``None`` on failure/block. Parsing into
        ``MatchEvents`` is done separately by
        ``livescore.providers.onexbet_events.parse_game_events``.
        """
        url = (
            f"{self.base_url}/service-api/main-live-feed/v3/gameEvents"
            f"?cfView=3&countEvents={count_events}&country=43&fcountry=43"
            f"&gameId={match_id}&gr=819&grMode=4&lng=en&marketType=1&ref=1"
        )
        return await self._get(url)

    def _parse_entry(self, raw: dict) -> MatchData | None:
        # Extract fields via dot-path
        fields: dict[str, Any] = {}
        for dotpath, name in FIELD_MAP.items():
            fields[name] = _get_nested(raw, dotpath)

        match_id = fields.get("id")
        if not match_id:
            return None

        half = int(fields.get("half") or 0)
        time_seconds = int(fields.get("time_seconds") or 0)
        half_text_val = fields.get("half_text")
        half_text_str = str(half_text_val) if half_text_val else None
        status = _map_status(half, time_seconds, half_text_str)
        minute = time_seconds // 60 if time_seconds else 0

        # Parse standings — use name-based mapping (reliable) over ID-based (can be swapped)
        stats: dict[str, int | None] = {}
        standings_obj = fields.get("standings_obj") or []
        if isinstance(standings_obj, list) and standings_obj:
            first = standings_obj[0] if isinstance(standings_obj[0], dict) else {}
            standings_list = first.get("Value", []) if first.get("Key") == 0 else []
            for s in standings_list:
                name = (s.get("N") or "").strip().lower()
                sid = s.get("ID")
                # Prefer name-based mapping (handles swapped IDs across leagues)
                if name in STANDINGS_NAME_MAP:
                    home_key, away_key = STANDINGS_NAME_MAP[name]
                elif sid in STANDINGS_MAP:
                    home_key, away_key = STANDINGS_MAP[sid]
                else:
                    continue
                stats[home_key] = s.get("S1") or 0
                stats[away_key] = s.get("S2") or 0

        # Fallback: parse cards from main_info (SC.I) if standings didn't have them
        if "home_red_cards" not in stats or "home_yellow_cards" not in stats:
            main_info = fields.get("main_info") or []
            if isinstance(main_info, list):
                for mi in main_info:
                    if not isinstance(mi, dict):
                        continue
                    mid = mi.get("ID")
                    if mid == 71 and "home_red_cards" not in stats:
                        stats["home_red_cards"] = mi.get("S1") or 0
                        stats["away_red_cards"] = mi.get("S2") or 0
                    elif mid == 70 and "home_yellow_cards" not in stats:
                        stats["home_yellow_cards"] = mi.get("S1") or 0
                        stats["away_yellow_cards"] = mi.get("S2") or 0

        # Parse prediction from games (game type 17)
        total_prediction: float | None = None
        games = fields.get("games") or []
        if isinstance(games, list):
            for game in games:
                if not isinstance(game, dict):
                    continue
                if game.get("G") == 17:
                    for cg in game.get("ME", []):
                        if (
                            isinstance(cg, dict)
                            and cg.get("CE") == 1
                            and cg.get("G") == 17
                            and cg.get("T") == 9
                        ):
                            total_prediction = cg.get("P")

        # Parse odds from games (AE) and event_odds (GE)
        odds: dict[str, float | None] = {}
        event_odds = fields.get("event_odds") or []
        all_games = list(games if isinstance(games, list) else []) + list(event_odds if isinstance(event_odds, list) else [])
        if all_games:
            for game in all_games:
                if not isinstance(game, dict):
                    continue
                for me in game.get("ME", []):
                    if not isinstance(me, dict):
                        continue
                    t = me.get("T")
                    c = me.get("C")
                    if t == 1:
                        odds["odds_home"] = c
                    elif t == 2:
                        odds["odds_draw"] = c
                    elif t == 3:
                        odds["odds_away"] = c
                    elif t == 9:  # total over
                        p = me.get("P")
                        if p is not None:
                            key = f"odds_over_{str(p).replace('.', '')}".rstrip("0")
                            if key in (
                                "odds_over_05", "odds_over_15",
                                "odds_over_25", "odds_over_35",
                            ):
                                odds[key] = c
                    elif t == 10:  # total under
                        p = me.get("P")
                        if p is not None:
                            key = f"odds_under_{str(p).replace('.', '')}".rstrip("0")
                            if key in (
                                "odds_under_05", "odds_under_15",
                                "odds_under_25", "odds_under_35",
                            ):
                                odds[key] = c
                    # Quick events
                    elif t == 3809:
                        odds["odds_goal_next_5min"] = c
                    elif t == 3811:
                        odds["odds_goal_next_10min"] = c
                    elif t == 3813:
                        odds["odds_goal_next_15min"] = c

        # Parse odds from flat E field (GetGameZip detail endpoint)
        flat_events = raw.get("E") or []
        if isinstance(flat_events, list):
            for ev in flat_events:
                if not isinstance(ev, dict):
                    continue
                g = ev.get("G")
                t = ev.get("T")
                c = ev.get("C")
                if c is None:
                    continue
                # G=1: 1x2 match result
                if g == 1:
                    if t == 1:
                        odds.setdefault("odds_home", c)
                    elif t == 2:
                        odds.setdefault("odds_draw", c)
                    elif t == 3:
                        odds.setdefault("odds_away", c)
                # G=17: total goals over/under
                elif g == 17:
                    p = ev.get("P")
                    if p is not None:
                        if t == 9:
                            key = f"odds_over_{str(p).replace('.', '')}".rstrip("0")
                            if key in ("odds_over_05", "odds_over_15", "odds_over_25", "odds_over_35"):
                                odds.setdefault(key, c)
                        elif t == 10:
                            key = f"odds_under_{str(p).replace('.', '')}".rstrip("0")
                            if key in ("odds_under_05", "odds_under_15", "odds_under_25", "odds_under_35"):
                                odds.setdefault(key, c)

        # Parse stoppage time from additional_info (SC.S "AddTime" entry).
        # 1xBet typically returns Value as a string of minutes ("3") but the
        # field is loosely typed across leagues — handle int, padded strings,
        # and leading-sign forms like "+3" without losing the value.
        additional_info = fields.get("additional_info") or []
        stoppage_time = _extract_stoppage(additional_info)

        # Capture "quick" markets for later validation (NOT used in betting yet).
        # G=96 = "Goal will be scored up to minute" (T=812 yes, T=813 no, P=minute).
        quick_markets: dict[str, Any] | None = None
        gutm: dict[int, dict[str, float]] = {}
        for ev in (flat_events if isinstance(flat_events, list) else []):
            if not isinstance(ev, dict) or ev.get("G") != 96:
                continue
            p, t, c = ev.get("P"), ev.get("T"), ev.get("C")
            if p is None or c is None:
                continue
            mn = int(float(p))  # e.g. 60.004 -> 60
            slot = gutm.setdefault(mn, {})
            if t == 812:
                slot["yes"] = c
            elif t == 813:
                slot["no"] = c
        if gutm:
            quick_markets = {
                "goal_upto_min": [[m, gutm[m].get("yes"), gutm[m].get("no")] for m in sorted(gutm)]
            }

        # FALLBACK window signal — "Interval Outcome (10m)" from Quick Events (X = no goal
        # in the 10-min interval). Priority is handled in analysis/quick_markets.py:
        # goal-up-to-minute (above) first, interval-outcome second.
        # Mechanism (decoded from the live feed, our base only): GetGameZip returns only the
        # market groups named in `topGroups` (that's why G=96 is fetched). The interval-outcome
        # market lives under its own groupId — add that id to `topGroups` and it arrives in this
        # same `E` array as a 3-way market (parameter = interval start minute). It is NOT the
        # coupon's Type=3794 (a betslip-only code); the feed uses its own type numbering, and it
        # is only offered on some matches. `scripts/interval_discovery.py` auto-detects the
        # groupId from a live match that offers it — confirm calibration, then set it here and
        # parse into quick_markets["interval_outcome_10m"] = [[start_min, w1, x, w2], ...].
        # Capture-and-validate: not wired until the groupId is confirmed on our base.

        # Parse events
        events: list[dict[str, Any]] = []

        # Build match URL
        league_name = str(fields.get("league") or "Unknown").lower().replace(" ", "-")
        league_id = fields.get("league_id") or ""
        match_url = f"{self.base_url}/en/live/football/{league_id}-{league_name}/{match_id}"

        # Sub-game links + "QE Link" (Quick events) — ported from autobet
        # onexbet.py:1951-1969. Each half and the "Quick events" market are exposed
        # by 1xBet as their own sub-games inside the SG ("halfs") array; their URLs
        # reuse this match's league slug but swap in the sub-game id.
        h1_game_id = h2_game_id = quick_game_id = None
        halfs = fields.get("halfs")
        if isinstance(halfs, list):
            for g in halfs:
                if not isinstance(g, dict) or g.get("MG") != match_id:
                    continue
                tg = g.get("TG")
                if tg == "Quick events":
                    quick_game_id = g.get("I")
                elif not tg:  # half sub-games carry no TG group name
                    if g.get("P") == 1:
                        h1_game_id = g.get("I")
                    elif g.get("P") == 2:
                        h2_game_id = g.get("I")

        def _game_url(gid: Any) -> str | None:
            if not gid:
                return None
            return f"{self.base_url}/en/live/football/{league_id}-{league_name}/{gid}"

        h1_url = _game_url(h1_game_id)
        h2_url = _game_url(h2_game_id)
        quick_events_url = _game_url(quick_game_id)

        # Live-video availability flag (1xBet "VA"), carried through like autobet.
        video = raw.get("VA")

        # Whether the "Goal will be scored up to a minute" market (G=96) is on
        # offer — the "G" column flags matches you can bet that event on.
        goal_up_to_min = bool(quick_markets and quick_markets.get("goal_upto_min"))

        return MatchData(
            source="1xbet",
            source_match_id=str(match_id),
            league=str(fields.get("league") or "Unknown"),
            home_team=str(fields.get("home_team") or "Unknown"),
            away_team=str(fields.get("away_team") or "Unknown"),
            home_score=int(fields.get("home_score") or 0),
            away_score=int(fields.get("away_score") or 0),
            minute=minute,
            time_seconds=time_seconds,
            status=status,
            stoppage_time=stoppage_time,
            match_url=match_url,
            h1_url=h1_url,
            h2_url=h2_url,
            quick_events_url=quick_events_url,
            video=video,
            goal_up_to_min=goal_up_to_min,
            total_prediction=total_prediction,
            initial_prediction=total_prediction if time_seconds <= 300 else None,
            home_possession=stats.get("home_possession"),
            away_possession=stats.get("away_possession"),
            home_shots_on_target=stats.get("home_shots_on_target"),
            away_shots_on_target=stats.get("away_shots_on_target"),
            home_shots_off_target=stats.get("home_shots_off_target"),
            away_shots_off_target=stats.get("away_shots_off_target"),
            home_attacks=stats.get("home_attacks"),
            away_attacks=stats.get("away_attacks"),
            home_dangerous_attacks=stats.get("home_dangerous_attacks"),
            away_dangerous_attacks=stats.get("away_dangerous_attacks"),
            home_yellow_cards=stats.get("home_yellow_cards"),
            away_yellow_cards=stats.get("away_yellow_cards"),
            home_red_cards=stats.get("home_red_cards"),
            away_red_cards=stats.get("away_red_cards"),
            home_corners=stats.get("home_corners"),
            away_corners=stats.get("away_corners"),
            home_offsides=stats.get("home_offsides"),
            away_offsides=stats.get("away_offsides"),
            home_free_kicks=stats.get("home_free_kicks"),
            away_free_kicks=stats.get("away_free_kicks"),
            home_goal_kicks=stats.get("home_goal_kicks"),
            away_goal_kicks=stats.get("away_goal_kicks"),
            home_substitutions=stats.get("home_substitutions"),
            away_substitutions=stats.get("away_substitutions"),
            home_penalties_awarded=stats.get("home_penalties_awarded"),
            away_penalties_awarded=stats.get("away_penalties_awarded"),
            odds_home=odds.get("odds_home"),
            odds_draw=odds.get("odds_draw"),
            odds_away=odds.get("odds_away"),
            odds_over_05=odds.get("odds_over_05"),
            odds_under_05=odds.get("odds_under_05"),
            odds_over_15=odds.get("odds_over_15"),
            odds_under_15=odds.get("odds_under_15"),
            odds_over_25=odds.get("odds_over_25"),
            odds_under_25=odds.get("odds_under_25"),
            odds_over_35=odds.get("odds_over_35"),
            odds_under_35=odds.get("odds_under_35"),
            odds_goal_next_5min=odds.get("odds_goal_next_5min"),
            odds_goal_next_10min=odds.get("odds_goal_next_10min"),
            odds_goal_next_15min=odds.get("odds_goal_next_15min"),
            quick_markets=quick_markets,
            events=events,
            raw=raw,
        )

    def _cache_odds(self, m: MatchData) -> None:
        """Cache odds from a parsed MatchData (from live feed)."""
        odds: dict[str, float | None] = {}
        for field in (
            "odds_home", "odds_draw", "odds_away",
            "odds_over_05", "odds_under_05", "odds_over_15", "odds_under_15",
            "odds_over_25", "odds_under_25", "odds_over_35", "odds_under_35",
            "odds_goal_next_5min", "odds_goal_next_10min", "odds_goal_next_15min",
            "total_prediction",
        ):
            val = getattr(m, field, None)
            if val is not None:
                odds[field] = val
        if odds:
            self._odds_cache[m.source_match_id] = odds

    def _merge_cached_odds(self, m: MatchData) -> None:
        """Merge cached odds into a MatchData from detail fetch (which lacks odds)."""
        cached = self._odds_cache.get(m.source_match_id)
        if not cached:
            return
        for field, val in cached.items():
            if getattr(m, field, None) is None and val is not None:
                object.__setattr__(m, field, val)

    async def fetch_half_odds(self, source_match_id: str, half: str) -> dict[str, float | None]:
        """Fetch under odds for a specific half from the sub-game endpoint.

        For H1 bets: fetches H1 sub-game odds (under 0.5/1.5 for H1 goals).
        For H2 bets: uses the full match odds (under line for total goals).

        Returns dict with keys like 'under_05', 'under_15', etc.
        """
        try:
            if half == "h1":
                # Discover sub-game IDs if not cached
                if source_match_id not in self._subgame_cache:
                    await self._discover_subgames(source_match_id)
                sub_ids = self._subgame_cache.get(source_match_id, [])
                if not sub_ids:
                    return {}
                # First sub-game is H1
                return await self._fetch_subgame_under_odds(sub_ids[0])
            else:
                # H2: use full match odds
                return await self._fetch_subgame_under_odds(source_match_id)
        except Exception:
            logger.exception("fetch_half_odds_error", match_id=source_match_id, half=half)
            return {}

    async def _discover_subgames(self, source_match_id: str) -> None:
        """Fetch full match with isSubGames=true to discover H1/H2 sub-game IDs."""
        url = (
            f"{self.base_url}/service-api/LiveFeed/GetGameZip"
            f"?id={source_match_id}&lng=en&isSubGames=true&GroupEvents=true"
            f"&countevents=250&grMode=4&topGroups=&country=43&marketType=1&isNewBuilder=true"
        )
        data = await self._get(url)
        if not data or not data.get("Value"):
            return
        sg = data["Value"].get("SG", [])
        # Collect half sub-game IDs: empty TG (not corners/quick events/etc)
        half_ids: list[str] = []
        for s in sg:
            if not isinstance(s, dict):
                continue
            tg = s.get("TG")
            # Half sub-games have empty/None TG — skip named sub-games
            if (tg is None or tg == "") and "I" in s:
                half_ids.append(str(s["I"]))
        # First is H1, second is H2
        self._subgame_cache[source_match_id] = half_ids[:2]

    async def _fetch_subgame_under_odds(self, subgame_id: str) -> dict[str, float | None]:
        """Fetch under odds from a sub-game (or full match) using GroupEvents format."""
        url = (
            f"{self.base_url}/service-api/LiveFeed/GetGameZip"
            f"?id={subgame_id}&lng=en&isSubGames=true&GroupEvents=true"
            f"&countevents=250&grMode=4&topGroups=&country=43&marketType=1&isNewBuilder=true"
        )
        data = await self._get(url)
        if not data or not data.get("Value"):
            return {}

        result: dict[str, float | None] = {}
        ge = data["Value"].get("GE", [])
        for g in ge:
            if not isinstance(g, dict) or g.get("G") != 17:
                continue
            for event_group in g.get("E", []):
                # GroupEvents=true: E entries are lists of related odds
                items = event_group if isinstance(event_group, list) else [event_group]
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    t = item.get("T")
                    c = item.get("C")
                    p = item.get("P")
                    if t == 10 and c is not None and p is not None:
                        # Under line: T=10, P=line (0.5, 1.0, 1.5, etc.)
                        key = f"under_{str(p).replace('.', '')}".rstrip("0")
                        result[key] = float(c)
        return result

    async def close(self) -> None:
        pass  # client is shared, closed externally
