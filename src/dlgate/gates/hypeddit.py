from __future__ import annotations

import logging
import random
import re

from playwright.async_api import Page

from dlgate.browser.actions import (
    random_delay,
    safe_click,
    safe_fill,
    take_screenshot,
    wait_for_download,
    wait_for_new_page,
)
from dlgate.config import Config
from dlgate.gates.base import BaseGateHandler
from dlgate.models import GateResult, GateStepType, ProcessStatus, Track

logger = logging.getLogger(__name__)


class HypedditHandler(BaseGateHandler):
    async def can_handle(self, url: str) -> bool:
        return "hypeddit.com" in url

    async def process(self, page: Page, track: Track, config: Config) -> GateResult:
        result = GateResult(track=track)
        gate_url = track.gate_url or track.url

        try:
            logger.info("Processing Hypeddit gate: %s", gate_url)
            await page.goto(gate_url, wait_until="domcontentloaded")
            await page.wait_for_selector(".fangate-slider-content", timeout=15000)
            await random_delay(1000, 2000)

            # Determine which steps are present
            steps = await self._detect_steps(page)
            logger.info("Detected steps: %s", steps)

            for step in steps:
                try:
                    if step == "email":
                        await self._handle_email(page, config)
                        result.steps_completed.append(GateStepType.EMAIL)
                    elif step == "soundcloud":
                        await self._handle_soundcloud_oauth(page)
                        result.steps_completed.append(GateStepType.SOUNDCLOUD_OAUTH)
                    elif step == "comment":
                        await self._handle_comment(page, config)
                        result.steps_completed.append(GateStepType.COMMENT)
                    elif step in ("spotify", "instagram", "tiktok", "youtube",
                                  "facebook", "apple_music", "twitter"):
                        await self._handle_social_link(page, step)
                        result.steps_completed.append(GateStepType.SOCIAL_LINK)
                    await random_delay()
                except Exception as e:
                    logger.warning("Step '%s' failed: %s", step, e)
                    await take_screenshot(page, f"step_fail_{step}")

            # Try to download
            download_path = await self._handle_download(page, config)
            if download_path:
                result.status = ProcessStatus.SUCCESS
                result.download_path = download_path
                result.steps_completed.append(GateStepType.DOWNLOAD)
            else:
                result.status = ProcessStatus.FAILED
                result.error_message = "Download button not found or download failed"

        except Exception as e:
            logger.error("Gate processing failed: %s", e)
            result.status = ProcessStatus.FAILED
            result.error_message = str(e)
            try:
                await take_screenshot(page, "gate_fail")
            except Exception:
                pass

        return result

    async def _detect_steps(self, page: Page) -> list[str]:
        """Detect which steps the gate requires by reading #steps_select or scanning the DOM."""
        steps = []

        # Try reading the steps_select hidden input
        steps_value = await page.evaluate(
            "document.getElementById('steps_select')?.value || ''"
        )

        if steps_value:
            logger.debug("steps_select value: %s", steps_value)
            # Parse the comma-separated step identifiers
            raw_steps = [s.strip().lower() for s in steps_value.split(",") if s.strip()]
            for s in raw_steps:
                if "email" in s or "mail" in s:
                    steps.append("email")
                elif "soundcloud" in s or "sc" in s:
                    steps.append("soundcloud")
                elif "comment" in s:
                    steps.append("comment")
                elif "spotify" in s or "sp" in s:
                    steps.append("spotify")
                elif "instagram" in s or "insta" in s or "ig" in s:
                    steps.append("instagram")
                elif "tiktok" in s or "tik" in s:
                    steps.append("tiktok")
                elif "youtube" in s or "yt" in s:
                    steps.append("youtube")
                elif "facebook" in s or "fb" in s:
                    steps.append("facebook")
                elif "apple" in s:
                    steps.append("apple_music")
                elif "twitter" in s or "x" == s:
                    steps.append("twitter")
                else:
                    logger.debug("Unknown step identifier: %s", s)
            return steps

        # Fallback: scan the DOM for step indicators
        logger.debug("No steps_select found, scanning DOM")
        if await page.query_selector("#email_address, #download_email_address"):
            steps.append("email")
        if await page.query_selector("[class*='soundcloud'], [onclick*='connect']"):
            steps.append("soundcloud")
        if await page.query_selector("[class*='comment'], textarea"):
            steps.append("comment")
        if await page.query_selector("[class*='spotify'], #login_sp"):
            steps.append("spotify")
        if await page.query_selector("[class*='instagram']"):
            steps.append("instagram")
        if await page.query_selector("[class*='tiktok']"):
            steps.append("tiktok")
        if await page.query_selector("[class*='youtube']"):
            steps.append("youtube")

        return steps

    async def _handle_email(self, page: Page, config: Config) -> None:
        logger.info("Filling email form")

        # Wait for the email step to be the current slide
        await self._wait_for_current_step(page)

        # Try different email input selectors
        for selector in ["#email_address", "#download_email_address",
                         "input[type='email']", "input[name='email']"]:
            if await safe_fill(page, selector, config.user.email, timeout=3000):
                break

        # Try filling name if present
        for selector in ["input[name='name']", "input[placeholder*='name' i]",
                         "input[placeholder*='Name']"]:
            if await safe_fill(page, selector, config.user.name, timeout=2000):
                break

        # Click submit/next
        await self._click_next_or_submit(page)

    async def _handle_soundcloud_oauth(self, page: Page) -> None:
        logger.info("Handling SoundCloud OAuth")
        await self._wait_for_current_step(page)

        # Look for the SoundCloud connect button
        sc_selectors = [
            "button[class*='soundcloud']",
            "a[class*='soundcloud']",
            "[onclick*='connect']",
            ".hy-btn-soundcloud",
            "button:has-text('SoundCloud')",
            "a:has-text('SoundCloud')",
        ]

        for selector in sc_selectors:
            btn = await page.query_selector(selector)
            if btn and await btn.is_visible():
                # Click opens OAuth popup
                new_page = await wait_for_new_page(
                    page.context,
                    btn.click(),
                    timeout=60000,
                )
                if new_page:
                    # Wait for OAuth to complete (popup closes or redirects)
                    try:
                        await new_page.wait_for_event("close", timeout=60000)
                    except Exception:
                        # If popup didn't close, try clicking authorize
                        try:
                            await safe_click(new_page, "button[type='submit'], .authorize", timeout=5000)
                            await new_page.wait_for_event("close", timeout=30000)
                        except Exception:
                            logger.warning("OAuth popup did not close automatically")
                            try:
                                await new_page.close()
                            except Exception:
                                pass

                await random_delay(1000, 3000)

                # Check if we need to click next after OAuth
                await self._click_next_or_submit(page, required=False)
                return

        logger.warning("SoundCloud OAuth button not found")

    async def _handle_comment(self, page: Page, config: Config) -> None:
        logger.info("Writing comment")
        await self._wait_for_current_step(page)

        comment = random.choice(config.comments)
        logger.info("Using comment: %s", comment)

        comment_selectors = [
            "textarea",
            "input[placeholder*='comment' i]",
            "input[placeholder*='Comment']",
            "[class*='comment'] input",
            "[class*='comment'] textarea",
        ]

        for selector in comment_selectors:
            if await safe_fill(page, selector, comment, timeout=3000):
                break

        await self._click_next_or_submit(page)

    async def _handle_social_link(self, page: Page, platform: str) -> None:
        logger.info("Handling social link: %s", platform)
        await self._wait_for_current_step(page)

        # Find all social buttons for this platform in the current step
        current_slide = await page.query_selector(".current-slide, .fangate-slider-content:not(.move-left)")
        if not current_slide:
            current_slide = page

        # Look for buttons related to this platform
        platform_selectors = {
            "spotify": ["[class*='spotify']", "#login_sp", "a[href*='spotify']"],
            "instagram": ["[class*='instagram']", "a[href*='instagram']"],
            "tiktok": ["[class*='tiktok']", "a[href*='tiktok']"],
            "youtube": ["[class*='youtube']", "a[href*='youtube']"],
            "facebook": ["[class*='facebook']", "a[href*='facebook']"],
            "apple_music": ["#apple-music-authorize", "[class*='apple']"],
            "twitter": ["[class*='twitter']", "[class*='x-']", "a[href*='twitter']", "a[href*='x.com']"],
        }

        selectors = platform_selectors.get(platform, [f"[class*='{platform}']"])

        # Find all action buttons in the current slide
        buttons = []
        for sel in selectors:
            found = await current_slide.query_selector_all(sel)
            for el in found:
                if await el.is_visible():
                    tag = await el.evaluate("el => el.tagName.toLowerCase()")
                    if tag in ("a", "button") or await el.get_attribute("onclick"):
                        buttons.append(el)

        if not buttons:
            # Try broader search - all visible buttons/links in current step
            all_btns = await current_slide.query_selector_all(".all-buttons a, .all-buttons button, .step_button a, .step_button button")
            for el in all_btns:
                if await el.is_visible():
                    buttons.append(el)

        logger.info("Found %d %s button(s)", len(buttons), platform)

        for btn in buttons:
            try:
                # Click the button - may open new tab
                new_page = await wait_for_new_page(
                    page.context,
                    btn.click(),
                    timeout=10000,
                )
                if new_page:
                    await random_delay(2000, 4000)
                    try:
                        await new_page.close()
                    except Exception:
                        pass
                await random_delay(500, 1500)
            except Exception as e:
                logger.warning("Failed to click %s button: %s", platform, e)

        # Click Next/Continue after social links
        await self._click_next_or_submit(page, required=False)

    async def _handle_download(self, page: Page, config: Config) -> str | None:
        logger.info("Looking for download button")
        await random_delay(1000, 2000)

        download_selectors = [
            "a[href*='download']",
            "button:has-text('Download')",
            "a:has-text('Download')",
            ".download-btn",
            "[class*='download']",
            "#downloadProcess a",
            "a.hy-btn",
        ]

        for selector in download_selectors:
            btn = await page.query_selector(selector)
            if btn and await btn.is_visible():
                href = await btn.get_attribute("href")
                if href and not href.startswith("javascript:"):
                    # Direct download link
                    path = await wait_for_download(
                        page,
                        btn.click(),
                        config.download.output_dir,
                    )
                    if path:
                        return path
                else:
                    # Button click triggers download
                    path = await wait_for_download(
                        page,
                        btn.click(),
                        config.download.output_dir,
                    )
                    if path:
                        return path

        logger.warning("No download button found")
        return None

    async def _wait_for_current_step(self, page: Page, timeout: int = 5000) -> None:
        """Wait for the current step slide to be ready."""
        try:
            await page.wait_for_selector(
                ".current-slide, .fangate-slider-content:not(.move-left):not(.upcomming-slide)",
                state="visible",
                timeout=timeout,
            )
        except Exception:
            pass  # Continue even if we can't detect the exact step

    async def _click_next_or_submit(self, page: Page, required: bool = True) -> bool:
        """Click the next/submit/continue button in the current step."""
        next_selectors = [
            ".current-slide button[type='submit']",
            ".current-slide .hy-btn",
            "button:has-text('Next')",
            "button:has-text('Continue')",
            "button:has-text('Submit')",
            "a:has-text('Next')",
            "input[type='submit']",
            ".fangate-slider-content:not(.move-left) .hy-btn",
        ]

        for selector in next_selectors:
            if await safe_click(page, selector, timeout=3000):
                await random_delay(1000, 2000)
                return True

        if required:
            logger.warning("Next/Submit button not found")
        return False
