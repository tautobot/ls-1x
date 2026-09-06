"""Tests for the 1xBet v3 gameEvents parser + prioritiser + coupon builder.

Dual-mode, per this repo's convention: runnable standalone
(``poetry run python tests/test_onexbet_events.py`` — exits non-zero on failure)
AND collectable by pytest (each ``test_*`` function asserts). No live network.

Ground truth is the committed fixture ``tests/fixtures/gameevents_sample.json``
(match 750391752, 2nd half, score 1-3).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from livescore.providers.onexbet_events import (
    MARKET_GROUP_NAMES,
    TARGET_GROUP_IDS,
    _interval_width,
    _outcome_label,
    parse_game_events,
    prioritize_markets,
)
from livescore.betting.sync_client import build_coupon_events

FIXTURE = Path(__file__).parent / "fixtures" / "gameevents_sample.json"


def _load() -> dict:
    return json.loads(FIXTURE.read_text())


# --- pytest-collectable test functions ---------------------------------------


def test_match_scalars_parsed():
    events = parse_game_events(_load())
    assert events.match_id == "750391752"
    assert events.main_game_id == "750391752"
    assert events.current_period == 2
    assert events.current_period_name == "2nd half"
    assert events.full_score == "1-3"


def test_target_groups_present():
    events = parse_game_events(_load())
    found = {g.group_id for g in events.all_markets}
    # 17 (Total), 1 (1X2), 14 (Total Even), 96 (goal-up-to-min), 2750 (interval)
    # are all live in this fixture.
    for gid in (17, 1, 14, 96, 2750):
        assert gid in found, f"groupId {gid} missing from parsed markets"


def test_only_target_groups_kept():
    events = parse_game_events(_load())
    found = {g.group_id for g in events.all_markets}
    # groupId 15 (Total 1 — types 11/12) is NOT a target and must be excluded.
    assert 15 not in found
    assert found <= set(TARGET_GROUP_IDS)


def test_group_names_mapping():
    # 14 is the true Total Even/Odd; 15 (Total 1) must never be labeled that.
    assert MARKET_GROUP_NAMES.get(14) == "Total Even"
    assert MARKET_GROUP_NAMES.get(15) != "Total Even"
    assert MARKET_GROUP_NAMES.get(17) == "Total"
    assert MARKET_GROUP_NAMES.get(1) == "1X2"


def test_outcome_types_parse_correctly():
    events = parse_game_events(_load())
    # 1X2 in the half subgame: types {1,2,3}.
    x12 = _half_group(events, 1)
    assert x12 is not None
    assert {o.type for o in x12.outcomes} >= {1, 2, 3}
    # Total: Over/Under types 9/10.
    total = _half_group(events, 17)
    assert total is not None
    assert {o.type for o in total.outcomes} >= {9}
    assert any(o.type == 9 and o.parameter is not None for o in total.outcomes)
    # Total Even: types 182/183 exactly (NOT 11/12 which is group 15).
    even = [g for g in events.all_markets if g.group_id == 14][0]
    assert {o.type for o in even.outcomes} == {182, 183}


def test_half_subgame_extracted_and_preferred():
    events = parse_game_events(_load())
    # A current-half copy of 1X2 exists (subgame "2nd half").
    half_x12 = _half_group(events, 1)
    assert half_x12 is not None
    assert half_x12.subgame_name and "half" in half_x12.subgame_name.lower()


def test_prioritize_order_and_current_half_first():
    events = parse_game_events(_load())
    ordered = prioritize_markets(events)
    ids = [g.group_id for g in ordered]
    assert ids, "prioritize_markets returned nothing"
    # Total (17) ranks first, 1X2 (1) early.
    assert ids[0] == 17
    assert 1 in ids[:4]
    # Market-level order among the goals markets is 17 -> 1 -> 14.
    first_17 = ids.index(17)
    first_1 = ids.index(1)
    first_14 = ids.index(14)
    assert first_17 < first_1 < first_14
    # For a market that has both a half copy and a full-match copy, the half copy
    # comes first.
    x12_groups = [g for g in ordered if g.group_id == 1]
    if len(x12_groups) >= 2:
        assert x12_groups[0].subgame_name and "half" in x12_groups[0].subgame_name.lower()


def test_blocked_flag_parsed():
    events = parse_game_events(_load())
    # groupId 96 in this fixture is fully blocked (not currently bettable).
    g96 = [g for g in events.all_markets if g.group_id == 96]
    assert g96, "groupId 96 expected in fixture"
    assert all(o.blocked for o in g96[0].outcomes)


def test_interval_width_helper():
    events = parse_game_events(_load())
    g2750 = [g for g in events.all_markets if g.group_id == 2750][0]
    # Fixture's live interval is params ["1","3"] => width 2.
    assert _interval_width(g2750) == 2.0


def test_outcome_label_helper():
    events = parse_game_events(_load())
    total = _half_group(events, 17)
    over = next(o for o in total.outcomes if o.type == 9)
    label = _outcome_label(17, over)
    assert label.startswith("Over (")
    x12 = _half_group(events, 1)
    w1 = next(o for o in x12.outcomes if o.type == 1)
    assert _outcome_label(1, w1) == "W1"


def test_build_coupon_events_shape():
    slip = [
        {"group_id": 17, "type": 9, "parameter": 2.5, "cf": 1.552,
         "game_id": 750391768, "label": "Over 2.5"},
        {"group_id": 1, "type": 1, "parameter": None, "cf": 2.08,
         "game_id": 750391768, "label": "W1"},
    ]
    events = build_coupon_events(slip)
    assert len(events) == 2
    assert events[0]["GameId"] == 750391768
    assert events[0]["Type"] == 9
    assert events[0]["Coef"] == 1.552
    assert events[0]["Param"] == 2.5
    # None parameter (1X2) defaults to 0.
    assert events[1]["Param"] == 0
    # All the constant scaffold keys are present.
    for k in ("PV", "PlayerId", "Kind", "InstrumentId", "Seconds", "Price", "Expired"):
        assert k in events[0]
    assert events[0]["PlayerId"] == 0 and events[0]["Kind"] == 1


def test_empty_input_is_safe():
    events = parse_game_events({})
    assert events.match_id == ""
    assert events.all_markets == []
    assert prioritize_markets(events) == []


def test_no_live_bet_path_exists():
    """Phase-1 real-money safety TRIPWIRE.

    Phase 1 must NOT contain any bet-placement code. If a later phase adds a live
    write path it should be a deliberate, reviewed change — this test failing is
    the alarm. Guards against accidentally reintroducing a MakeBetWeb/UpdateCoupon
    call into the betting package.
    """
    from livescore.betting import sync_client
    assert not hasattr(sync_client, "update_coupon_sync")
    assert not hasattr(sync_client, "make_bet_web_sync")

    import livescore.betting as betting_pkg
    betting_dir = Path(betting_pkg.__file__).parent
    for py in betting_dir.rglob("*.py"):
        text = py.read_text()
        # No HTTP write, and no live bet-endpoint PATH may be present (docstrings
        # naming the markets are fine — we key on the actual URL path + verb).
        assert ".post(" not in text, f"{py.name} performs an HTTP POST (Phase 1 must not place bets)"
        for path in ("LiveBet/Secure/MakeBetWeb", "LiveBet-update/Open/UpdateCoupon"):
            assert path not in text, f"{py.name} references bet endpoint {path!r}"


# --- helpers -----------------------------------------------------------------


def _half_group(events, group_id):
    """Return the current-half copy of a group, else the first copy found."""
    groups = [g for g in events.all_markets if g.group_id == group_id]
    for g in groups:
        if g.subgame_name and "half" in g.subgame_name.lower():
            return g
    return groups[0] if groups else None


# --- standalone runner (repo convention) -------------------------------------


def _main() -> int:
    failures: list[str] = []
    tests = [
        obj
        for name, obj in sorted(globals().items())
        if name.startswith("test_") and callable(obj)
    ]
    for test in tests:
        try:
            test()
        except AssertionError as exc:
            failures.append(f"{test.__name__}: {exc}")
        except Exception as exc:  # noqa: BLE001 - surface any error as a failure
            failures.append(f"{test.__name__}: unexpected {type(exc).__name__}: {exc}")

    if failures:
        print(f"FAILED {len(failures)} of {len(tests)} checks:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print(f"All {len(tests)} checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(_main())
