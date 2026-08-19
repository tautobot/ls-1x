from __future__ import annotations

import asyncio
from typing import Any

import httpx
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

from horus.models import MatchData
from horus.providers.base import BaseProvider
from horus.providers.onexbet import _extract_stoppage

logger = structlog.get_logger()


def _get_nested(obj: dict, dotpath: str) -> Any:
    parts = dotpath.split(".")
    current: Any = obj
    for part in parts:
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


FIELD_MAP = {
    "iid": "id",
    "kickoffTime": "kickoff_time",
    "SC.CP": "half",
    "SC.TS": "time_seconds",
    "LI": "league_id",
    "LE": "league",
    "O1E": "home_team",
    "O2E": "away_team",
    "SC.FS.S1": "home_score",
    "SC.FS.S2": "away_score",
    "SC.ST": "standings_obj",
    "SC.S": "additional_info",
    "SC.I": "main_info",
    "AE": "games",
}

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


def _map_status(half: int, time_seconds: int) -> str:
    # half 0 or 3 with time at 90min = ended
    if half in (0, 3) and time_seconds >= 5400:
        return "ended"
    if time_seconds == 0 and half == 0:
        return "not_started"
    if half == 1 and time_seconds > 0:
        return "h1"
    if half == 1:
        return "h1"
    if half == 2 and (time_seconds == 0 or time_seconds == 2700):
        return "ht"
    # H2 including stoppage time (time_seconds can exceed 5400)
    if half == 2 and time_seconds > 2700:
        return "h2"
    if half == 2:
        return "h2"
    return "not_started"


class EightXBetProvider(BaseProvider):
    source_name = "8xbet"

    def __init__(self, client: httpx.AsyncClient, settings: Any) -> None:
        self.client = client
        self.base_url = settings.x8_base_url
        self.origin = settings.x8_origin
        self.domain = settings.x8_domain
        self.headers = {
            "accept": "application/json, text/plain, */*",
            "accept-language": "en-us",
            "apptype": "1",
            "currency": "VND",
            "device": "mobile",
            "priority": "u=1, i",
            "referer": f"{self.origin}/",
            "region": "VN",
            "sec-ch-ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"macOS"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "cross-site",
            "time-zone": "GMT+07:00",
            "user-agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            "x-uuid": "284103216e541e2f3c614cf33f60e10b",
            "authority": self.domain,
            "origin": self.origin,
        }
        self._sem = asyncio.Semaphore(5)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=4), reraise=True)
    async def _get(self, url: str) -> dict | None:
        resp = await self.client.get(url, headers=self.headers, timeout=10.0)
        if resp.status_code != 200:
            logger.warning("x8_http_error", status=resp.status_code, url=url)
            return None
        return resp.json()

    async def _fetch_one(self, match_id: str) -> MatchData | None:
        async with self._sem:
            return await self.fetch_match_detail(match_id)

    async def fetch_live_matches(self) -> list[MatchData]:
        try:
            url = (
                f"{self.base_url}/product/business/sport/tournament/info"
                "?sid=1&inplay=true&sort=tournament&language=en-us"
            )
            data = await self._get(url)
            if not data or not data.get("data"):
                return []

            match_ids: list[str] = []
            tournaments = data["data"].get("tournaments", [])
            for tournament in tournaments:
                for match in tournament.get("matches", []):
                    iid = match.get("iid")
                    if iid:
                        match_ids.append(str(iid))

            # Fetch all match details concurrently with semaphore
            results = await asyncio.gather(
                *[self._fetch_one(mid) for mid in match_ids],
                return_exceptions=True,
            )
            matches: list[MatchData] = []
            for r in results:
                if isinstance(r, MatchData):
                    matches.append(r)
                elif isinstance(r, Exception):
                    logger.warning("x8_match_fetch_failed", error=str(r))
            return matches
        except Exception:
            logger.exception("x8_fetch_live_error")
            return []

    async def fetch_match_detail(self, match_id: str) -> MatchData | None:
        try:
            url = (
                f"{self.base_url}/product/business/sport/inplay/match"
                f"?sid=1&iid={match_id}&vd=a"
            )
            data = await self._get(url)
            if not data or data.get("code") != 0:
                return None
            match_data = data.get("data", {}).get("data")
            if not match_data:
                return None
            return self._parse(match_data, match_id)
        except Exception:
            logger.exception("x8_fetch_detail_error", match_id=match_id)
            return None

    def _parse(self, raw: dict, match_id: str) -> MatchData | None:
        fields: dict[str, Any] = {}
        for dotpath, name in FIELD_MAP.items():
            if "." in dotpath:
                fields[name] = _get_nested(raw, dotpath)
            else:
                fields[name] = raw.get(dotpath)

        half = int(fields.get("half") or 0)
        time_seconds = int(fields.get("time_seconds") or 0)
        status = _map_status(half, time_seconds)
        minute = time_seconds // 60 if time_seconds else 0

        # Parse standings
        stats: dict[str, int | None] = {}
        standings_obj = fields.get("standings_obj") or []
        if isinstance(standings_obj, list) and standings_obj:
            first = standings_obj[0] if isinstance(standings_obj[0], dict) else {}
            standings_list = first.get("Value", []) if first.get("Key") == 0 else []
            for s in standings_list:
                sid = s.get("ID")
                if sid in STANDINGS_MAP:
                    home_key, away_key = STANDINGS_MAP[sid]
                    stats[home_key] = s.get("S1") or 0
                    stats[away_key] = s.get("S2") or 0

        # Fallback: parse cards from main_info if standings didn't have them
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

        # Parse prediction and odds from games
        total_prediction: float | None = None
        odds: dict[str, float | None] = {}
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

        # Stoppage time (SC.S "AddTime" entry, same shape as 1xBet).
        stoppage_time = _extract_stoppage(fields.get("additional_info"))

        # Build match URL
        match_url = f"{self.origin}/sportEvents/inplay/football/match/{match_id}"

        return MatchData(
            source="8xbet",
            source_match_id=match_id,
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
            odds_home=odds.get("odds_home"),
            odds_draw=odds.get("odds_draw"),
            odds_away=odds.get("odds_away"),
            events=[],
            raw=raw,
        )

    async def close(self) -> None:
        pass
