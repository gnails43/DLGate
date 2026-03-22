from __future__ import annotations

import logging
import random

from playwright.async_api import Page

from dlgate.browser.actions import (
    random_delay,
    take_screenshot,
    wait_for_download,
    wait_for_new_page,
)
from dlgate.config import Config
from dlgate.gates.base import BaseGateHandler
from dlgate.models import GateResult, GateStepType, ProcessStatus, Track

logger = logging.getLogger(__name__)

# Mapping from steps_select tokens to step handler names
STEP_MAP = {
    "email": "email",
    "sc": "soundcloud",
    "ig": "instagram",
    "tk": "tiktok",
    "sp": "spotify",
    "yt": "youtube",
    "fb": "facebook",
    "tw": "twitter",
    "am": "apple_music",
    "dw": "download",
}


async def js_fill(page: Page, selector: str, value: str) -> bool:
    """Fill an input using JavaScript (bypasses visibility checks)."""
    return await page.evaluate(f"""() => {{
        const el = document.querySelector('{selector}');
        if (!el) return false;
        el.value = {repr(value)};
        el.dispatchEvent(new Event('input', {{bubbles: true}}));
        el.dispatchEvent(new Event('change', {{bubbles: true}}));
        return true;
    }}""")


async def js_click(page: Page, selector: str) -> bool:
    """Click an element using JavaScript (bypasses visibility checks)."""
    return await page.evaluate(f"""() => {{
        const el = document.querySelector('{selector}');
        if (!el) return false;
        el.click();
        return true;
    }}""")


class HypedditHandler(BaseGateHandler):
    async def can_handle(self, url: str) -> bool:
        return "hypeddit.com" in url

    async def process(self, page: Page, track: Track, config: Config) -> GateResult:
        result = GateResult(track=track)
        gate_url = track.gate_url or track.url

        try:
            logger.info("Processing Hypeddit gate: %s", gate_url)
            await page.goto(gate_url, wait_until="domcontentloaded")
            await page.wait_for_selector(".fangate-slider-content", state="attached", timeout=15000)
            await random_delay(1000, 2000)

            # Read steps from #steps_select
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
                    elif step == "download":
                        continue
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
        """Detect steps from #steps_select hidden input."""
        steps_value = await page.evaluate(
            "document.getElementById('steps_select')?.value || ''"
        )
        if not steps_value:
            logger.warning("No steps_select found")
            return []

        logger.debug("steps_select value: %s", steps_value)
        steps = []
        for token in steps_value.split(","):
            token = token.strip().lower()
            if token in STEP_MAP:
                steps.append(STEP_MAP[token])
            else:
                logger.debug("Unknown step token: %s", token)
        return steps

    async def _handle_email(self, page: Page, config: Config) -> None:
        logger.info("Filling email form")

        # Fill name
        if await js_fill(page, "#email_name", config.user.name):
            logger.info("Filled name: %s", config.user.name)

        # Fill email
        if await js_fill(page, "#email_address", config.user.email):
            logger.info("Filled email: %s", config.user.email)

        # Click submit
        if await js_click(page, "#email_to_downloads_next"):
            logger.info("Clicked email submit")
            await random_delay(2000, 4000)
        else:
            logger.warning("Email submit button not found")

    async def _handle_soundcloud_oauth(self, page: Page) -> None:
        logger.info("Handling SoundCloud OAuth")

        # Find the SC step's connect button via JS and click it
        # The connect button triggers a popup for OAuth
        clicked = await page.evaluate("""() => {
            const scStep = document.querySelector('.fangate-slider-content.sc');
            if (!scStep) return false;
            const btn = scStep.querySelector('a.hype-btn-green, a.hype-btn, button.hype-btn');
            if (!btn) return false;
            btn.click();
            return true;
        }""")

        if clicked:
            logger.info("Clicked SoundCloud connect button")
            # Wait for possible OAuth popup
            try:
                new_page = await page.context.wait_for_event("page", timeout=10000)
                if new_page:
                    await new_page.wait_for_load_state("domcontentloaded")
                    logger.info("SoundCloud OAuth popup opened")
                    try:
                        await new_page.wait_for_event("close", timeout=60000)
                    except Exception:
                        try:
                            await new_page.close()
                        except Exception:
                            pass
            except Exception:
                logger.info("No OAuth popup (may already be authorized)")
            await random_delay(2000, 4000)
        else:
            logger.warning("SoundCloud connect button not found")

    async def _handle_comment(self, page: Page, config: Config) -> None:
        logger.info("Writing comment")
        comment = random.choice(config.comments)

        await page.evaluate(f"""() => {{
            const ta = document.querySelector('textarea, input[name*="comment"]');
            if (ta) {{
                ta.value = {repr(comment)};
                ta.dispatchEvent(new Event('input', {{bubbles: true}}));
            }}
            const btn = document.querySelector('.current-slide button.hype-btn-green, .current-slide .hype-btn');
            if (btn) btn.click();
        }}""")
        logger.info("Comment submitted: %s", comment)
        await random_delay(1500, 3000)

    async def _handle_social_link(self, page: Page, platform: str) -> None:
        logger.info("Handling social link: %s", platform)

        platform_config = {
            "instagram": "ig",
            "tiktok": "tk",
            "spotify": "sp",
            "youtube": "yt",
            "facebook": "fb",
            "twitter": "tw",
            "apple_music": "am",
        }
        step_class = platform_config.get(platform, platform)

        # Get all action links in this step (excluding Next buttons)
        action_links = await page.evaluate(f"""() => {{
            const step = document.querySelector('.fangate-slider-content.{step_class}');
            if (!step) return [];
            const form = step.querySelector('#step_{step_class}');
            if (!form) return [];
            // Find all action buttons/links (not Next)
            const links = form.querySelectorAll('a.hype-btn, button.hype-btn');
            const result = [];
            for (const link of links) {{
                const text = link.textContent.trim();
                const id = link.id || '';
                if (id.includes('skipper') || text.toLowerCase() === 'next') continue;
                result.push({{
                    tag: link.tagName,
                    text: text.substring(0, 60),
                    href: link.href || '',
                    id: id,
                    hasOnclick: !!link.onclick,
                }});
            }}
            return result;
        }}""")

        logger.info("Found %d %s action(s)", len(action_links), platform)

        for i, link_info in enumerate(action_links):
            logger.debug("  Action %d: %s", i, link_info.get("text", ""))
            # Click the action link via JS
            clicked = await page.evaluate(f"""() => {{
                const step = document.querySelector('.fangate-slider-content.{step_class}');
                const form = step?.querySelector('#step_{step_class}');
                if (!form) return false;
                const links = form.querySelectorAll('a.hype-btn, button.hype-btn');
                let idx = 0;
                for (const link of links) {{
                    const id = link.id || '';
                    if (id.includes('skipper') || link.textContent.trim().toLowerCase() === 'next') continue;
                    if (idx === {i}) {{
                        link.click();
                        return true;
                    }}
                    idx++;
                }}
                return false;
            }}""")

            if clicked:
                # Check if a new tab opened
                try:
                    new_page = await page.context.wait_for_event("page", timeout=5000)
                    if new_page:
                        await new_page.wait_for_load_state("domcontentloaded")
                        logger.info("Opened %s link in new tab", platform)
                        await random_delay(2000, 4000)
                        try:
                            await new_page.close()
                        except Exception:
                            pass
                except Exception:
                    pass
                await random_delay(500, 1500)

        # Click Next/Skip button
        next_clicked = await page.evaluate(f"""() => {{
            const step = document.querySelector('.fangate-slider-content.{step_class}');
            if (!step) return false;
            // Try skipper/next buttons
            const skipper = step.querySelector('button.button-next, button[id*="skipper"], a.button-next, a[id*="skipper"]');
            if (skipper) {{ skipper.click(); return true; }}
            // Fallback: any Next button in the step
            const btns = step.querySelectorAll('button');
            for (const btn of btns) {{
                if (btn.textContent.trim().toLowerCase() === 'next') {{
                    btn.click();
                    return true;
                }}
            }}
            return false;
        }}""")

        if next_clicked:
            logger.info("Clicked Next for %s", platform)
            await random_delay(1000, 2000)
        else:
            logger.warning("Next button not found for %s", platform)

    async def _handle_download(self, page: Page, config: Config) -> str | None:
        logger.info("Looking for download button")
        await random_delay(1000, 2000)

        # Try clicking download button and catching the download
        dl_exists = await page.evaluate("""() => {
            return !!document.querySelector('#gateDownloadButton, a.free_dwln');
        }""")

        if dl_exists:
            try:
                async with page.expect_download(timeout=30000) as download_info:
                    await page.evaluate("""() => {
                        const btn = document.querySelector('#gateDownloadButton') ||
                                    document.querySelector('a.free_dwln');
                        if (btn) btn.click();
                    }""")
                download = await download_info.value
                from pathlib import Path
                save_path = str(Path(config.download.output_dir) / download.suggested_filename)
                await download.save_as(save_path)
                logger.info("Downloaded: %s", save_path)
                return save_path
            except Exception as e:
                logger.error("Download failed: %s", e)
                return None

        logger.warning("Download button not found")
        return None
