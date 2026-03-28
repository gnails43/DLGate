"""Scan SoundCloud feed for tracks with free download gate links.

Two-phase approach:
  Phase 1: Scroll feed and collect all candidate track URLs (fast, no navigation)
  Phase 2: Visit each candidate track page to extract gate URLs

Usage:
  python find_free_dl.py [--count 100] [--exclude previous-results.json]
"""
import argparse
import asyncio
import json
import logging
import re
import sys
from pathlib import Path

from dlgate.browser.session import BrowserSession
from dlgate.config import Config

logging.basicConfig(level=logging.INFO, format="%(levelname)-8s %(message)s")
logger = logging.getLogger(__name__)

# Known gate domains
GATE_DOMAINS = [
    "hypeddit.com", "toneden.io", "fanlink.to", "gate.fm",
    "hive.co", "boost.link", "distrokid.com/hyperfollow",
    "gate.sc",  # SoundCloud buy link wrapper → redirects to actual gate URL
]


def resolve_gate_sc(url: str) -> str:
    """Resolve gate.sc redirect URLs to actual gate URLs."""
    from urllib.parse import parse_qs, unquote, urlparse
    parsed = urlparse(url)
    if "gate.sc" in parsed.netloc:
        qs = parse_qs(parsed.query)
        if "url" in qs:
            return unquote(qs["url"][0])
    return url


def find_gate_url_in_text(text: str) -> str | None:
    """Find a gate URL in text."""
    urls = re.findall(r'https?://[^\s"\'<>\)]+', text)
    for url in urls:
        for domain in GATE_DOMAINS:
            if domain in url:
                resolved = resolve_gate_sc(url.rstrip(".,;:!)"))
                return resolved
    return None


def load_exclude_urls(paths: list[str]) -> set[str]:
    """Load gate URLs from previous result files to exclude."""
    excluded = set()
    for path in paths:
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            for item in data:
                if "url" in item:
                    excluded.add(item["url"])
                if "soundcloud_url" in item:
                    excluded.add(item["soundcloud_url"])
        except Exception as e:
            logger.warning("Could not load exclude file %s: %s", path, e)
    return excluded


async def phase1_collect_candidates(page, max_candidates: int = 500, max_scrolls: int = 300) -> list[dict]:
    """Phase 1: Scroll feed and collect candidate tracks with buy links or free DL mentions.

    Does NOT navigate away from the feed page. Only collects metadata visible in feed.
    """
    candidates = []
    seen_track_urls = set()
    stale_count = 0  # How many scrolls without new candidates

    for scroll in range(max_scrolls):
        # Extract all visible feed items
        tracks_data = await page.evaluate("""() => {
            const results = [];
            const items = document.querySelectorAll('.soundList__item, .userStreamItem');
            for (const item of items) {
                const titleEl = item.querySelector('.soundTitle__title span, .soundTitle__title');
                const artistEl = item.querySelector('.soundTitle__username, .soundTitle__usernameText');
                const linkEl = item.querySelector('a.soundTitle__title, a.sc-link-dark');
                const descEl = item.querySelector('.truncatedAudioInfo__content, .sc-truncate');

                // Check for "Buy" or gate link buttons
                const buyLink = item.querySelector(
                    'a.sc-buylink, a[href*="hypeddit"], a[href*="toneden"], ' +
                    'a[href*="fanlink"], a[href*="gate.fm"], a[href*="hive.co"], a[href*="boost.link"]'
                );

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

        new_this_scroll = 0
        for track in tracks_data:
            if track["trackUrl"] in seen_track_urls:
                continue
            seen_track_urls.add(track["trackUrl"])

            # Quick filter: must have buy link OR free DL mention OR gate URL in desc
            has_gate_in_buy = any(d in track["buyHref"] for d in GATE_DOMAINS) if track["buyHref"] else False
            has_gate_in_desc = find_gate_url_in_text(track["descText"]) is not None if track["descText"] else False

            if has_gate_in_buy or has_gate_in_desc or track["hasFreeDL"]:
                # Pre-extract gate URL if visible from feed
                gate_url = None
                if has_gate_in_buy:
                    gate_url = resolve_gate_sc(track["buyHref"])
                elif has_gate_in_desc:
                    gate_url = find_gate_url_in_text(track["descText"])

                candidates.append({
                    "title": track["title"],
                    "artist": track["artist"],
                    "trackUrl": track["trackUrl"],
                    "gateUrl": gate_url,  # May be None, will resolve in phase 2
                    "buyHref": track["buyHref"],
                    "hasFreeDL": track["hasFreeDL"],
                })
                new_this_scroll += 1

        total_seen = len(seen_track_urls)
        total_candidates = len(candidates)

        if new_this_scroll > 0:
            stale_count = 0
        else:
            stale_count += 1

        # Log every 5 scrolls or when new candidates found
        if scroll % 5 == 0 or new_this_scroll > 0:
            logger.info("Scroll %3d | seen: %d | candidates: %d | new: %d",
                        scroll + 1, total_seen, total_candidates, new_this_scroll)

        if total_candidates >= max_candidates:
            logger.info("Reached max candidates (%d), stopping scroll", max_candidates)
            break

        # If 15 scrolls without new candidates, feed is exhausted
        if stale_count >= 15:
            logger.info("No new candidates for %d scrolls, feed exhausted", stale_count)
            break

        # Scroll down
        await page.evaluate("window.scrollBy(0, 1500)")
        await page.wait_for_timeout(1500)

    logger.info("Phase 1 complete: %d candidates from %d feed items", len(candidates), len(seen_track_urls))
    return candidates


async def phase2_resolve_gate_urls(page, candidates: list[dict], exclude_urls: set[str],
                                     target_count: int = 100) -> list[dict]:
    """Phase 2: Visit each candidate's track page to resolve gate URL.

    Skips candidates that already have gate URLs from phase 1 (unless excluded).
    """
    found_tracks = []
    seen_gate_urls = set(exclude_urls)

    for i, cand in enumerate(candidates):
        if len(found_tracks) >= target_count:
            break

        # If already have gate URL from phase 1
        gate_url = cand.get("gateUrl")

        if gate_url and gate_url in seen_gate_urls:
            continue

        if gate_url:
            # Validate it's a known gate domain
            is_gate = any(d in gate_url for d in GATE_DOMAINS)
            if is_gate and gate_url not in seen_gate_urls:
                seen_gate_urls.add(gate_url)
                track_type = "hypeddit" if "hypeddit.com" in gate_url else "gate"
                found_tracks.append({
                    "url": gate_url,
                    "title": cand["title"],
                    "artist": cand["artist"],
                    "type": track_type,
                    "soundcloud_url": cand["trackUrl"],
                })
                logger.info("[%3d/%3d] ✓ %s - %s (from feed)",
                           len(found_tracks), target_count,
                           cand["artist"][:25], cand["title"][:35])
                continue

        # Need to visit the track page to find gate URL
        logger.info("[%3d/%3d] Checking: %s - %s",
                   len(found_tracks), target_count,
                   cand["artist"][:25], cand["title"][:35])

        try:
            await page.goto(cand["trackUrl"], wait_until="domcontentloaded")
            await page.wait_for_timeout(2000)

            # Extract buy link and description
            page_data = await page.evaluate("""() => {
                // Check buy button
                const buyLink = document.querySelector('a.sc-buylink');
                const buyHref = buyLink?.href || '';

                // Click "Show more" if present
                const showMore = document.querySelector('.truncatedAudioInfo__wrapper button');
                if (showMore) showMore.click();

                // Get description
                const descEl = document.querySelector('.truncatedAudioInfo__content');
                const desc = descEl?.textContent?.trim()?.substring(0, 3000) || '';

                // Also check all links in the description area
                const descLinks = [];
                const linkEls = document.querySelectorAll('.truncatedAudioInfo__content a, .sc-tag-group a');
                for (const a of linkEls) {
                    if (a.href) descLinks.push(a.href);
                }

                return { buyHref, desc, descLinks };
            }""")

            gate_url = None

            # Check buy link
            if page_data["buyHref"]:
                for domain in GATE_DOMAINS:
                    if domain in page_data["buyHref"]:
                        gate_url = page_data["buyHref"]
                        break

            # Check description text
            if not gate_url and page_data["desc"]:
                gate_url = find_gate_url_in_text(page_data["desc"])

            # Check description links
            if not gate_url:
                for link in page_data.get("descLinks", []):
                    for domain in GATE_DOMAINS:
                        if domain in link:
                            gate_url = link
                            break
                    if gate_url:
                        break

            if gate_url and gate_url not in seen_gate_urls:
                seen_gate_urls.add(gate_url)
                track_type = "hypeddit" if "hypeddit.com" in gate_url else "gate"
                found_tracks.append({
                    "url": gate_url,
                    "title": cand["title"],
                    "artist": cand["artist"],
                    "type": track_type,
                    "soundcloud_url": cand["trackUrl"],
                })
                logger.info("[%3d/%3d] ✓ Found gate: %s", len(found_tracks), target_count, gate_url[:80])
            elif gate_url:
                logger.info("         ✗ Already seen: %s", gate_url[:80])
            else:
                logger.info("         ✗ No gate URL found")

        except Exception as e:
            logger.warning("         ✗ Error: %s", str(e)[:80])

    return found_tracks


async def main():
    parser = argparse.ArgumentParser(description="Find free download tracks from SoundCloud feed")
    parser.add_argument("--count", type=int, default=100, help="Number of tracks to find (default: 100)")
    parser.add_argument("--exclude", nargs="*", default=[], help="JSON files with previously found tracks to exclude")
    parser.add_argument("--output", default="test-feed.json", help="Output JSON file path")
    args = parser.parse_args()

    target_count = args.count
    exclude_urls = load_exclude_urls(args.exclude)
    if exclude_urls:
        logger.info("Excluding %d previously found URLs", len(exclude_urls))

    config = Config.load()
    config.ensure_dirs()
    session = BrowserSession(config.browser)
    await session.start()
    page = session.page

    found_tracks = []

    try:
        # Navigate to feed
        logger.info("Going to SoundCloud feed...")
        await page.goto("https://soundcloud.com/feed", wait_until="domcontentloaded")
        await page.wait_for_timeout(5000)

        # Check if logged in
        feed_check = await page.evaluate("""() => {
            const items = document.querySelectorAll('.soundList__item, .userStreamItem');
            return { itemCount: items.length, url: window.location.href };
        }""")
        logger.info("Feed state: %d items loaded, url=%s", feed_check["itemCount"], feed_check["url"])

        if feed_check["itemCount"] == 0:
            logger.warning("No feed items found. Are you logged in?")
            await page.wait_for_timeout(5000)
            feed_check2 = await page.evaluate("""() => {
                return document.querySelectorAll('.soundList__item, .userStreamItem').length;
            }""")
            if feed_check2 == 0:
                logger.error("Still no items. Aborting.")
                await session.close()
                return

        # Phase 1: Collect candidates from feed
        logger.info("=" * 60)
        logger.info("PHASE 1: Scrolling feed to collect candidates...")
        logger.info("=" * 60)
        candidates = await phase1_collect_candidates(page, max_candidates=target_count * 5)

        if not candidates:
            logger.warning("No candidates found in feed!")
            await session.close()
            return

        # Phase 2: Resolve gate URLs
        logger.info("=" * 60)
        logger.info("PHASE 2: Resolving gate URLs for %d candidates...", len(candidates))
        logger.info("=" * 60)
        found_tracks = await phase2_resolve_gate_urls(page, candidates, exclude_urls, target_count)

    except Exception as e:
        logger.error("Error: %s", e, exc_info=True)

    await session.close()

    # Save results
    if found_tracks:
        output_path = args.output
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(found_tracks, f, indent=2, ensure_ascii=False)

        logger.info("")
        logger.info("=" * 60)
        logger.info("RESULTS: Found %d tracks with gate URLs", len(found_tracks))
        logger.info("=" * 60)

        # Count by type
        type_counts = {}
        for t in found_tracks:
            tp = t.get("type", "unknown")
            type_counts[tp] = type_counts.get(tp, 0) + 1
        for tp, cnt in type_counts.items():
            logger.info("  %s: %d", tp, cnt)

        logger.info("")
        for i, t in enumerate(found_tracks, 1):
            logger.info("  %3d. %s - %s", i, t["artist"][:25], t["title"][:40])
        logger.info("")
        logger.info("Saved to %s", output_path)
    else:
        logger.warning("No free download tracks found!")


asyncio.run(main())
