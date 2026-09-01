from __future__ import annotations

from abc import ABC, abstractmethod

from livescore.models import MatchData


class BaseProvider(ABC):
    source_name: str = ""

    @abstractmethod
    async def fetch_live_matches(self) -> list[MatchData]: ...

    @abstractmethod
    async def fetch_match_detail(self, match_id: str) -> MatchData | None: ...

    async def close(self) -> None: ...
