"""Top-level entrypoint for the live-match sync service.

Runs the ported ``JsonSyncService`` which discovers live football matches from the
1xbet/8xbet providers, converts them to the autobet JSON shape, and writes them
directly into ls-1x's in-process file-backed store (``horus/jsondb.py``). The service
handles both discovery of new matches AND deletion of ended ones internally, so it
supersedes the legacy ``fetch_matches.py`` + ``delete_ended_matches.py`` pair.

    poetry run python sync_matches.py

Config comes from ``horus/json_sync/settings.py`` (SYNC_* env vars, with sane
defaults) plus the bare ``JSON_SYNC_SOURCE`` env (default "1x").
"""
import asyncio

from horus.json_sync.runner import main

if __name__ == "__main__":
    asyncio.run(main())
