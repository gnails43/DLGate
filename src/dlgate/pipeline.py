from __future__ import annotations

import json
import logging
from pathlib import Path

from dlgate.browser.actions import random_delay, take_screenshot
from dlgate.browser.session import BrowserSession
from dlgate.config import Config
from dlgate.gates import get_handler
from dlgate.models import GateResult, ProcessStatus, Track, TrackType
from dlgate.scraper.gate_detector import detect_gate_url
from dlgate.scraper.link_aggregator import (
    is_aggregator_url,
    is_unsupported_platform,
    resolve_aggregator,
)
from dlgate.scraper.soundcloud import get_track_title_artist

logger = logging.getLogger(__name__)


def load_track_list(json_path: str) -> list[Track]:
    """Load tracks from a JSON file exported by the Chrome extension."""
    path = Path(json_path)
    if not path.exists():
        raise FileNotFoundError(f"Track list not found: {json_path}")

    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    tracks = []
    for item in data:
        track_type = TrackType.HYPEDDIT if item.get("type") == "hypeddit" else TrackType.SOUNDCLOUD
        tracks.append(Track(
            url=item["url"],
            title=item.get("title", ""),
            artist=item.get("artist", ""),
            track_type=track_type,
            gate_url=item["url"] if track_type == TrackType.HYPEDDIT else None,
        ))

    return tracks


async def process_tracks(session: BrowserSession, tracks: list[Track], config: Config) -> list[GateResult]:
    """Process a list of tracks through their download gates."""
    results: list[GateResult] = []

    for i, track in enumerate(tracks, 1):
        logger.info("--- Processing track %d/%d: %s ---", i, len(tracks), track.title or track.url)

        try:
            result = await process_single_track(session, track, config)
            results.append(result)

            status_msg = result.status.value.upper()
            if result.download_path:
                logger.info("[%s] Downloaded: %s", status_msg, result.download_path)
            elif result.error_message:
                logger.info("[%s] %s", status_msg, result.error_message)
            else:
                logger.info("[%s] %s", status_msg, track.url)

        except Exception as e:
            logger.error("Unexpected error processing track: %s", e)
            results.append(GateResult(
                track=track,
                status=ProcessStatus.FAILED,
                error_message=str(e),
            ))

        await random_delay(1000, 3000)

    return results


async def process_single_track(session: BrowserSession, track: Track, config: Config) -> GateResult:
    """Process a single track."""
    page = session.page

    # If it's a SoundCloud URL, find the gate URL first
    if track.track_type == TrackType.SOUNDCLOUD and not track.gate_url:
        # Get title/artist from SoundCloud page
        await page.goto(track.url, wait_until="domcontentloaded")
        await page.wait_for_timeout(3000)

        if not track.title:
            track.title, track.artist = await get_track_title_artist(page)

        gate_url = await detect_gate_url(page, track.url)
        if not gate_url:
            return GateResult(
                track=track,
                status=ProcessStatus.NO_GATE,
                error_message="No download gate URL found",
            )
        track.gate_url = gate_url

    # If it's a Hypeddit URL directly, set gate_url
    if track.track_type == TrackType.HYPEDDIT and not track.gate_url:
        track.gate_url = track.url

    # Check if the gate URL is an unsupported platform (Beatport, etc.)
    if track.gate_url and is_unsupported_platform(track.gate_url):
        return GateResult(
            track=track,
            status=ProcessStatus.SKIPPED,
            error_message=f"Unsupported platform (paid store): {track.gate_url}",
        )

    # Check if the gate URL is a link aggregator (Linktree, etc.)
    if track.gate_url and is_aggregator_url(track.gate_url):
        logger.info("Detected link aggregator, resolving: %s", track.gate_url)
        resolved_url = await resolve_aggregator(page, track.gate_url)
        if not resolved_url:
            return GateResult(
                track=track,
                status=ProcessStatus.SKIPPED,
                error_message=f"No free download link found on aggregator page: {track.gate_url}",
            )
        logger.info("Resolved to gate URL: %s", resolved_url)
        track.gate_url = resolved_url

    # Find the right handler
    handler = get_handler(track.gate_url)

    # If no handler found, the URL might redirect to a known gate platform.
    # Follow the URL and check the final destination.
    if not handler and track.gate_url:
        logger.info("Unknown gate URL, following redirect: %s", track.gate_url)
        try:
            response = await page.goto(track.gate_url, wait_until="domcontentloaded", timeout=15000)
            await page.wait_for_timeout(3000)
            final_url = page.url

            if final_url != track.gate_url:
                logger.info("Redirected to: %s", final_url)
                track.gate_url = final_url
                handler = get_handler(final_url)

            # If still no handler, check if the page itself is an aggregator
            if not handler:
                if is_aggregator_url(final_url):
                    resolved = await resolve_aggregator(page, final_url)
                    if resolved:
                        track.gate_url = resolved
                        handler = get_handler(resolved)
                elif is_unsupported_platform(final_url):
                    return GateResult(
                        track=track,
                        status=ProcessStatus.SKIPPED,
                        error_message=f"Unsupported platform: {final_url}",
                    )
        except Exception as e:
            logger.warning("Failed to follow gate URL: %s", e)

    if not handler:
        return GateResult(
            track=track,
            status=ProcessStatus.FAILED,
            error_message=f"No handler for gate URL: {track.gate_url}",
        )

    return await handler.process(page, track, config)
