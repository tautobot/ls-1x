from __future__ import annotations

import asyncio
import os

import httpx

from horus.json_sync.local_client import JsonLocalClient
from horus.json_sync.service import JsonSyncService
from horus.json_sync.settings import configure_logging, settings
from horus.providers import build_providers

# The store collection the sync service writes into. The service stores ALL
# providers' matches into this single collection (as agent.livescore did).
# Read from the bare JSON_SYNC_SOURCE env (not SYNC_-prefixed) per the runtime
# contract; defaults to "1x".
JSON_SYNC_SOURCE = os.environ.get("JSON_SYNC_SOURCE", "1x")


async def main() -> None:
    """Composition root for the live-match sync service.

    Builds the bookmaker providers (which still fetch over real HTTP), the
    in-process JSON store client (writes into ``horus.jsondb``), and the sync
    service, then runs the finder + updater loops forever. Only the *providers*
    talk to the network now — the store leg is fully in-process.
    """
    configure_logging()

    http_client = httpx.AsyncClient(
        timeout=httpx.Timeout(10.0),
        limits=httpx.Limits(max_connections=20),
    )
    providers = build_providers(settings, http_client)
    # db_path=None -> uses horus.jsondb's JSON_DB_PATH default (<repo>/db.json)
    json_client = JsonLocalClient()

    service = JsonSyncService(
        providers=providers,
        json_client=json_client,
        source=JSON_SYNC_SOURCE,
        finder_interval=settings.match_finder_interval,
        updater_interval=settings.match_updater_interval,
    )

    try:
        await service.run()
    finally:
        await http_client.aclose()


if __name__ == "__main__":
    asyncio.run(main())
