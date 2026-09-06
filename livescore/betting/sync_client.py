"""Synchronous 1xBet betting client — Phase 1 (READ + coupon PREVIEW only).

Callable directly from the Streamlit render thread (which is synchronous), so
this uses a blocking ``httpx.Client`` and NEVER touches the sync subsystem's
shared ``AsyncClient``/event loop.

Phase 1 implements exactly two things:

* ``fetch_game_events_sync`` — a read-only GET of the v3 ``gameEvents`` feed
  (no auth), reusing the shared ``DEFAULT_HEADERS`` from the async provider.
* ``build_coupon_events`` — a **pure** function that turns selected outcomes
  into the ``Events`` list a UpdateCoupon/MakeBetWeb request would carry
  (per BETTING_SPEC §2.2). It performs NO network I/O.

There is deliberately NO ``update_coupon_sync`` and NO ``make_bet_web_sync``
here: Phase 1 places no bets and makes no network WRITE calls. The coupon list
built here is for PREVIEW/inspection only.
"""

from __future__ import annotations

import httpx
import structlog

from livescore.providers.onexbet import DEFAULT_HEADERS

logger = structlog.get_logger()


def fetch_game_events_sync(
    base_url: str,
    match_id: str,
    proxy: str | None = None,
    *,
    count_events: int = 250,
    timeout: float = 10.0,
) -> dict | None:
    """Blocking GET of the v3 ``gameEvents`` feed for one match.

    READ-ONLY, no auth. Reuses ``DEFAULT_HEADERS`` plus a per-call ``referer``.
    Honors ``proxy`` (bookmakers block datacenter IPs, e.g. Streamlit Cloud —
    set ``SYNC_HTTP_PROXY``). Returns the raw response dict or ``None`` on any
    failure/non-200/non-JSON (never raises into the caller).
    """
    url = (
        f"{base_url}/service-api/main-live-feed/v3/gameEvents"
        f"?cfView=3&countEvents={count_events}&country=43&fcountry=43"
        f"&gameId={match_id}&gr=819&grMode=4&lng=en&marketType=1&ref=1"
    )
    headers = {**DEFAULT_HEADERS, "referer": f"{base_url}/en/live"}
    try:
        # httpx 0.28: pass the proxy as ``proxy=`` (falls back to direct when None).
        with httpx.Client(proxy=proxy or None, timeout=timeout) as client:
            resp = client.get(url, headers=headers)
    except Exception as exc:
        # Log the class/message only — never headers (no cookie/x-hd here anyway),
        # and never the full URL body. match_id is public.
        logger.warning(
            "sync_game_events_error", match_id=match_id, error=str(exc)
        )
        return None

    if resp.status_code != 200:
        logger.warning(
            "sync_game_events_http_error",
            match_id=match_id,
            status=resp.status_code,
            content_type=resp.headers.get("content-type"),
            body=resp.text[:300],
        )
        return None
    try:
        return resp.json()
    except Exception:
        logger.warning(
            "sync_game_events_json_error",
            match_id=match_id,
            content_type=resp.headers.get("content-type"),
            body=resp.text[:300],
        )
        return None


def build_coupon_events(selected: list[dict]) -> list[dict]:
    """Turn selected bet-slip outcomes into the coupon ``Events`` list.

    PURE function — no network, no side effects. Each ``selected`` entry is a
    flat dict produced by the betting UI's bet-slip, carrying at least::

        {"game_id": int, "type": int, "cf": float, "parameter": float|None}

    Returns one dict per selection in the UpdateCoupon/MakeBetWeb event shape
    (BETTING_SPEC §2.2). ``Param`` defaults to ``0`` when the outcome has no
    parameter (e.g. 1X2). This does not place a bet.
    """
    events: list[dict] = []
    for sel in selected:
        param = sel.get("parameter")
        events.append(
            {
                "GameId": int(sel["game_id"]),
                "Type": int(sel["type"]),
                "Coef": float(sel["cf"]),
                "Param": float(param) if param is not None else 0,
                "PV": None,
                "PlayerId": 0,
                "Kind": 1,
                "InstrumentId": 0,
                "Seconds": 0,
                "Price": 0,
                "Expired": 0,
            }
        )
    return events
