"""
Unit suite for the in-process JSON store client (horus/json_sync/local_client.py).

Runs standalone (no pytest required), matching this repo's plain-script convention:

    poetry run python tests/test_local_client.py

Exits non-zero if any assertion fails. Uses an isolated temp DB (passed explicitly
via JsonLocalClient(db_path=...)) and never touches the repo's real db.json.

Covers the JsonLocalClient contract that JsonSyncService relies on:
  * post_match  = upsert (insert; on id-exists ValueError -> update in place)
  * put_match   = update; insert if not-found
  * delete_match = idempotent (True if removed OR already absent)
  * get_all_matches = full collection
"""
import os
import sys
import asyncio
import tempfile

# Isolate: point the store at a temp file BEFORE importing horus modules.
_TMPDIR = tempfile.mkdtemp(prefix="qa_local_client_")
DB = os.path.join(_TMPDIR, "db.json")
os.environ["JSON_DB_PATH"] = DB

from horus import jsondb  # noqa: E402
jsondb.JSON_DB_PATH = DB
from horus.json_sync.local_client import JsonLocalClient  # noqa: E402

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
    """Reset the temp store to the empty seed between test groups."""
    jsondb._save_atomic(jsondb._seed(), DB)


def _rec(mid, **extra):
    r = {"id": mid, "team1": f"Home {mid}", "team2": f"Away {mid}", "status": "on_going_h1"}
    r.update(extra)
    return r


async def test_post_inserts_new():
    _fresh_db()
    c = JsonLocalClient(db_path=DB)
    ok = await c.post_match(SOURCE, _rec("100"))
    check(ok is True, "post_match on fresh id returns True")
    rows = await c.get_all_matches(SOURCE)
    check(len(rows) == 1, "post_match inserted exactly one row")
    check(rows[0]["id"] == "100", "inserted row has id '100'")
    check(rows[0]["team1"] == "Home 100", "inserted row carries payload fields")


async def test_post_upserts_on_conflict():
    _fresh_db()
    c = JsonLocalClient(db_path=DB)
    await c.post_match(SOURCE, _rec("100", score="0 - 0"))
    # Second post with SAME id but mutated payload must UPDATE, not raise/duplicate.
    ok = await c.post_match(SOURCE, _rec("100", score="1 - 0", status="on_going_h2"))
    check(ok is True, "post_match on existing id (upsert) returns True")
    rows = await c.get_all_matches(SOURCE)
    check(len(rows) == 1, "upsert did not duplicate the row")
    check(rows[0]["score"] == "1 - 0", "upsert replaced the payload (score updated)")
    check(rows[0]["status"] == "on_going_h2", "upsert replaced the payload (status updated)")


async def test_put_updates_existing():
    _fresh_db()
    c = JsonLocalClient(db_path=DB)
    await c.post_match(SOURCE, _rec("200", score="0 - 0"))
    ok = await c.put_match(SOURCE, "200", _rec("200", score="2 - 1"))
    check(ok is True, "put_match on existing id returns True")
    rows = await c.get_all_matches(SOURCE)
    check(len(rows) == 1, "put on existing id did not duplicate")
    check(rows[0]["score"] == "2 - 1", "put replaced the payload")


async def test_put_inserts_if_missing():
    _fresh_db()
    c = JsonLocalClient(db_path=DB)
    # put on an id that does not exist yet must INSERT it.
    ok = await c.put_match(SOURCE, "300", _rec("300", score="3 - 3"))
    check(ok is True, "put_match on missing id (insert-if-missing) returns True")
    rows = await c.get_all_matches(SOURCE)
    check(len(rows) == 1, "put-insert created exactly one row")
    check(rows[0]["id"] == "300", "put-insert used the intended id")
    check(rows[0]["score"] == "3 - 3", "put-insert carried the payload")


async def test_put_forces_id_on_insert():
    _fresh_db()
    c = JsonLocalClient(db_path=DB)
    # payload id disagrees with match_id arg -> insert must use match_id, defensively.
    ok = await c.put_match(SOURCE, "400", {"id": "999", "team1": "A", "team2": "B"})
    check(ok is True, "put_match with mismatched id returns True")
    rec = jsondb.get_record(SOURCE, "400", DB)
    check(rec is not None, "record was inserted under match_id '400', not payload id '999'")
    check(jsondb.get_record(SOURCE, "999", DB) is None, "no stray record under payload id '999'")


async def test_delete_removes_existing():
    _fresh_db()
    c = JsonLocalClient(db_path=DB)
    await c.post_match(SOURCE, _rec("500"))
    ok = await c.delete_match(SOURCE, "500")
    check(ok is True, "delete_match on existing id returns True")
    rows = await c.get_all_matches(SOURCE)
    check(len(rows) == 0, "delete removed the row")


async def test_delete_is_idempotent():
    _fresh_db()
    c = JsonLocalClient(db_path=DB)
    await c.post_match(SOURCE, _rec("600"))
    first = await c.delete_match(SOURCE, "600")
    second = await c.delete_match(SOURCE, "600")  # already gone
    check(first is True, "first delete of existing id returns True")
    check(second is True, "second delete of now-absent id ALSO returns True (idempotent)")


async def test_delete_never_existed():
    _fresh_db()
    c = JsonLocalClient(db_path=DB)
    ok = await c.delete_match(SOURCE, "does-not-exist")
    check(ok is True, "delete of an id that never existed returns True (idempotent)")


async def test_get_all_empty():
    _fresh_db()
    c = JsonLocalClient(db_path=DB)
    rows = await c.get_all_matches(SOURCE)
    check(rows == [], "get_all_matches on empty collection returns []")


async def _run():
    tests = [
        test_post_inserts_new,
        test_post_upserts_on_conflict,
        test_put_updates_existing,
        test_put_inserts_if_missing,
        test_put_forces_id_on_insert,
        test_delete_removes_existing,
        test_delete_is_idempotent,
        test_delete_never_existed,
        test_get_all_empty,
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
    print("OK: JsonLocalClient contract holds (upsert / insert-if-missing / idempotent delete)")


if __name__ == "__main__":
    main()
