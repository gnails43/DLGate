from __future__ import annotations

import logging
import re
from typing import Optional

from playwright.async_api import Page

logger = logging.getLogger(__name__)

# Known download gate URL patterns
GATE_PATTERNS = [
    re.compile(r"https?://(?:www\.)?hypeddit\.com/\S+", re.IGNORECASE),
    re.compile(r"https?://(?:www\.)?toneden\.io/\S+", re.IGNORECASE),
    re.compile(r"https?://(?:www\.)?fanlink\.to/\S+", re.IGNORECASE),
    re.compile(r"https?://(?:www\.)?gate\.fm/\S+", re.IGNORECASE),
    re.compile(r"https?://(?:www\.)?distrokid\.com/hyperfollow/\S+", re.IGNORECASE),
    # Link aggregators (may contain free DL links)
    re.compile(r"https?://linktr\.ee/\S+", re.IGNORECASE),
    re.compile(r"https?://(?:www\.)?lnk\.to/\S+", re.IGNORECASE),
    re.compile(r"https?://(?:www\.)?ffm\.to/\S+", re.IGNORECASE),
    re.compile(r"https?://(?:www\.)?orcd\.co/\S+", re.IGNORECASE),
    re.compile(r"https?://(?:www\.)?push\.fm/\S+", re.IGNORECASE),
    re.compile(r"https?://(?:www\.)?smarturl\.it/\S+", re.IGNORECASE),
]


async def detect_gate_url(page: Page, track_url: str) -> Optional[str]:
    """Navigate to a SoundCloud track page and find a download gate URL."""
    logger.info("Detecting gate URL from: %s", track_url)

    await page.goto(track_url, wait_until="domcontentloaded")
    await page.wait_for_timeout(3000)  # Wait for SPA to render

    # 1. Check the track description for gate URLs
    description = await _get_description_text(page)
    if description:
        gate_url = _find_gate_url_in_text(description)
        if gate_url:
            logger.info("Found gate URL in description: %s", gate_url)
            return gate_url

    # 2. Check for "Free Download" or "Buy" links
    gate_url = await _check_download_links(page)
    if gate_url:
        logger.info("Found gate URL in download link: %s", gate_url)
        return gate_url

    # 3. Check all links on the page
    gate_url = await _check_all_links(page)
    if gate_url:
        logger.info("Found gate URL in page links: %s", gate_url)
        return gate_url

    logger.info("No gate URL found for: %s", track_url)
    return None


async def _get_description_text(page: Page) -> str:
    """Extract the track description text."""
    selectors = [
        ".truncatedAudioInfo__content",
        ".soundActions .sc-text",
        "[class*='description']",
        ".sc-truncate",
    ]
    for sel in selectors:
        el = await page.query_selector(sel)
        if el:
            text = await el.inner_text()
            if text.strip():
                return text

    # Also get the raw HTML to find href attributes
    for sel in selectors:
        el = await page.query_selector(sel)
        if el:
            html = await el.inner_html()
            if html.strip():
                return html

    return ""


async def _check_download_links(page: Page) -> Optional[str]:
    """Check buy/download buttons for gate URLs."""
    selectors = [
        "a[class*='buyButton']",
        "a[class*='download']",
        "a:has-text('Free Download')",
        "a:has-text('Download')",
        "a:has-text('Buy')",
    ]
    for sel in selectors:
        elements = await page.query_selector_all(sel)
        for el in elements:
            href = await el.get_attribute("href")
            if href and _is_gate_url(href):
                return href
    return None


async def _check_all_links(page: Page) -> Optional[str]:
    """Scan all links on the page for gate URLs."""
    links = await page.query_selector_all("a[href]")
    for link in links:
        href = await link.get_attribute("href")
        if href and _is_gate_url(href):
            return href
    return None


def _find_gate_url_in_text(text: str) -> Optional[str]:
    """Find a gate URL in text content."""
    for pattern in GATE_PATTERNS:
        match = pattern.search(text)
        if match:
            return match.group(0).rstrip(".,;:!?)")
    return None


def _is_gate_url(url: str) -> bool:
    """Check if a URL matches a known gate pattern."""
    return any(pattern.match(url) for pattern in GATE_PATTERNS)
