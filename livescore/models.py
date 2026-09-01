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
    # Raw
    events: list[dict[str, Any]] = Field(default_factory=list)
    raw: dict[str, Any] = Field(default_factory=dict)
