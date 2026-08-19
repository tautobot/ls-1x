from __future__ import annotations

from dataclasses import dataclass

from horus.models import MatchData

# Map agent.livescore status → autobet MatchStatus strings
STATUS_MAP = {
    "not_started": "not_started",
    "h1": "on_going_h1",
    "ht": "half_time",
    "h2": "on_going_h2",
    "ended": "ended",
}


def _format_league(league: str | None) -> str:
    """Prefix women's leagues with ``(W) `` for the JSON server, e.g.
    ``Slovakia. Liga 1. Women`` -> ``(W) Slovakia. Liga 1. Women``. Idempotent
    (won't double-prefix). 1xBet league names are English, so ``women`` is the marker."""
    if not league:
        return league or ""
    if league.lstrip().startswith("(W)"):
        return league
    if "women" in league.lower():
        return f"(W) {league}"
    return league


def _time_match_str(time_seconds: int | None, stoppage_time: int | None = None) -> str:
    """Convert seconds to ``MM:SS`` (with autobet-style ``+N`` extra-time suffix).

    Mirrors autobet's behavior of appending the API's ``AddTime`` minutes onto
    the displayed clock so downstream consumers see e.g. ``"45:00 +3"`` rather
    than losing the value as a separate field.
    """
    if not time_seconds:
        base = "00:00"
    else:
        minutes = time_seconds // 60
        seconds = time_seconds % 60
        base = f"{minutes:02d}:{seconds:02d}"
    if stoppage_time and stoppage_time > 0:
        return f"{base} +{stoppage_time}"
    return base


def _half_from_status(status: str) -> int:
    """Derive half number from status."""
    if status in ("not_started",):
        return 0
    if status == "h1":
        return 1
    return 2


@dataclass
class MatchState:
    """In-memory state accumulated across updates for a single match.

    Mirrors what autobet's compare_matches() preserves between cycles.
    """

    prediction: str = ""          # initial prediction (locked once set)
    h2_prediction: str = ""       # prediction captured at halftime
    scores: str = ""              # all goal times, e.g. "82:23, 27:16"
    h1_scores: str = ""           # goal times in first half
    h2_scores: str = ""           # goal times in second half
    h1_team1_score: str = ""      # home score at halftime
    h1_team2_score: str = ""      # away score at halftime
    h1_score: str = ""            # formatted "X - Y" at halftime
    freeze_time: int = 0          # freeze counter
    risk: int = 0                 # risk flag


def detect_goals(
    prev: MatchData | None,
    curr: MatchData,
    state: MatchState,
) -> None:
    """Compare scores between prev and curr, append goal times to state."""
    if prev is None:
        return

    prev_total = prev.home_score + prev.away_score
    curr_total = curr.home_score + curr.away_score

    if curr_total <= prev_total:
        return

    # A goal was scored — record the time
    time_match = _time_match_str(curr.time_seconds)
    half = _half_from_status(curr.status)

    state.scores = f"{time_match}, {state.scores}" if state.scores else time_match
    if half == 1:
        state.h1_scores = f"{time_match}, {state.h1_scores}" if state.h1_scores else time_match
    elif half == 2:
        state.h2_scores = f"{time_match}, {state.h2_scores}" if state.h2_scores else time_match


def capture_halftime(
    prev: MatchData | None,
    curr: MatchData,
    state: MatchState,
) -> None:
    """Capture h1 score and h2 prediction when match transitions to halftime."""
    prev_status = prev.status if prev else "not_started"

    # Capture h1 score at halftime (only once)
    if curr.status in ("ht", "h2") and not state.h1_score:
        if curr.status == "ht":
            # At halftime, current score IS the h1 score
            state.h1_team1_score = str(curr.home_score)
            state.h1_team2_score = str(curr.away_score)
        elif prev_status == "ht" and curr.status == "h2":
            # Transitioning from HT to H2, use prev scores as h1
            state.h1_team1_score = str(prev.home_score if prev else curr.home_score)
            state.h1_team2_score = str(prev.away_score if prev else curr.away_score)
        elif prev_status == "h1" and curr.status == "h2":
            # Jumped from h1 to h2 (missed HT), use prev scores
            state.h1_team1_score = str(prev.home_score if prev else curr.home_score)
            state.h1_team2_score = str(prev.away_score if prev else curr.away_score)
        if state.h1_team1_score:
            state.h1_score = f"{state.h1_team1_score} - {state.h1_team2_score}"

    # Capture h2 prediction at halftime (only once)
    # Also capture if match is already at HT when we first see it
    if curr.status == "ht" and not state.h2_prediction:
        cur_pred = curr.total_prediction or 0
        state.h2_prediction = str(cur_pred)


def update_prediction(curr: MatchData, state: MatchState) -> None:
    """Lock prediction from first appearance (within first 10 min)."""
    if not state.prediction:
        ts = curr.time_seconds or 0
        if ts <= 600 and curr.total_prediction:
            state.prediction = str(curr.total_prediction)


def update_risk(curr: MatchData, state: MatchState) -> None:
    """Set risk=1 if prediction >= 4 (matches autobet logic)."""
    if state.risk != 0:
        return
    pred = curr.total_prediction
    if pred and pred >= 4:
        state.risk = 1
    init_pred = float(state.prediction) if state.prediction else 0
    if init_pred >= 4:
        state.risk = 1


def match_data_to_json(data: MatchData, state: MatchState) -> dict:
    """Convert a MatchData + accumulated state to autobet JSON server format.

    All values as strings to match autobet's format — the Streamlit frontend
    sorts by these fields and crashes on mixed str/int types.
    """
    time_seconds = data.time_seconds or 0
    status = STATUS_MAP.get(data.status, "unknown")
    half = _half_from_status(data.status)
    score = f"{data.home_score} - {data.away_score}"

    cur_prediction = data.total_prediction or 0
    prediction = state.prediction or str(cur_prediction)

    result: dict = {
        "id": data.source_match_id,
        "half": str(half),
        "time_second": str(time_seconds),
        "league": _format_league(data.league),
        "team1": data.home_team,
        "team2": data.away_team,
        "team1_score": str(data.home_score),
        "team2_score": str(data.away_score),
        "penalties": None,
        "time_match": _time_match_str(time_seconds, data.stoppage_time),
        "prediction": prediction,
        "cur_prediction": str(cur_prediction),
        "scores": state.scores,
        "score": score,
        "team1_redcard": str(data.home_red_cards or 0),
        "team2_redcard": str(data.away_red_cards or 0),
        "url": data.match_url or "",
        "status": status,
        "freeze_time": str(state.freeze_time),
        "risk": str(state.risk),
    }

    # H1 score (set once halftime is reached)
    if state.h1_score:
        result["h1_team1_score"] = state.h1_team1_score
        result["h1_team2_score"] = state.h1_team2_score
        result["h1_score"] = state.h1_score

    # H2 prediction (set once at halftime)
    if state.h2_prediction:
        result["h2_prediction"] = state.h2_prediction

    # H1/H2 goal times
    if state.h1_scores:
        result["h1_scores"] = state.h1_scores
    if state.h2_scores:
        result["h2_scores"] = state.h2_scores

    # Stoppage time
    if data.stoppage_time:
        result["add_time"] = str(data.stoppage_time)

    # Stats (all as strings)
    if data.home_attacks is not None:
        result["team1_attacks"] = str(data.home_attacks)
    if data.away_attacks is not None:
        result["team2_attacks"] = str(data.away_attacks)
    if data.home_dangerous_attacks is not None:
        result["team1_d_attacks"] = str(data.home_dangerous_attacks)
    if data.away_dangerous_attacks is not None:
        result["team2_d_attacks"] = str(data.away_dangerous_attacks)
    if data.home_possession is not None:
        result["team1_possession"] = str(data.home_possession)
    if data.away_possession is not None:
        result["team2_possession"] = str(data.away_possession)
    if data.home_shots_on_target is not None:
        result["team1_shots_on_target"] = str(data.home_shots_on_target)
    if data.away_shots_on_target is not None:
        result["team2_shots_on_target"] = str(data.away_shots_on_target)
    if data.home_shots_off_target is not None:
        result["team1_shots_off_target"] = str(data.home_shots_off_target)
    if data.away_shots_off_target is not None:
        result["team2_shots_off_target"] = str(data.away_shots_off_target)

    # Computed fields
    sot_h = data.home_shots_on_target or 0
    soft_h = data.home_shots_off_target or 0
    sot_a = data.away_shots_on_target or 0
    soft_a = data.away_shots_off_target or 0
    result["team1_shots"] = f"{sot_h} + {soft_h}"
    result["team2_shots"] = f"{sot_a} + {soft_a}"
    result["total_shots"] = str(sot_h + soft_h + sot_a + soft_a)

    return result
