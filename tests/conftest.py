"""Pytest-only test isolation for the file-backed JSON store.

Each ``test_*.py`` module here follows the repo's plain-script convention and
pins the store at its OWN temp file at import time::

    _TMPDIR = tempfile.mkdtemp(...)
    DB = os.path.join(_TMPDIR, "db.json")
    os.environ["JSON_DB_PATH"] = DB
    from livescore import jsondb
    jsondb.JSON_DB_PATH = DB

Run one file at a time (``python tests/test_jsondb.py``) that is correct. But
pytest imports ALL of them into a single process, and ``jsondb.JSON_DB_PATH`` is
a shared mutable module global: the last module imported wins and silently
clobbers the others. ``test_jsondb.py``'s ``JsonServerProcessor`` calls resolve
the path from that global (no explicit ``db_path``), so its ``reset_db()`` writes
land in one file while its reads come from another module's empty temp DB —
surfacing as ``IndexError: list index out of range``.

This autouse fixture re-pins the global to the *currently running* module's own
``DB`` before every test, so reads and writes always target the same file
regardless of collection/import order. It is a no-op for the standalone script
runners (conftest is only loaded under pytest), preserving the
"runs standalone, no pytest required" contract.
"""
import os

import pytest

from livescore import jsondb


@pytest.fixture(autouse=True)
def _pin_json_db_path(request):
    db = getattr(request.module, "DB", None)
    if db is not None:
        os.environ["JSON_DB_PATH"] = db
        jsondb.JSON_DB_PATH = db
    yield
