"""Parsing + prioritisation for the 1xBet v3 ``gameEvents`` feed.

The v3 feed (`GET .../main-live-feed/v3/gameEvents`) is the READ side of the
betting UI: it exposes every live market for a single match as numeric
``groupId`` buckets, each carrying a list of outcome events.

Two structural facts drive the defensive parsing here (confirmed against
``tests/fixtures/gameevents_sample.json``):

1. **No fixed location for a market.** Markets can appear at the top level
   (``raw["eventGroups"]``) AND/OR nested inside ``raw["subGamesForMainGame"]``
   entries (the current half, "Corners", "Quick events", etc.). The same
   ``groupId`` (e.g. 17 "Total") legitimately appears in multiple subgames with
   different meaning (goals Total vs. Corners Total). So the parser scans every
   container and records which subgame each group came from, and the
   market-picking is a *parse-time filter* by subgame name — never an assumption
   about a fixed path.

2. **``events`` is a list-of-lists.** Each group's ``events`` is a list whose
   items are themselves lists of event dicts; they must be flattened.

Only the six target markets (see ``TARGET_GROUP_IDS``) are surfaced to the
betting UI; ``prioritize_markets`` orders them with the current-half copies
first.

Nothing in this module performs any network I/O or bet placement.
"""

from __future__ import annotations

import time
from typing import Any

from livescore.models import GameEvent, MarketGroup, MatchEvents

# Human-readable names for the target market groupIds (the raw payload carries
# only numeric groupId). groupId 2750 is width-qualified at render time (5m/10m),
# so its base name is generic here — see ``_interval_width``/``_outcome_label``.
MARKET_GROUP_NAMES: dict[int, str] = {
    1: "1X2",
    17: "Total",
    14: "Total Even",
    96: "Goal Will Be Scored Up To A Minute",
    2750: "Closest Interval Outcome",
}

# Display priority order used by ``prioritize_markets`` (market-level ordering;
# current-half vs full-match is a secondary sort key applied within a market).
TARGET_GROUP_IDS: tuple[int, ...] = (17, 1, 14, 96, 2750)

# Groups 1/17/14 (goals 1X2 / Total / Total-Even) must only ever be collected
# from the current-half/period subgames or the top level — NEVER from these
# named subgames, whose same-groupId markets mean something different (Corners
# Total, Result+Total combos, accumulator outcomes, per-player stats). This is a
# parse-time exclusion so a Corners-Total can never be mislabeled as goals-Total.
_HALF_ONLY_GROUP_IDS: frozenset[int] = frozenset({1, 17, 14})
_EXCLUDED_HALF_SUBGAME_NAMES: frozenset[str] = frozenset(
    {"corners", "result + total", "accumulator outcomes", "players' stats"}
)

# Goal-up-to-minute (96) and the interval markets (2750) are NOT half-scoped:
# in real payloads 96 appears at the top level (and, when offered, under
# "Quick events") and 2750 appears under the "Quick events" subgame. They are
# therefore accepted from ANY container (see ``_keep_group``), and ordering is
# left to ``prioritize_markets``.
_QUICK_GROUP_IDS: frozenset[int] = frozenset({96, 2750})

# Per-market outcome type -> short label, for the six target markets.
_OUTCOME_TYPE_LABELS: dict[int, dict[int, str]] = {
    1: {1: "W1", 2: "X", 3: "W2"},           # 1X2
    17: {9: "Over", 10: "Under"},            # Total
    14: {182: "Even", 183: "Odd"},           # Total Even/Odd
    96: {812: "Yes", 813: "No"},             # Goal up to minute
    2750: {3626: "W1", 3627: "X", 3628: "W2"},  # Interval outcome
}


def _iter_event_dicts(events: Any) -> list[dict]:
    """Flatten a group's ``events`` (a list-of-lists) into a flat list of dicts.

    Tolerates the occasional flat list or stray dict without raising.
    """
    flat: list[dict] = []
    if not isinstance(events, list):
        return flat
    for item in events:
        if isinstance(item, list):
            flat.extend(e for e in item if isinstance(e, dict))
        elif isinstance(item, dict):
            flat.append(item)
    return flat


def _parse_event(raw_event: dict) -> GameEvent | None:
    """Map one raw v3 event dict onto a ``GameEvent``. Returns None if unusable."""
    etype = raw_event.get("type")
    cf = raw_event.get("cf")
    if etype is None or cf is None:
        return None
    event_params = raw_event.get("eventParams") or {}
    params = event_params.get("params") if isinstance(event_params, dict) else None
    if not isinstance(params, list):
        params = []
    try:
        return GameEvent(
            type=int(etype),
            parameter=raw_event.get("parameter"),
            cf=float(cf),
            cf_view=raw_event.get("cfView"),
            params=[str(p) for p in params],
            is_center=bool(raw_event.get("isCenter", False)),
            blocked=bool(raw_event.get("blocked", False)),
            player_id=raw_event.get("playerId"),
            player_name=raw_event.get("playerName"),
        )
    except (TypeError, ValueError):
        return None


def _parse_group(
    raw_group: dict,
    *,
    subgame_id: int | None,
    subgame_name: str | None,
) -> MarketGroup | None:
    """Parse one raw ``eventGroups`` entry into a ``MarketGroup``.

    Only target groupIds are kept; a group is dropped when it carries no
    parseable outcomes.
    """
    group_id = raw_group.get("groupId")
    if group_id is None:
        return None
    try:
        group_id = int(group_id)
    except (TypeError, ValueError):
        return None
    if group_id not in TARGET_GROUP_IDS:
        return None

    outcomes: list[GameEvent] = []
    for raw_event in _iter_event_dicts(raw_group.get("events")):
        parsed = _parse_event(raw_event)
        if parsed is not None:
            outcomes.append(parsed)
    if not outcomes:
        return None

    return MarketGroup(
        group_id=group_id,
        short_group_id=raw_group.get("shortGroupId"),
        name=MARKET_GROUP_NAMES.get(group_id),
        subgame_id=subgame_id,
        subgame_name=subgame_name,
        outcomes=outcomes,
    )


def _is_period_subgame(subgame_name: str | None) -> bool:
    """True when a subgame is a football half/period (current-half copy)."""
    if not subgame_name:
        return False
    name = subgame_name.lower()
    return "half" in name or "period" in name


def _keep_group(group_id: int, subgame_name: str | None) -> bool:
    """Parse-time filter deciding whether a group in this subgame is wanted.

    - Goals 1X2/Total/Total-Even (1/17/14): keep only from half/period subgames
      or the top level (``subgame_name is None``); never from Corners/Result+
      Total/Accumulator/Players' stats.
    - Quick markets (96/2750): accepted from any container (they live top-level
      or in "Quick events"); prioritisation handles ordering.
    """
    if group_id in _HALF_ONLY_GROUP_IDS:
        if subgame_name is None:
            return True  # top-level goals market
        low = subgame_name.lower()
        if low in _EXCLUDED_HALF_SUBGAME_NAMES:
            return False
        return _is_period_subgame(subgame_name)
    return True


def parse_game_events(raw: dict) -> MatchEvents:
    """Parse a raw v3 ``gameEvents`` response into ``MatchEvents``.

    Defensive: scans the top-level ``eventGroups`` (which may be absent) AND
    every ``subGamesForMainGame`` entry, flattens the list-of-lists ``events``,
    and applies the parse-time subgame filter (``_keep_group``) so goals markets
    are never sourced from Corners/accumulator subgames.
    """
    if not isinstance(raw, dict):
        raw = {}

    scores = raw.get("scores") or {}
    match_id = raw.get("id")
    main_game_id = raw.get("mainGameId")

    all_markets: list[MarketGroup] = []

    def _collect(groups: Any, subgame_id: int | None, subgame_name: str | None) -> None:
        if not isinstance(groups, list):
            return
        for raw_group in groups:
            if not isinstance(raw_group, dict):
                continue
            gid = raw_group.get("groupId")
            try:
                gid_int = int(gid) if gid is not None else None
            except (TypeError, ValueError):
                gid_int = None
            if gid_int is None or gid_int not in TARGET_GROUP_IDS:
                continue
            if not _keep_group(gid_int, subgame_name):
                continue
            parsed = _parse_group(
                raw_group, subgame_id=subgame_id, subgame_name=subgame_name
            )
            if parsed is not None:
                all_markets.append(parsed)

    # Top-level eventGroups (may be absent — hence ``or []``).
    _collect(raw.get("eventGroups") or [], None, None)

    # Every subgame's eventGroups.
    for subgame in raw.get("subGamesForMainGame") or []:
        if not isinstance(subgame, dict):
            continue
        _collect(
            subgame.get("eventGroups") or [],
            subgame.get("id"),
            subgame.get("subGameName"),
        )

    return MatchEvents(
        match_id=str(match_id) if match_id is not None else "",
        main_game_id=str(main_game_id) if main_game_id is not None else None,
        current_period=scores.get("currentPeriod"),
        current_period_name=scores.get("currentPeriodName"),
        full_score=scores.get("fullScore"),
        all_markets=all_markets,
        fetched_at=time.time(),
    )


def _interval_width(group: MarketGroup) -> float | None:
    """Interval width (end - start) in minutes for a groupId-2750 market.

    Reads the first outcome whose ``params`` has >=2 numeric boundary strings.
    """
    for outcome in group.outcomes:
        if len(outcome.params) >= 2:
            try:
                return float(outcome.params[1]) - float(outcome.params[0])
            except ValueError:
                continue
    return None


def prioritize_markets(events: MatchEvents) -> list[MarketGroup]:
    """Order the target markets for display.

    Market order: Total (17) -> 1X2 (1) -> Total Even (14) ->
    Goal-up-to-minute (96) -> Interval Outcome 10m (2750, width 8..12) ->
    Interval Outcome 5m (2750, other widths). Within a market, the current-half
    copy sorts before the full-match copy. Non-target groups are excluded.
    """
    half_subgame_ids = {
        g.subgame_id
        for g in events.all_markets
        if _is_period_subgame(g.subgame_name)
    }

    def rank(g: MarketGroup) -> tuple[int, int]:
        if g.group_id == 17:
            prio = 0
        elif g.group_id == 1:
            prio = 1
        elif g.group_id == 14:
            prio = 2
        elif g.group_id == 96:
            prio = 3
        elif g.group_id == 2750:
            width = _interval_width(g)
            prio = 4 if width is not None and 8 <= width <= 12 else 5
        else:
            return (99, 1)
        half_bonus = 0 if g.subgame_id in half_subgame_ids else 1
        return (prio, half_bonus)

    picked = [g for g in events.all_markets if g.group_id in TARGET_GROUP_IDS]
    return sorted(picked, key=rank)


def _outcome_label(group_id: int, event: GameEvent) -> str:
    """Human-readable label for one outcome (for the betting UI).

    Examples: ``"Over (2.5)"``, ``"W1"``, ``"Even"``, ``"Yes (80')"``,
    ``"W1 [1-3']"``. Falls back to ``"Type {n}"`` for unknown types.
    """
    base = _OUTCOME_TYPE_LABELS.get(group_id, {}).get(event.type)
    if base is None:
        base = f"Type {event.type}"

    if group_id == 17:
        # Total Over/Under with the goal line.
        if event.parameter is not None:
            return f"{base} ({event.parameter:g})"
        return base
    if group_id == 96:
        # Goal up to a minute — parameter encodes the minute (int part).
        if event.parameter is not None:
            return f"{base} ({int(event.parameter)}')"
        return base
    if group_id == 2750:
        # Interval outcome — params carry the literal [start, end] boundaries.
        if len(event.params) >= 2:
            return f"{base} [{event.params[0]}-{event.params[1]}']"
        return base
    # 1X2 (1) and Total Even (14) need no parameter qualifier.
    return base
