"""Run the live-match sync *inside* the Streamlit process.

Streamlit Community Cloud runs ONLY ``streamlit run app.py`` — there is no way to
launch ``sync_matches.py`` as a separate systemd service alongside it, so on Cloud
nothing would ever populate ``db.json`` and the match table stays empty.

``ensure_sync_running()`` starts the same finder+updater loops
(``livescore.json_sync.runner.main``) in a daemon background thread, exactly once per
server process. Call it from the app on every rerun — it is idempotent and
process-global, so repeated calls (and multiple viewer sessions) all share the one
sync thread.

Set ``EMBEDDED_SYNC=0`` to disable — e.g. a VM/host deployment that instead runs
``sync_matches.py`` as a standalone systemd service (see ``systemds/1xbet.sync.service``).
"""
from __future__ import annotations

import asyncio
import os
import threading
import time

import structlog

# Import the whole sync chain EAGERLY, in the main thread, at module import time
# (streamlit_app.py imports this module during its first run). If these imports
# were done lazily inside the background thread, they could race with Streamlit's
# rerun re-imports of overlapping `livescore.*` modules and raise
# `KeyError: 'livescore.json_server'` mid-import. Loading everything once up front on
# the main thread makes every later `from livescore... import` a safe dict lookup.
from livescore.json_sync.runner import main as _sync_main  # noqa: E402

_log = structlog.get_logger(service="json_sync.embedded")
_started = False
_guard = threading.Lock()


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() not in ("", "0", "false", "no", "off")


def embedded_sync_enabled() -> bool:
    # Default ON so the app "just works" on Streamlit Cloud with zero config.
    return _truthy(os.environ.get("EMBEDDED_SYNC", "1"))


def ensure_sync_running() -> bool:
    """Idempotently start the in-process sync thread. Returns True if the sync is
    (now or already) running in this process, False if disabled via EMBEDDED_SYNC.
    """
    global _started
    if not embedded_sync_enabled():
        return False
    with _guard:
        if _started:
            return True
        _started = True
        thread = threading.Thread(
            target=_supervise, name="json_sync_embedded", daemon=True
        )
        thread.start()
    return True


def _supervise() -> None:
    """Run the async sync forever, restarting it if it ever exits or crashes.

    Each ``asyncio.run`` owns a fresh event loop in this thread. A crash (e.g. a
    transient network wobble that escapes the loops' own try/except) is logged and
    the whole sync is relaunched after a short backoff — the same resilience the
    systemd ``Restart=always`` unit gives the standalone service.
    """
    while True:
        try:
            asyncio.run(_sync_main())
            _log.warning("embedded_sync_exited_restarting")
        except Exception:
            _log.exception("embedded_sync_crashed_restarting")
        time.sleep(5)
