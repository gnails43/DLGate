from __future__ import annotations

import logging

from playwright.async_api import Page

logger = logging.getLogger(__name__)


async def get_track_title_artist(page: Page) -> tuple[str, str]:
    """Extract title and artist from a SoundCloud track page."""
    title = ""
    artist = ""

    title_selectors = [
        ".soundTitle__title span",
        ".listenDetails__trackTitle span",
        "h1[itemprop='name']",
    ]
    for sel in title_selectors:
        el = await page.query_selector(sel)
        if el:
            title = (await el.inner_text()).strip()
            if title:
                break

    artist_selectors = [
        ".soundTitle__username",
        ".listenDetails__artist",
        "a[class*='userBadge__username']",
    ]
    for sel in artist_selectors:
        el = await page.query_selector(sel)
        if el:
            artist = (await el.inner_text()).strip()
            if artist:
                break

    if not title:
        title = await page.title()

    return title, artist
