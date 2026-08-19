from __future__ import annotations

from typing import TYPE_CHECKING

from horus.providers.base import BaseProvider

if TYPE_CHECKING:
    import httpx

    from horus.json_sync.settings import SyncSettings


def build_providers(settings: SyncSettings, client: httpx.AsyncClient) -> list[BaseProvider]:
    from horus.providers.eightxbet import EightXBetProvider
    from horus.providers.onexbet import OneXBetProvider

    return [
        OneXBetProvider(client=client, settings=settings),
        EightXBetProvider(client=client, settings=settings),
    ]
