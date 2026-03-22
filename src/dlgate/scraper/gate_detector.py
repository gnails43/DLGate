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

    # 1. Check the buy/cart button (most reliable on SoundCloud)
    gate_url = await _check_buy_button(page)
    if gate_url:
        logger.info("Found gate URL in buy button: %s", gate_url)
        return gate_url

    # 2. Check the track description for gate URLs
    description = await _get_description_text(page)
    if description:
        logger.debug("Description text: %s", description[:200])
        gate_url = _find_gate_url_in_text(description)
        if gate_url:
            logger.info("Found gate URL in description: %s", gate_url)
            return gate_url

    # 3. Collect all links on the page via JS and check
    gate_url = await _check_all_links_js(page)
    if gate_url:
        logger.info("Found gate URL in page links: %s", gate_url)
        return gate_url

    logger.info("No gate URL found for: %s", track_url)
    return None


async def _check_buy_button(page: Page) -> Optional[str]:
    """Check the SoundCloud buy/cart button for a gate URL."""
    # The cart/buy button on SoundCloud links to external sites
    # Try multiple selectors for the buy link
    href = await page.evaluate("""() => {
        // Buy button selectors (cart icon)
        const selectors = [
            'a.sc-buylink',
            'a[class*="buyButton"]',
            'a[class*="BuyButton"]',
            'a.sc-button-buy',
            'a[title*="Buy"]',
            'a[title*="buy"]',
            'a[aria-label*="Buy"]',
        ];
        for (const sel of selectors) {
            const el = document.querySelector(sel);
            if (el && el.href) return el.href;
        }

        // Also check for link in the "more" actions or any cart-like button
        const allLinks = document.querySelectorAll('a[href]');
        for (const link of allLinks) {
            const classes = link.className || '';
            const text = link.textContent.trim().toLowerCase();
            if (
                classes.includes('buy') ||
                classes.includes('Buy') ||
                text === 'buy' ||
                text === 'free download' ||
                text.includes('free download')
            ) {
                return link.href;
            }
        }
        return null;
    }""")

    if href and _is_gate_url(href):
        return href

    # Even if not a known gate URL, if it's an external link from the buy button
    # it might redirect to a gate. Return it for further processing.
    if href and not href.startswith("https://soundcloud.com"):
        logger.info("Buy button links to external URL: %s", href)
        return href

    return None


async def _get_description_text(page: Page) -> str:
    """Extract the track description text and link hrefs via JavaScript."""
    result = await page.evaluate("""() => {
        const selectors = [
            '.truncatedAudioInfo__content',
            '[class*="Description"]',
            '[class*="description"]',
            '.sc-text',
        ];
        for (const sel of selectors) {
            const el = document.querySelector(sel);
            if (el) {
                // Get plain text
                const text = el.innerText || '';
                // Also extract href values from any anchor tags
                const hrefs = Array.from(el.querySelectorAll('a[href]'))
                    .map(a => a.href)
                    .join(' ');
                const combined = (text + ' ' + hrefs).trim();
                if (combined) return combined;
            }
        }
        return '';
    }""")
    return result


async def _check_all_links_js(page: Page) -> Optional[str]:
    """Scan all links on the page for gate URLs using JavaScript."""
    links = await page.evaluate("""() => {
        const anchors = document.querySelectorAll('a[href]');
        const hrefs = [];
        for (const a of anchors) {
            if (a.href && !a.href.startsWith('https://soundcloud.com')) {
                hrefs.push(a.href);
            }
        }
        return hrefs;
    }""")

    for href in links:
        if _is_gate_url(href):
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
