"""Scan SoundCloud feed for tracks with free download gate links."""
import asyncio
import json
import logging
import re
import sys

from dlgate.browser.session import BrowserSession
from dlgate.config import Config

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# Known gate domains
GATE_DOMAINS = [
    "hypeddit.com", "toneden.io", "fanlink.to", "gate.fm",
    "hive.co", "boost.link", "distrokid.com/hyperfollow",
]

# Patterns that suggest free download
FREE_DL_PATTERNS = re.compile(
    r"free\s*(download|dl|d/l)|download\s*gate|dl\s*gate|free\s*release",
    re.IGNORECASE,
)


async def find_gate_url_in_text(text: str) -> str | None:
    """Find a gate URL in text."""
    urls = re.findall(r'https?://[^\s"\'<>\)]+', text)
    for url in urls:
        for domain in GATE_DOMAINS:
            if domain in url:
                return url.rstrip(".,;:!?)")
    return None


async def main():
    config = Config.load()
    config.ensure_dirs()
    session = BrowserSession(config.browser)
    await session.start()
    page = session.page

    found_tracks = []
    seen_urls = set()
    target_count = 3

    try:
        logger.info("Going to SoundCloud feed...")
        await page.goto("https://soundcloud.com/feed", wait_until="domcontentloaded")
        await page.wait_for_timeout(5000)

        # Check if logged in
        feed_check = await page.evaluate("""() => {
            const items = document.querySelectorAll('.soundList__item, .userStreamItem');
            return { itemCount: items.length, url: window.location.href };
        }""")
        logger.info("Feed state: %s", feed_check)

        if feed_check["itemCount"] == 0:
            # Try waiting more
            await page.wait_for_timeout(5000)

        max_scrolls = 15
        for scroll in range(max_scrolls):
            if len(found_tracks) >= target_count:
                break

            logger.info("=== Scroll %d (found %d/%d) ===", scroll + 1, len(found_tracks), target_count)

            # Get all visible track items
            tracks_data = await page.evaluate("""() => {
                const results = [];
                // SoundCloud feed items
                const items = document.querySelectorAll('.soundList__item, .userStreamItem');
                for (const item of items) {
                    const titleEl = item.querySelector('.soundTitle__title span, .soundTitle__title');
                    const artistEl = item.querySelector('.soundTitle__username, .soundTitle__usernameText');
                    const linkEl = item.querySelector('a.soundTitle__title, a.sc-link-dark');
                    const descEl = item.querySelector('.truncatedAudioInfo__content, .sc-truncate');

                    // Check for "Buy" or "Free Download" button
                    const buyLink = item.querySelector('a.sc-buylink, a[href*="hypeddit"], a[href*="toneden"], a[href*="fanlink"]');

                    // Get full text content to search for "free download" mentions
                    const fullText = item.textContent || '';

                    const data = {
                        title: titleEl?.textContent?.trim() || '',
                        artist: artistEl?.textContent?.trim() || '',
                        trackUrl: linkEl?.href || '',
                        buyHref: buyLink?.href || '',
                        hasFreeDL: /free\s*(download|dl|d\/l)/i.test(fullText),
                        descText: descEl?.textContent?.trim()?.substring(0, 500) || '',
                    };

                    if (data.trackUrl && data.title) {
                        results.push(data);
                    }
                }
                return results;
            }""")

            for track in tracks_data:
                if track["trackUrl"] in seen_urls:
                    continue
                seen_urls.add(track["trackUrl"])

                gate_url = None

                # Check buy link first
                if track["buyHref"]:
                    for domain in GATE_DOMAINS:
                        if domain in track["buyHref"]:
                            gate_url = track["buyHref"]
                            break

                # Check description text for gate URLs
                if not gate_url and track["descText"]:
                    gate_url = await find_gate_url_in_text(track["descText"])

                # Check if "free download" is mentioned
                if not gate_url and not track["hasFreeDL"]:
                    continue

                # If we found a mention but no URL yet, click into the track to check
                if not gate_url and track["hasFreeDL"]:
                    logger.info("  '%s' by %s has 'free dl' mention, checking...",
                                track["title"][:40], track["artist"])

                if gate_url:
                    logger.info("  FOUND: '%s' by %s -> %s",
                                track["title"][:40], track["artist"], gate_url[:80])

                    # Determine type
                    track_type = "hypeddit" if "hypeddit.com" in gate_url else "gate"

                    found_tracks.append({
                        "url": gate_url,
                        "title": track["title"],
                        "artist": track["artist"],
                        "type": track_type,
                        "soundcloud_url": track["trackUrl"],
                    })

                    if len(found_tracks) >= target_count:
                        break

            # If not enough found, try clicking into tracks that mention "free download"
            if len(found_tracks) < target_count:
                for track in tracks_data:
                    if len(found_tracks) >= target_count:
                        break
                    if track["trackUrl"] in seen_urls and track["trackUrl"] not in [t.get("soundcloud_url") for t in found_tracks]:
                        continue
                    if not track["hasFreeDL"] and not track["buyHref"]:
                        continue
                    # Already found gate URL for this one
                    if any(t.get("soundcloud_url") == track["trackUrl"] for t in found_tracks):
                        continue

                    # Click into the track page to find gate URL
                    logger.info("  Checking track page: %s", track["trackUrl"][:80])
                    try:
                        await page.goto(track["trackUrl"], wait_until="domcontentloaded")
                        await page.wait_for_timeout(3000)

                        # Check buy button
                        buy_href = await page.evaluate("""() => {
                            const buyLink = document.querySelector('a.sc-buylink');
                            return buyLink?.href || '';
                        }""")

                        # Check description
                        desc = await page.evaluate("""() => {
                            // Click "Show more" if present
                            const showMore = document.querySelector('.truncatedAudioInfo__wrapper button');
                            if (showMore) showMore.click();

                            const el = document.querySelector('.truncatedAudioInfo__content');
                            return el?.textContent?.trim()?.substring(0, 2000) || '';
                        }""")

                        gate_url = None
                        if buy_href:
                            for domain in GATE_DOMAINS:
                                if domain in buy_href:
                                    gate_url = buy_href
                                    break

                        if not gate_url and desc:
                            gate_url = await find_gate_url_in_text(desc)

                        if gate_url:
                            track_type = "hypeddit" if "hypeddit.com" in gate_url else "gate"
                            logger.info("  FOUND via page: '%s' -> %s", track["title"][:40], gate_url[:80])
                            found_tracks.append({
                                "url": gate_url,
                                "title": track["title"],
                                "artist": track["artist"],
                                "type": track_type,
                                "soundcloud_url": track["trackUrl"],
                            })

                        # Go back to feed
                        await page.goto("https://soundcloud.com/feed", wait_until="domcontentloaded")
                        await page.wait_for_timeout(3000)

                    except Exception as e:
                        logger.warning("  Error checking track: %s", e)
                        await page.goto("https://soundcloud.com/feed", wait_until="domcontentloaded")
                        await page.wait_for_timeout(3000)

            if len(found_tracks) >= target_count:
                break

            # Scroll down for more
            await page.evaluate("window.scrollBy(0, 2000)")
            await page.wait_for_timeout(3000)

    except Exception as e:
        logger.error("Error scanning feed: %s", e)

    await session.close()

    if found_tracks:
        # Write JSON
        output_path = "test-feed.json"
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(found_tracks, f, indent=2, ensure_ascii=False)
        logger.info("\n=== Found %d tracks ===", len(found_tracks))
        for i, t in enumerate(found_tracks, 1):
            logger.info("  %d. %s - %s", i, t["artist"], t["title"])
            logger.info("     Gate: %s", t["url"])
        logger.info("\nSaved to %s", output_path)
    else:
        logger.warning("No free download tracks found in feed!")


asyncio.run(main())
