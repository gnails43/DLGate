from __future__ import annotations

import glob
import logging
import os
from pathlib import Path
from typing import Optional

from playwright.async_api import Browser, BrowserContext, Page, async_playwright

from dlgate.config import BrowserConfig

logger = logging.getLogger(__name__)


class BrowserSession:
    """Manages a persistent Playwright browser context.

    Uses a persistent user data directory so cookies/logins survive across runs.
    """

    def __init__(self, config: BrowserConfig) -> None:
        self._config = config
        self._playwright = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None

    async def __aenter__(self) -> BrowserSession:
        await self.start()
        return self

    async def __aexit__(self, *exc) -> None:
        await self.close()

    @staticmethod
    def _clean_lock_files(profile_dir: str) -> None:
        """Remove stale browser lock files that prevent startup."""
        lock_patterns = ["SingletonLock", "SingletonSocket", "SingletonCookie"]
        for pattern in lock_patterns:
            for lock_file in glob.glob(os.path.join(profile_dir, pattern)):
                try:
                    os.remove(lock_file)
                    logger.debug("Removed stale lock file: %s", lock_file)
                except OSError:
                    pass

    async def start(self) -> None:
        profile_dir = str(Path(self._config.profile_dir).resolve())
        Path(profile_dir).mkdir(parents=True, exist_ok=True)
        self._clean_lock_files(profile_dir)

        self._playwright = await async_playwright().start()

        # Use local Chrome if channel is set, otherwise use Playwright's Chromium
        launch_kwargs = {
            "user_data_dir": profile_dir,
            "headless": self._config.headless,
            "slow_mo": self._config.slow_mo,
            "viewport": {"width": 1280, "height": 900},
            "accept_downloads": True,
            "args": [
                "--disable-blink-features=AutomationControlled",
            ],
            "ignore_default_args": ["--enable-automation"],
        }
        if self._config.channel:
            launch_kwargs["channel"] = self._config.channel

        self._context = await self._playwright.chromium.launch_persistent_context(
            **launch_kwargs,
        )
        # Use existing page or create one
        if self._context.pages:
            self._page = self._context.pages[0]
        else:
            self._page = await self._context.new_page()

        self._page.set_default_timeout(self._config.timeout)
        logger.info("Browser session started (profile: %s)", profile_dir)

    async def close(self) -> None:
        if self._context:
            try:
                await self._context.close()
            except Exception:
                pass  # Browser may already be closed by user
            self._context = None
        if self._playwright:
            try:
                await self._playwright.stop()
            except Exception:
                pass
            self._playwright = None
        logger.info("Browser session closed")

    @property
    def page(self) -> Page:
        if self._page is None:
            raise RuntimeError("Browser session not started")
        return self._page

    @property
    def context(self) -> BrowserContext:
        if self._context is None:
            raise RuntimeError("Browser session not started")
        return self._context

    async def new_page(self) -> Page:
        return await self.context.new_page()
