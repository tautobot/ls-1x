#!/usr/bin/env python
"""Seed realistic test data into the local in-process JSON store.

Runs through the REAL JsonServerProcessor API (post_match), never direct file
writes, so it exercises the same code path the app relies on. Idempotent
(upsert by id) and reversible (--clean removes only the ids it created).

Usage:
    poetry run python scripts/seed_test_data.py            # seed
    poetry run python scripts/seed_test_data.py --summary  # seed + print summary
    poetry run python scripts/seed_test_data.py --clean    # remove seeded ids

Target the store via JSON_DB_PATH env (defaults to <repo>/db.json). This seeder
refuses to run against anything that looks like a production/remote target.
"""
import os
import sys
import argparse

# Guard: this seeder injects XSS/SQLi-shaped strings and synthetic data.
# It must only ever touch a LOCAL file store. There is no network target in the
# in-process design, but we still assert JSON_DB_PATH is a local filesystem path.
_target = os.environ.get('JSON_DB_PATH', '')
if '://' in _target or _target.startswith('http'):
    sys.exit(f'REFUSING to run: JSON_DB_PATH looks remote: {_target!r}')

from livescore.json_server import JsonServerProcessor  # noqa: E402
from livescore.enums import MatchStatus  # noqa: E402

SOURCE = '1x'

# Seeded-id prefix so --clean can identify exactly what we created without
# touching any real records.
SEED_PREFIX = '9900'


def _mk(i, risk, status=None, **extra):
    # SHAPE FIDELITY: every value must match what livescore/json_sync/converter.py emits,
    # because app.py sorts on / string-compares these fields. In particular:
    #   * `half`  -> str (converter emits str(half)); an int here would (a) crash
    #     utils.sort_json's itemgetter('half',...) if seed & sync data ever mix, and
    #     (b) make the app's `row.half == '1'/'2'` coloring branches unreachable.
    #   * `score` -> "H - A" (converter: f"{home} - {away}"); the app's green/orange
    #     coloring compares `row.score in ('0 - 0', '0 - 1', ...)`.
    #   * `team1_shots`/`team2_shots` -> "N + M" (converter format); without them
    #     highlight_rows' "both shots NaN -> red" branch fires for every row and masks
    #     the risk-based pink/cyan branches.
    home_goals, away_goals = i % 4, (i + 1) % 3
    rec = {
        'id'        : f'{SEED_PREFIX}{i:03d}',
        'league'    : extra.pop('league', f'Test League {i}'),
        'team1'     : extra.pop('team1', f'Home {i}'),
        'team2'     : extra.pop('team2', f'Away {i}'),
        'half'      : extra.pop('half', str((i % 2) + 1)),   # str, mirroring converter
        'time_match': extra.pop('time_match', f'{20 + (i % 40):02d}:0{i % 10}'),
        'score'     : extra.pop('score', f'{home_goals} - {away_goals}'),  # "H - A"
        'risk'      : risk,          # stored as string, mirroring production
        'prediction': extra.pop('prediction', str(round(2 + (i % 4) * 0.5, 1))),
        # Shots in the converter's "on + off" string form so highlight_rows can parse
        # them and the risk-based / green / orange coloring paths become exercisable.
        'team1_shots': extra.pop('team1_shots', f'{i % 3} + {i % 4}'),
        'team2_shots': extra.pop('team2_shots', f'{(i + 1) % 3} + {(i + 2) % 4}'),
    }
    if status is not None:
        rec['status'] = status
    rec.update(extra)
    return rec


def build_records():
    """Realistic shape, volume, distribution across risk x status, plus edge cases."""
    statuses = [
        MatchStatus.ON_GOING_H1, MatchStatus.EXTRA_TIME_H1, MatchStatus.HALF_TIME,
        MatchStatus.ON_GOING_H2, MatchStatus.EXTRA_TIME_H2, MatchStatus.NOT_STARTED,
        MatchStatus.ENDED, MatchStatus.UNKNOWN,
    ]
    # Risk values the app filters on: '0','-1','-2' (potential/good) plus '1','2' (higher).
    risks = ['0', '-1', '-2', '1', '2', '3']
    records = []
    i = 0
    # Cross-product-ish spread so every filter value has data on both sides.
    for s in statuses:
        for r in risks:
            records.append(_mk(i, r, s))
            i += 1
    # Long-tail / edge cases:
    records.append(_mk(i, '-1'))  # NO status field -> must be excluded by status filters
    i += 1
    records.append(_mk(i, '-2', MatchStatus.ON_GOING_H1,
                       team1='Cluj-Napoca', team2='Đội Bóng 🇻🇳',  # unicode/CJK/emoji + diacritics
                       league='Liga I'))
    i += 1
    records.append(_mk(i, '0', MatchStatus.HALF_TIME,
                       team1="<script>alert('xss')</script>",       # XSS-shaped input
                       team2="Robert'); DROP TABLE matches;--"))    # SQLi-shaped input
    i += 1
    records.append(_mk(i, '-1', MatchStatus.ON_GOING_H2,
                       team1='X' * 200))  # max-length-ish string
    i += 1
    return records


def seed():
    records = build_records()
    created, updated = 0, 0
    for rec in records:
        # Upsert: put if exists, else post (idempotent re-runs).
        existing = JsonServerProcessor(source=SOURCE, params={'id': rec['id']}).get_match()
        if existing.get('success'):
            JsonServerProcessor(source=SOURCE, params=rec).put_match()
            updated += 1
        else:
            resp = JsonServerProcessor(source=SOURCE, params=rec).post_match()
            if resp.status_code == 201:
                created += 1
            else:
                print(f'  WARN post {rec["id"]} -> {resp.status_code}: {resp.json()}')
    return created, updated, len(records)


def clean():
    removed = 0
    all_ = JsonServerProcessor(source=SOURCE, params={'skip_convert_data_types': True}).get_all_matches()['data']
    for rec in all_:
        rid = str(rec.get('id', ''))
        if rid.startswith(SEED_PREFIX):
            resp = JsonServerProcessor(source=SOURCE, params={'id': rid}).delete_match()
            if resp.status_code == 200:
                removed += 1
    return removed


def summary():
    data = JsonServerProcessor(source=SOURCE, params={'skip_convert_data_types': True}).get_all_matches()['data']
    seeded = [r for r in data if str(r.get('id', '')).startswith(SEED_PREFIX)]
    from collections import Counter
    print(f'\n-- store summary (collection {SOURCE!r}) --')
    print(f'total records: {len(data)} | seeded by this script: {len(seeded)}')
    print('risk distribution (seeded):', dict(Counter(str(r.get("risk")) for r in seeded)))
    print('status distribution (seeded):', dict(Counter(str(r.get("status")) for r in seeded)))
    print('records with NO status key:', sum(1 for r in seeded if 'status' not in r))
    print('sample seeded ids:', [r['id'] for r in seeded[:5]], '...')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--clean', action='store_true', help='remove only seeded ids')
    ap.add_argument('--summary', action='store_true', help='print store summary after seeding')
    args = ap.parse_args()

    if args.clean:
        n = clean()
        print(f'removed {n} seeded records')
        return

    created, updated, total = seed()
    print(f'seeded {total} records ({created} created, {updated} updated) into {SOURCE!r}')
    if args.summary:
        summary()


if __name__ == '__main__':
    main()
