"""Detect and resolve link aggregator pages (Linktree, Linkfire, etc.)

These pages list multiple platform links. We look for free download
platforms (Hypeddit, etc.) and return that URL for gate processing.
"""
from __future__ import annotations

import logging
import re
from typing import Optional

from playwright.async_api import Page

logger = logging.getLogger(__name__)

# Domains that host link aggregator pages
AGGREGATOR_DOMAINS = [
    "linktr.ee",
    "linktree.com",
    "linkfire.com",
    "lnk.to",
    "fanlink.to",
    "toneden.io",
    "ffm.to",
    "orcd.co",
    "distrokid.com/hyperfollow",
    "push.fm",
    "smarturl.it",
    "bio.link",
    "beacons.ai",
]

# Gate/free download platforms we can process (in priority order)
FREE_DL_PLATFORMS = [
    re.compile(r"https?://(?:www\.)?hypeddit\.com/\S+", re.IGNORECASE),
    re.compile(r"https?://(?:www\.)?gate\.fm/\S+", re.IGNORECASE),
]

# Platforms we cannot process (paid stores, streaming only)
UNSUPPORTED_PLATFORMS = [
    "beatport.com",
    "traxsource.com",
    "juno.co.uk",
    "junodownload.com",
    "bandcamp.com",
    "itunes.apple.com",
    "music.apple.com",
    "open.spotify.com",
    "youtube.com",
    "youtu.be",
    "music.youtube.com",
    "deezer.com",
    "tidal.com",
    "amazon.com/music",
    "music.amazon.com",
]


def is_aggregator_url(url: str) -> bool:
    """Check if a URL is a known link aggregator page."""
    return any(domain in url for domain in AGGREGATOR_DOMAINS)


def is_unsupported_platform(url: str) -> bool:
    """Check if a URL is a platform we cannot process (Beatport, etc.)."""
    return any(domain in url for domain in UNSUPPORTED_PLATFORMS)


def is_free_dl_url(url: str) -> Optional[str]:
    """Check if a URL matches a free download gate platform. Returns the URL if matched."""
    for pattern in FREE_DL_PLATFORMS:
        if pattern.search(url):
            return url
    return None


async def resolve_aggregator(page: Page, url: str) -> Optional[str]:
    """Visit a link aggregator page and find a free download gate URL.

    Returns the gate URL (e.g. Hypeddit) if found, None otherwise.
    """
    logger.info("Checking link aggregator: %s", url)

    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=15000)
        await page.wait_for_timeout(3000)
    except Exception as e:
        logger.warning("Failed to load aggregator page: %s", e)
        return None

    # Collect all links on the page
    links = await page.evaluate("""() => {
        const anchors = document.querySelectorAll('a[href]');
        return Array.from(anchors).map(a => ({
            href: a.href,
            text: a.textContent.trim().substring(0, 100),
        }));
    }""")

    logger.debug("Found %d links on aggregator page", len(links))

    # Look for free download gate links (priority order)
    for link in links:
        href = link.get("href", "")
        gate_url = is_free_dl_url(href)
        if gate_url:
            logger.info("Found free download gate: %s", gate_url)
            return gate_url

    # No free download link found
    logger.info("No free download gate found on aggregator page")
    return None
