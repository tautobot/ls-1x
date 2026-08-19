"""
Regression suite for the file-backed JSON store (horus/jsondb.py + horus/json_server.py).

Runs standalone (no pytest required), matching this repo's plain-script convention:

    poetry run python tests/test_jsondb.py

Exits non-zero if any assertion fails. All tests use an isolated temp DB and never
touch the repo's real db.json. Covers the JsonServerProcessor public API contract,
filter semantics, type coercion, multi-process concurrency, and corrupt-file self-heal.

Authored by pyrx-qa as the durable regression suite for the remote->local store migration.
"""
import os
import sys
import json
import glob
import tempfile
import subprocess
import textwrap
import collections

# --- Isolate: point the store at a temp file BEFORE importing horus modules. ---
_TMPDIR = tempfile.mkdtemp(prefix="qa_jsondb_")
DB = os.path.join(_TMPDIR, "db.json")
os.environ["JSON_DB_PATH"] = DB

from horus import jsondb  # noqa: E402
jsondb.JSON_DB_PATH = DB  # what JsonServerProcessor's un-pathed calls default to
from horus.json_server import (  # noqa: E402
    JsonServerProcessor,
    parse_filters,
    make_predicate,
)

_PASS = 0
_FAIL = 0
_FAILURES = []


def check(name, cond, detail=""):
    global _PASS, _FAIL
    if cond:
        _PASS += 1
    else:
        _FAIL += 1
        _FAILURES.append(f"{name} :: {detail}")
        print(f"  FAIL: {name} :: {detail}")


def reset_db(state):
    with open(DB, "w") as f:
        json.dump(state, f)


def write_raw(s):
    with open(DB, "w") as f:
        f.write(s)


def P(params, source="1x"):
    return JsonServerProcessor(source=source, params=params)


SEED = {
    "1x": [
        {"id": "1", "risk": "-1", "status": "ended", "half": 1, "time_match": "10:00"},
        {"id": "2", "risk": "-2", "status": "on_going_h1", "half": 1, "time_match": "11:00"},
        {"id": "3", "risk": "0", "status": "ended", "half": 2, "time_match": "12:00"},
        {"id": "4", "risk": "-1", "status": "ex_time_h1", "half": 1, "time_match": "13:00"},
        {"id": "5", "risk": "3"},  # no status, no half -> excluded by any status filter
    ],
    "8x": [],
}


def test_filter_semantics():
    check("parse None -> {}", parse_filters(None) == {})
    check("parse '' -> {}", parse_filters("") == {})
    check("parse leading ?", parse_filters("?risk=0&risk=-1") == {"risk": ["0", "-1"]})
    check("parse AND across fields",
          parse_filters("?risk=-1&status=ended") == {"risk": ["-1"], "status": ["ended"]})
    check("parse malformed segment skipped",
          parse_filters("?risk=0&garbage&status=ended") == {"risk": ["0"], "status": ["ended"]})
    check("parse value containing =", parse_filters("?url=a=b") == {"url": ["a=b"]})
    check("parse trailing & ignored", parse_filters("?risk=0&") == {"risk": ["0"]})

    pred = make_predicate("?risk=-1&risk=-2")
    check("OR within field matches -1", pred({"risk": "-1"}))
    check("OR within field matches -2", pred({"risk": "-2"}))
    check("OR within field excludes 0", not pred({"risk": "0"}))
    check("int -1 coerced to '-1' matches", pred({"risk": -1}))
    check("missing field excluded", not pred({"status": "ended"}))
    check("empty filter matches all", make_predicate("")({"anything": 1}))
    check("substring does NOT match ('1' vs '10')", not make_predicate("?risk=1")({"risk": "10"}))
    check("whitespace in value is significant", not make_predicate("?risk= -1")({"risk": "-1"}))

    pred2 = make_predicate("?risk=-1&risk=-2&status=on_going_h1&status=ex_time_h1")
    check("AND both satisfied", pred2({"risk": "-1", "status": "ex_time_h1"}))
    check("AND fails on wrong status", not pred2({"risk": "-1", "status": "ended"}))
    check("AND fails on wrong risk", not pred2({"risk": "0", "status": "ex_time_h1"}))


def test_get_all_matches():
    reset_db({"1x": [], "8x": []})
    r = P({"skip_convert_data_types": True}).get_all_matches()
    check("empty get_all", r["success"] and r["data"] == [], str(r))

    reset_db(SEED)
    r = P({"skip_convert_data_types": True}).get_all_matches()
    check("get_all returns all 5", len(r["data"]) == 5, str(len(r["data"])))
    r = P({"skip_convert_data_types": True}).get_all_matches("?risk=-1&risk=-2")
    check("risk OR -> ids 1,2,4", sorted(x["id"] for x in r["data"]) == ["1", "2", "4"],
          str([x["id"] for x in r["data"]]))
    r = P({"skip_convert_data_types": True}).get_all_matches(
        "?risk=-1&risk=-2&status=on_going_h1&status=ex_time_h1")
    check("risk+status AND -> ids 2,4", sorted(x["id"] for x in r["data"]) == ["2", "4"],
          str([x["id"] for x in r["data"]]))
    r = P({"skip_convert_data_types": True}).get_all_matches("?status=ended")
    check("status=ended -> ids 1,3 (id5 has no status, excluded)",
          sorted(x["id"] for x in r["data"]) == ["1", "3"], str([x["id"] for x in r["data"]]))


def test_convert_data_types():
    reset_db({"1x": [{"id": "7", "risk": "-1", "prediction": "3", "coef": "1.5", "name": "abc",
                      "scores": ["1", "2"]}], "8x": []})
    raw = P({"skip_convert_data_types": True}).get_all_matches()["data"][0]
    check("skip=True keeps risk str", raw["risk"] == "-1" and isinstance(raw["risk"], str))

    conv = P({"skip_convert_data_types": False}).get_all_matches()["data"][0]
    check("skip=False '3' -> int", conv["prediction"] == 3 and isinstance(conv["prediction"], int))
    check("skip=False '1.5' -> float", conv["coef"] == 1.5 and isinstance(conv["coef"], float))
    check("skip=False negative '-1' STAYS str", conv["risk"] == "-1" and isinstance(conv["risk"], str))
    check("skip=False 'abc' stays str", conv["name"] == "abc")
    check("skip=False list value preserved", conv["scores"] == ["1", "2"])
    check("default (no flag) converts", P({}).get_all_matches()["data"][0]["prediction"] == 3)


def test_get_match():
    reset_db(SEED)
    r = P({"id": "2", "skip_convert_data_types": True}).get_match()
    check("get_match found", r["success"] and r["data"]["id"] == "2", str(r))
    r = P({"id": 2, "skip_convert_data_types": True}).get_match()
    check("get_match int id coerced", r["success"] and r["data"]["id"] == "2", str(r))
    r = P({"id": "999", "skip_convert_data_types": True}).get_match()
    check("get_match missing -> success False, data None", r == {"success": False, "data": None}, str(r))
    r = P({"skip_convert_data_types": True}).get_match()
    check("get_match no id -> not found", r == {"success": False, "data": None}, str(r))


def test_post_match():
    reset_db({"1x": [], "8x": []})
    resp = P({"risk": "-1", "status": "ended"}).post_match()
    check("post 201", resp.status_code == 201, str(resp.status_code))
    check("post auto id '1'", resp.json()["id"] == "1", str(resp.json()))
    check("post auto id '2'", P({"risk": "0"}).post_match().json()["id"] == "2")

    resp = P({"id": "100", "risk": "1"}).post_match()
    check("post provided id honored", resp.json()["id"] == "100")
    check("post auto after 100 -> '101'", P({"risk": "2"}).post_match().json()["id"] == "101")

    resp = P({"id": "100", "risk": "9"}).post_match()
    check("post duplicate id -> 409", resp.status_code == 409, str(resp.status_code))
    check("post 409 has error body", "error" in resp.json())

    resp = P({"id": 500, "risk": "1"}).post_match()
    check("post int id stored as str", resp.json()["id"] == "500" and isinstance(resp.json()["id"], str))
    check("post int-vs-str duplicate -> 409", P({"id": 500, "risk": "1"}).post_match().status_code == 409)
    check("post empty-string id -> auto-increment", P({"id": "", "risk": "1"}).post_match().json()["id"] != "")

    reset_db({"1x": [], "8x": []})
    check("post non-numeric id honored", P({"id": "abc", "risk": "1"}).post_match().json()["id"] == "abc")
    check("post auto id ignores non-int ids -> '1'", P({"risk": "2"}).post_match().json()["id"] == "1")


def test_put_match():
    reset_db(SEED)
    resp = P({"id": "1", "risk": "9", "newfield": "x"}).put_match()
    check("put 200", resp.status_code == 200, str(resp.status_code))
    check("put keeps id", resp.json()["id"] == "1")
    check("put full-replace drops old fields", "status" not in resp.json(), str(resp.json()))
    got = P({"id": "1", "skip_convert_data_types": True}).get_match()["data"]
    check("put persisted", got.get("risk") == "9" and "status" not in got, str(got))
    check("put nonexistent -> 404", P({"id": "9999", "risk": "1"}).put_match().status_code == 404)
    check("put no id -> 404", P({"risk": "1"}).put_match().status_code == 404)


def test_delete_match():
    reset_db(SEED)
    resp = P({"id": "3"}).delete_match()
    check("delete 200", resp.status_code == 200, str(resp.status_code))
    check("delete .json() -> {}", resp.json() == {})
    check("deleted record is gone",
          P({"id": "3", "skip_convert_data_types": True}).get_match() == {"success": False, "data": None})
    check("delete already-deleted -> 404", P({"id": "3"}).delete_match().status_code == 404)
    check("delete nonexistent -> 404", P({"id": "9999"}).delete_match().status_code == 404)
    check("delete no id -> 404", P({}).delete_match().status_code == 404)


def test_round_trip():
    reset_db({"1x": [], "8x": []})
    nid = P({"risk": "-1", "team1": "A", "team2": "B"}).post_match().json()["id"]
    got = P({"id": nid, "skip_convert_data_types": True}).get_match()
    check("roundtrip get-after-post", got["success"] and got["data"]["team1"] == "A", str(got))
    P({"id": nid, "risk": "-2", "team1": "C"}).put_match()
    got = P({"id": nid, "skip_convert_data_types": True}).get_match()
    check("roundtrip get-after-put", got["data"]["risk"] == "-2" and got["data"]["team1"] == "C")
    P({"id": nid}).delete_match()
    check("roundtrip get-after-delete gone",
          not P({"id": nid, "skip_convert_data_types": True}).get_match()["success"])


def test_adversarial_inputs():
    reset_db({"1x": [], "8x": []})
    emoji = "Đội B\xf3ng \U0001F1FB\U0001F1F3"
    nid = P({"team1": emoji, "risk": "-1"}).post_match().json()["id"]
    check("unicode/emoji round-trips",
          P({"id": nid, "skip_convert_data_types": True}).get_match()["data"]["team1"] == emoji)

    xss = "<script>alert(1)</script>'; DROP TABLE x;--"
    nid = P({"note": xss, "risk": "0"}).post_match().json()["id"]
    check("XSS/SQLi stored verbatim (no interpretation)",
          P({"id": nid, "skip_convert_data_types": True}).get_match()["data"]["note"] == xss)

    big = "x" * 200
    check("200-char string ok", len(P({"note": big, "risk": "0"}).post_match().json()["note"]) == 200)


def test_unknown_and_new_collection():
    reset_db({"1x": [], "8x": []})
    r = JsonServerProcessor(source="nonexistent", params={"skip_convert_data_types": True}).get_all_matches()
    check("unknown source -> success True, empty", r["success"] and r["data"] == [], str(r))
    resp = JsonServerProcessor(source="newcol", params={"risk": "1"}).post_match()
    check("post to new collection auto-creates", resp.status_code == 201 and resp.json()["id"] == "1", str(resp.json()))


def test_self_heal():
    for desc, raw in [
        ("truncated JSON", '{"1x": [{"id": "1", "risk"'),
        ("garbage bytes", "\x00 not json !!!"),
        ("root is a list", "[1,2,3]"),
        ("root is a string", '"hello"'),
        ("empty file", ""),
    ]:
        write_raw(raw)
        r = P({"skip_convert_data_types": True}).get_all_matches()
        check(f"self-heal: {desc}", r["success"] and r["data"] == [], str(r))

    os.remove(DB)
    r = P({"skip_convert_data_types": True}).get_all_matches()
    check("missing file auto-creates", r["success"] and r["data"] == [] and os.path.exists(DB), str(r))

    write_raw("CORRUPT")
    resp = P({"risk": "-1"}).post_match()
    check("post after corruption heals + succeeds", resp.status_code == 201 and resp.json()["id"] == "1")

    # A valid dict missing the '1x' key is NOT corrupt: must preserve sibling collections.
    write_raw('{"8x": [{"id": "5", "risk": "1"}]}')
    P({"risk": "-1"}).post_match()  # writes to 1x
    db = json.load(open(DB))
    check("partial dict preserves sibling collection",
          len(db.get("8x", [])) == 1 and len(db.get("1x", [])) == 1, str(db))

    # No stray temp files left behind by atomic writes.
    write_raw('{"1x": [], "8x": []}')
    for _ in range(5):
        P({"risk": "0"}).post_match()
    strays = glob.glob(os.path.join(_TMPDIR, ".db_*.tmp"))
    check("no stray temp files after atomic writes", strays == [], str(strays))


def test_concurrency():
    """5 real OS processes x 40 auto-increment inserts must yield 200 contiguous unique ids."""
    conc_dir = tempfile.mkdtemp(prefix="qa_conc_")
    conc_db = os.path.join(conc_dir, "db.json")
    with open(conc_db, "w") as f:
        json.dump({"1x": [], "8x": []}, f)

    worker_src = textwrap.dedent("""
        import os, sys
        os.environ['JSON_DB_PATH'] = sys.argv[1]
        from horus import jsondb
        jsondb.JSON_DB_PATH = sys.argv[1]
        from horus.json_server import JsonServerProcessor
        w = int(sys.argv[2]); n = int(sys.argv[3])
        for i in range(n):
            JsonServerProcessor(source='1x', params={'risk': str(w), 'w': w}).post_match()
    """)
    worker_path = os.path.join(conc_dir, "worker.py")
    with open(worker_path, "w") as f:
        f.write(worker_src)

    nproc, nins = 5, 40
    expected = nproc * nins
    procs = [subprocess.Popen([sys.executable, worker_path, conc_db, str(w), str(nins)],
                              env=dict(os.environ)) for w in range(nproc)]
    codes = [p.wait() for p in procs]
    check("all concurrency workers exit 0", all(c == 0 for c in codes), str(codes))

    recs = json.load(open(conc_db))["1x"]
    ids = [r["id"] for r in recs]
    check("no lost updates (200 records)", len(recs) == expected, str(len(recs)))
    check("all ids unique", len(set(ids)) == len(ids),
          str([i for i, c in collections.Counter(ids).items() if c > 1][:5]))
    check("ids contiguous 1..200", sorted(int(i) for i in ids) == list(range(1, expected + 1)))
    per = collections.Counter(r["w"] for r in recs)
    check("each worker's 40 writes survived", all(per[w] == nins for w in range(nproc)), str(dict(per)))


def main():
    tests = [
        test_filter_semantics, test_get_all_matches, test_convert_data_types,
        test_get_match, test_post_match, test_put_match, test_delete_match,
        test_round_trip, test_adversarial_inputs, test_unknown_and_new_collection,
        test_self_heal, test_concurrency,
    ]
    for t in tests:
        print(f"--- {t.__name__} ---")
        t()
    print()
    print(f"RESULTS: {_PASS} passed, {_FAIL} failed")
    if _FAILURES:
        print("FAILURES:")
        for f in _FAILURES:
            print("  -", f)
    return 1 if _FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
