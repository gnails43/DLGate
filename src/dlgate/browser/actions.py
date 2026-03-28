from __future__ import annotations

import asyncio
import logging
import random
from pathlib import Path

from playwright.async_api import Download, Page

logger = logging.getLogger(__name__)


async def random_delay(min_ms: int = 500, max_ms: int = 2000) -> None:
    delay = random.randint(min_ms, max_ms) / 1000.0
    await asyncio.sleep(delay)


async def safe_click(page: Page, selector: str, timeout: int = 10000) -> bool:
    try:
        await page.wait_for_selector(selector, state="visible", timeout=timeout)
        await page.click(selector)
        return True
    except Exception as e:
        logger.warning("Failed to click '%s': %s", selector, e)
        return False


async def safe_fill(page: Page, selector: str, value: str, timeout: int = 10000) -> bool:
    try:
        await page.wait_for_selector(selector, state="visible", timeout=timeout)
        await page.fill(selector, value)
        return True
    except Exception as e:
        logger.warning("Failed to fill '%s': %s", selector, e)
        return False


async def wait_for_new_page(context, action_coro, timeout: int = 60000) -> Page | None:
    """Execute an action that opens a new page/popup and return that page."""
    future: asyncio.Future[Page] = asyncio.get_event_loop().create_future()

    def on_page(page: Page) -> None:
        if not future.done():
            future.set_result(page)

    context.on("page", on_page)
    try:
        await action_coro
        try:
            new_page = await asyncio.wait_for(future, timeout=timeout / 1000)
            await new_page.wait_for_load_state("domcontentloaded")
            return new_page
        except asyncio.TimeoutError:
            logger.warning("No new page opened within timeout")
            return None
    finally:
        context.remove_listener("page", on_page)


async def wait_for_download(page: Page, action_coro, output_dir: str, timeout: int = 30000) -> str | None:
    """Execute an action that triggers a download and save the file."""
    try:
        async with page.expect_download(timeout=timeout) as download_info:
            await action_coro
        download: Download = await download_info.value

        suggested = download.suggested_filename
        save_path = str(Path(output_dir) / suggested)
        await download.save_as(save_path)
        logger.info("Downloaded: %s", save_path)
        return save_path
    except Exception as e:
        logger.error("Download failed: %s", e)
        return None


async def take_screenshot(page: Page, name: str, output_dir: str = "./debug_screenshots") -> str:
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    path = str(Path(output_dir) / f"{name}.png")
    await page.screenshot(path=path, full_page=True)
    logger.info("Screenshot saved: %s", path)
    return path
