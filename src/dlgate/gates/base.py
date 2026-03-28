from __future__ import annotations

from abc import ABC, abstractmethod

from playwright.async_api import Page

from dlgate.config import Config
from dlgate.models import GateResult, Track


class BaseGateHandler(ABC):
    @abstractmethod
    async def can_handle(self, url: str) -> bool:
        """Check if this handler can process the given gate URL."""
        ...

    @abstractmethod
    async def process(self, page: Page, track: Track, config: Config) -> GateResult:
        """Process the gate and return the result."""
        ...
