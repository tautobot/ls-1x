from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class MatchData(BaseModel):
    """Data returned by a provider for a single match.

    Ported verbatim (only this model) from agent.livescore's ``src/models.py``.
    The DB-layer models (Match, MatchSnapshot, etc.) are intentionally left out —
    the sync subsystem is DB-free and only needs this shape to flow from provider
    → converter → in-process JSON store.
    """

    source: str
    source_match_id: str
    league: str
    home_team: str
    away_team: str
    home_score: int = 0
    away_score: int = 0
    minute: int | None = None
    time_seconds: int | None = None
    status: str = "not_started"
    stoppage_time: int | None = None
    # Bookmaker total score prediction
    total_prediction: float | None = None
    initial_prediction: float | None = None
    h2_prediction: float | None = None
    # Match stats
    home_possession: int | None = None
    away_possession: int | None = None
    home_shots_on_target: int | None = None
    away_shots_on_target: int | None = None
    home_shots_off_target: int | None = None
    away_shots_off_target: int | None = None
    home_attacks: int | None = None
    away_attacks: int | None = None
    home_dangerous_attacks: int | None = None
    away_dangerous_attacks: int | None = None
    # Cards
    home_yellow_cards: int | None = None
    away_yellow_cards: int | None = None
    home_red_cards: int | None = None
    away_red_cards: int | None = None
    # Corners, offsides, goal kicks, free kicks
    home_corners: int | None = None
    away_corners: int | None = None
    home_offsides: int | None = None
    away_offsides: int | None = None
    home_goal_kicks: int | None = None
    away_goal_kicks: int | None = None
    home_free_kicks: int | None = None
    away_free_kicks: int | None = None
    # Substitutions & penalties
    home_substitutions: int | None = None
    away_substitutions: int | None = None
    home_penalties_awarded: int | None = None
    away_penalties_awarded: int | None = None
    # 1x2 Odds
    odds_home: float | None = None
    odds_draw: float | None = None
    odds_away: float | None = None
    # Over/Under odds
    odds_over_05: float | None = None
    odds_under_05: float | None = None
    odds_over_15: float | None = None
    odds_under_15: float | None = None
    odds_over_25: float | None = None
    odds_under_25: float | None = None
    odds_over_35: float | None = None
    odds_under_35: float | None = None
    # Quick event odds
    odds_goal_next_5min: float | None = None
    odds_goal_next_10min: float | None = None
    odds_goal_next_15min: float | None = None
    # Captured "quick" markets for validation (not yet used in bets):
    #   goal_upto_min: [[minute, yes_odds, no_odds], ...]  (1xBet G=96)
    #   interval_outcome: [[interval, home, draw, away], ...] (best-effort)
    quick_markets: dict[str, Any] | None = None
    # Match URL (link to bookmaker match page)
    match_url: str | None = None
    # Sub-game links derived from the 1xBet SG/"halfs" array (autobet parity):
    #   h1_url / h2_url        — bookmaker page for each half's sub-game
    #   quick_events_url ("QE Link") — page for the "Quick events" sub-game
    h1_url: str | None = None
    h2_url: str | None = None
    quick_events_url: str | None = None
    # Live-video availability flag (1xBet "VA" field), carried through verbatim.
    video: Any = None
    # Whether the "Goal will be scored up to a minute" market (groupId 96) is
    # offered for this match — surfaced as the "G" column, sticky once seen.
    goal_up_to_min: bool = False
    # Raw
    events: list[dict[str, Any]] = Field(default_factory=list)
    raw: dict[str, Any] = Field(default_factory=dict)


class GameEvent(BaseModel):
    """One outcome/selection inside a MarketGroup (v3 gameEvents 'event').

    Mirrors the raw event dict shape observed in the v3 ``gameEvents`` feed:
    ``{"type": int, "parameter": float?, "cf": float, "cfView": str,
    "eventParams": {"params": [...]}, "isCenter"?: bool, "blocked"?: bool}``.
    """

    type: int
    parameter: float | None = None
    cf: float
    cf_view: str | None = None
    params: list[str] = Field(default_factory=list)
    is_center: bool = False
    blocked: bool = False
    player_id: int | None = None
    player_name: str | None = None


class MarketGroup(BaseModel):
    """One betting market (a v3 ``eventGroups`` entry) for a match/subgame.

    ``name`` is resolved from ``MARKET_GROUP_NAMES`` (the raw payload carries only
    numeric ``groupId``). ``subgame_id``/``subgame_name`` identify which bettable
    game the outcomes belong to (the match itself, the current-half subgame, the
    "Quick events" subgame, etc.); both are ``None`` for top-level groups.
    """

    group_id: int
    short_group_id: int | None = None
    name: str | None = None
    subgame_id: int | None = None
    subgame_name: str | None = None
    outcomes: list[GameEvent] = Field(default_factory=list)


class MatchEvents(BaseModel):
    """Per-match v3 ``gameEvents`` snapshot — the READ side for the betting UI.

    ``all_markets`` is a flat list of every parsed group across the top-level
    ``eventGroups`` and every ``subGamesForMainGame`` entry; prioritisation and
    current-half selection happen downstream in ``prioritize_markets``.
    """

    match_id: str
    main_game_id: str | None = None
    current_period: int | None = None
    current_period_name: str | None = None
    full_score: str | None = None
    all_markets: list[MarketGroup] = Field(default_factory=list)
    fetched_at: float | None = None
