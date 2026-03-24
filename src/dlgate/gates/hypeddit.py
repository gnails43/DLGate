from __future__ import annotations

import logging
import random
import re
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from playwright.async_api import Page

from dlgate.browser.actions import random_delay, take_screenshot
from dlgate.config import Config
from dlgate.gates.base import BaseGateHandler
from dlgate.models import GateResult, GateStepType, ProcessStatus, Track

logger = logging.getLogger(__name__)

MAX_STEPS = 20  # Safety limit to avoid infinite loops


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


async def detect_screen_state(page: Page) -> dict:
    """Detect what's currently visible on the Hypeddit page."""
    return await page.evaluate("""() => {
        const currentSlide = document.querySelector('.fangate-slider-content.current-slide');
        if (currentSlide) {
            const cls = currentSlide.className || '';
            const tokens = cls.split(/\s+/);

            if (tokens.includes('dw')) {
                return { screen: 'download_ready', details: cls.trim() };
            }

            const classMap = {
                'sc': 'soundcloud', 'ig': 'instagram', 'tk': 'tiktok',
                'sp': 'spotify', 'yt': 'youtube', 'fb': 'facebook',
                'tw': 'twitter', 'am': 'apple_music', 'email': 'email',
            };
            for (const [key, screen] of Object.entries(classMap)) {
                if (tokens.includes(key)) {
                    return { screen, details: cls.trim() };
                }
            }
            if (currentSlide.querySelector('#email_address'))
                return { screen: 'email', details: 'email field in current-slide' };
            if (currentSlide.querySelector('.hype-btn-soundcloud'))
                return { screen: 'soundcloud', details: 'SC button in current-slide' };

            return { screen: 'unknown_slide', details: cls.trim() };
        }

        const anySlide = document.querySelector('.fangate-slider-content');
        if (anySlide) {
            return { screen: 'landing', details: 'slides exist but no current-slide' };
        }

        const dlBtn = document.querySelector('#gateDownloadButton');
        if (dlBtn) {
            return { screen: 'landing', details: 'gateDownloadButton only' };
        }

        return { screen: 'unknown', details: document.title };
    }""")


class HypedditHandler(BaseGateHandler):
    def __init__(self):
        self._api_requests: list[dict] = []
        self._gate_id: str | None = None
        self._steps: str | None = None
        self._csrf_token: str | None = None
        self._is_skippable: bool = True

    async def can_handle(self, url: str) -> bool:
        return "hypeddit.com" in url or "gate.sc" in url

    @staticmethod
    def _resolve_gate_url(url: str) -> str:
        """Resolve gate.sc redirect URLs and other wrappers to actual Hypeddit URLs.

        gate.sc wraps URLs like: https://gate.sc/?url=https%3A%2F%2Fhypeddit.com%2F...
        """
        parsed = urlparse(url)
        # gate.sc redirect
        if "gate.sc" in parsed.netloc:
            qs = parse_qs(parsed.query)
            if "url" in qs:
                resolved = unquote(qs["url"][0])
                logger.info("Resolved gate.sc URL: %s -> %s", url[:60], resolved[:80])
                return resolved
        return url

    def _generate_email_alias(self, base_email: str) -> str:
        """Generate a unique email alias by inserting random dots in the local part.

        Gmail ignores dots in the local part, so g.na.k@gmail.com delivers
        to gnak@gmail.com, but Hypeddit treats them as different addresses.
        This avoids the "attempts over" rate limit per email.

        Note: + addressing (user+tag@) is rejected by Hypeddit's validator.
        """
        local, domain = base_email.split("@", 1)
        # Strip existing dots and + tags for a clean base
        local = local.split("+")[0].replace(".", "")
        if len(local) < 2:
            return base_email
        # Insert dots at random positions (but never at start/end or consecutive)
        positions = sorted(random.sample(range(1, len(local)), min(random.randint(1, 3), len(local) - 1)))
        parts = []
        prev = 0
        for pos in positions:
            parts.append(local[prev:pos])
            prev = pos
        parts.append(local[prev:])
        dotted = ".".join(parts)
        return f"{dotted}@{domain}"

    async def process(self, page: Page, track: Track, config: Config) -> GateResult:
        result = GateResult(track=track)
        gate_url = track.gate_url or track.url
        self._retried_download = False

        try:
            # Resolve gate.sc redirect URLs to actual Hypeddit URLs
            gate_url = self._resolve_gate_url(gate_url)
            logger.info("Processing Hypeddit gate: %s", gate_url)

            # Set up network request interception BEFORE loading the page
            self._api_requests = []
            page.on("request", self._capture_request)
            page.on("response", self._capture_response)

            response = await page.goto(gate_url, wait_until="domcontentloaded")
            await random_delay(2000, 3000)

            # Check for 404 / deleted gate
            if response and response.status == 404:
                logger.warning("Gate returned 404: %s", gate_url)
                result.status = ProcessStatus.SKIPPED
                result.error_message = "Gate page not found (404)"
                return result

            # Check page content for deleted/removed gate
            page_text = await page.evaluate("document.body?.innerText?.substring(0, 500) || ''")
            if any(phrase in page_text.lower() for phrase in [
                "page not found", "gate not found", "has been removed",
                "no longer available", "this page doesn't exist",
                "404", "not found",
            ]):
                logger.warning("Gate appears deleted: %s", gate_url)
                result.status = ProcessStatus.SKIPPED
                result.error_message = "Gate page deleted or not found"
                return result

            # Dismiss cookie consent if present
            await self._dismiss_cookies(page)
            await random_delay(500, 1000)

            # Extract gate metadata
            await self._extract_gate_metadata(page)

            # Click initial Download button to activate the gate
            await self._click_initial_download(page)
            await random_delay(3000, 5000)
            await take_screenshot(page, "01_after_activate")

            # Re-extract metadata after gate activation (may have changed)
            await self._extract_gate_metadata(page)

            # Reactive loop: detect screen state and act accordingly
            step_num = 1
            prev_screen = None
            stale_count = 0

            for iteration in range(MAX_STEPS):
                state = await detect_screen_state(page)
                screen = state["screen"]
                details = state["details"]
                logger.info("Step %d: screen=%s details=%s", step_num, screen, details)

                # Detect stale state
                if screen == prev_screen:
                    stale_count += 1
                    if stale_count >= 3:
                        logger.warning("Stuck on '%s' for %d iterations", screen, stale_count)
                        await take_screenshot(page, f"{step_num:02d}_stuck_{screen}")
                        # Dump all captured API requests for debugging
                        self._dump_api_log()
                        break
                else:
                    stale_count = 0
                prev_screen = screen

                await take_screenshot(page, f"{step_num:02d}_{screen}")

                if screen == "landing":
                    await self._click_initial_download(page)
                    await random_delay(1000, 2000)
                    if not await self._wait_for_auto_advance(page, screen):
                        await self._advance_slide(page)
                    await random_delay(1000, 2000)

                elif screen == "email":
                    await self._handle_email(page, config)
                    result.steps_completed.append(GateStepType.EMAIL)
                    if not await self._wait_for_auto_advance(page, screen):
                        await self._advance_slide(page)
                    await random_delay(1000, 2000)

                elif screen == "soundcloud":
                    await self._handle_soundcloud(page, config)
                    result.steps_completed.append(GateStepType.SOUNDCLOUD_OAUTH)
                    if not await self._wait_for_auto_advance(page, screen):
                        await self._advance_slide(page)
                    await random_delay(2000, 3000)

                elif screen in ("instagram", "tiktok", "spotify", "youtube",
                                "facebook", "twitter", "apple_music"):
                    await self._handle_social_step(page, screen)
                    result.steps_completed.append(GateStepType.SOCIAL_LINK)
                    if not await self._wait_for_auto_advance(page, screen):
                        await self._advance_slide(page)
                    await random_delay(1000, 2000)

                elif screen == "download_ready":
                    # Check server-side pathway to find missing steps
                    await self._complete_missing_steps(page, config, result)
                    # Then mark all steps as skipped (server + client)
                    await self._mark_all_steps_skipped(page)
                    download_path = await self._handle_final_download(page, config)
                    if download_path:
                        result.status = ProcessStatus.SUCCESS
                        result.download_path = download_path
                        result.steps_completed.append(GateStepType.DOWNLOAD)
                        await take_screenshot(page, f"{step_num:02d}_download_result")
                        self._dump_api_log()
                        return result

                    # Download failed - try reloading the gate page once to get
                    # server-side state and retry with actual incomplete steps.
                    if not getattr(self, '_retried_download', False):
                        self._retried_download = True
                        logger.info("Download failed, reloading gate to check server state")
                        await page.goto(gate_url, wait_until="domcontentloaded")
                        await random_delay(2000, 3000)
                        await self._dismiss_cookies(page)
                        await self._click_initial_download(page)
                        await random_delay(3000, 5000)
                        prev_screen = None
                        # Continue the loop
                    else:
                        result.status = ProcessStatus.FAILED
                        result.error_message = "Download failed (after retry)"
                        await take_screenshot(page, f"{step_num:02d}_download_result")
                        self._dump_api_log()
                        return result

                elif screen in ("unknown", "unknown_slide"):
                    logger.warning("Unknown screen state, trying to proceed")
                    await self._try_click_next(page)
                    await random_delay(1000, 2000)

                step_num += 1

            # If we exit the loop without downloading
            if result.status != ProcessStatus.SUCCESS:
                result.status = ProcessStatus.FAILED
                result.error_message = "Gate processing did not reach download"
                await take_screenshot(page, "final_state")
                self._dump_api_log()

        except Exception as e:
            logger.error("Gate processing failed: %s", e)
            result.status = ProcessStatus.FAILED
            result.error_message = str(e)
            self._dump_api_log()
            try:
                await take_screenshot(page, "gate_error")
            except Exception:
                pass

        return result

    def _capture_request(self, request) -> None:
        """Capture all requests to Hypeddit API endpoints."""
        url = request.url
        if "hypeddit.com" in url and not any(ext in url for ext in [".css", ".js", ".png", ".jpg", ".gif", ".ico", ".svg", ".woff"]):
            entry = {
                "url": url,
                "method": request.method,
                "post_data": request.post_data,
                "type": "request",
            }
            # For gate API calls, capture headers too
            if "setGate" in url or "download" in url or "gate/" in url:
                try:
                    entry["headers"] = dict(request.headers)
                except Exception:
                    pass
                logger.info("GATE API Request: %s %s data=%s headers=%s",
                            request.method, url, request.post_data, entry.get("headers", {}))
            self._api_requests.append(entry)

    async def _capture_response_async(self, response) -> None:
        """Capture responses from Hypeddit API endpoints (async version)."""
        url = response.url
        if "hypeddit.com" in url and ("setGate" in url or "download" in url or "gate" in url.split("hypeddit.com")[-1]):
            entry = {
                "url": url,
                "status": response.status,
                "type": "response",
            }
            # Capture response body for download API
            if "download" in url:
                try:
                    body = await response.text()
                    entry["body"] = body[:2000]
                    logger.info("GATE API Response body: %s", body[:500])
                except Exception:
                    pass
            self._api_requests.append(entry)
            logger.info("GATE API Response: %d %s", response.status, url)

    def _capture_response(self, response) -> None:
        """Capture responses from Hypeddit API endpoints."""
        url = response.url
        if "hypeddit.com" in url and ("setGate" in url or "download" in url or "gate" in url.split("hypeddit.com")[-1]):
            entry = {
                "url": url,
                "status": response.status,
                "type": "response",
            }
            self._api_requests.append(entry)
            logger.info("GATE API Response: %d %s", response.status, url)

    def _dump_api_log(self) -> None:
        """Log all captured API requests for debugging."""
        if self._api_requests:
            logger.info("=== Captured %d API requests ===", len(self._api_requests))
            for entry in self._api_requests:
                if entry["type"] == "request":
                    logger.info("  %s %s | data: %s", entry["method"], entry["url"], entry.get("post_data"))
                else:
                    logger.info("  <- %s %s", entry.get("status"), entry["url"])
        else:
            logger.info("=== No API requests captured ===")

    async def _dismiss_cookies(self, page: Page) -> None:
        """Dismiss cookie consent banners."""
        await page.evaluate("""() => {
            const btns = document.querySelectorAll(
                'button[class*="cookie"], a[class*="cookie"], .cookie-banner button, ' +
                '[class*="consent"] button, [class*="gdpr"] button, a[class*="dismiss"]'
            );
            for (const btn of btns) { btn.click(); }
            document.querySelectorAll('button, a').forEach(el => {
                const text = el.textContent.trim().toLowerCase();
                if (text === 'accept' || text === 'ok' || text === 'got it' ||
                    text === 'accept all' || text === 'agree') {
                    el.click();
                }
            });
        }""")

    async def _mark_all_steps_skipped(self, page: Page) -> None:
        """Register all gate steps as skipped both server-side and client-side.

        1. Call /setGatePathwayOr for each step type in steps_select (server-side)
        2. Add skip_gate_steps[] hidden inputs (client-side, for DL form submission)
        """
        # Server-side: register each step as skipped via API
        steps = (self._steps or "").split(",")
        step_types = [s for s in steps if s and s != "dw"]

        if self._gate_id and step_types:
            csrf_token = self._csrf_token or ""
            for step in step_types:
                skip_result = await page.evaluate(f"""async () => {{
                    try {{
                        let token = '{csrf_token}';
                        if (!token) {{
                            const meta = document.querySelector('meta[name="csrf-token"]');
                            if (meta) token = meta.getAttribute('content');
                        }}
                        const fd = new URLSearchParams();
                        fd.append('fan_gate_id', '{self._gate_id}');
                        fd.append('skipSteps[]', '{step}');
                        fd.append('selectedStep', '{step}');
                        const r = await fetch('/setGatePathwayOr', {{
                            method: 'POST', body: fd.toString(), credentials: 'include',
                            headers: {{
                                'Content-Type': 'application/x-www-form-urlencoded',
                                'X-Requested-With': 'XMLHttpRequest',
                                'X-CSRF-TOKEN': token,
                            }},
                        }});
                        return {{ status: r.status, body: (await r.text()).substring(0, 100) }};
                    }} catch(e) {{
                        return {{ status: 0, body: 'error: ' + e.message }};
                    }}
                }}""")
                logger.info("Pre-download skip %s: status=%s", step, skip_result.get("status"))

        # Client-side: add hidden inputs for download form
        result = await page.evaluate("""() => {
            const stepTypes = ['email', 'sc', 'ig', 'tk', 'sp', 'yt', 'fb', 'tw', 'am'];
            const added = [];
            for (const step of stepTypes) {
                const existing = document.querySelector(`input[name="skip_gate_steps[]"][value="${step}"]`);
                if (!existing) {
                    const input = document.createElement('input');
                    input.type = 'hidden';
                    input.name = 'skip_gate_steps[]';
                    input.value = step;
                    input.id = 'skippable_' + step;
                    const anchor = document.querySelector('#is_skippable') || document.querySelector('form') || document.body;
                    anchor.appendChild(input);
                    added.push(step);
                }
            }
            const existing = Array.from(document.querySelectorAll('input[name="skip_gate_steps[]"]'))
                .map(el => el.value);
            return { added, existing };
        }""")
        logger.info("Skip gate steps: added=%s existing=%s", result.get("added"), result.get("existing"))

    async def _extract_gate_metadata(self, page: Page) -> None:
        """Extract gate ID, step config, CSRF token, and jumpGate function info."""
        meta = await page.evaluate("""() => {
            const result = {
                fan_gate_id: null,
                steps_select: null,
                all_hidden_inputs: {},
                jumpGate_exists: typeof jumpGate === 'function',
                jumpGate_source: null,
                rX5mPQjW7s_exists: typeof rX5mPQjW7s === 'function',
                slide_classes: [],
                skipper_ids: [],
                csrf_meta: null,
                csrf_input: null,
                jquery_csrf: null,
            };

            // Get CSRF token from various sources
            const csrfMeta = document.querySelector('meta[name="csrf-token"]');
            if (csrfMeta) result.csrf_meta = csrfMeta.getAttribute('content');

            const csrfInput = document.querySelector('input[name="_token"]');
            if (csrfInput) result.csrf_input = csrfInput.value;

            // Check jQuery AJAX setup for CSRF
            if (typeof $ !== 'undefined' && $.ajaxSettings && $.ajaxSettings.headers) {
                result.jquery_csrf = $.ajaxSettings.headers['X-CSRF-TOKEN'] || null;
            }

            // Get jumpGate source code (full)
            if (typeof jumpGate === 'function') {
                result.jumpGate_source = jumpGate.toString().substring(0, 2000);
            }

            // Get all hidden inputs
            const inputs = document.querySelectorAll('input[type="hidden"]');
            for (const input of inputs) {
                if (input.id) result.all_hidden_inputs[input.id] = input.value;
                if (input.name) result.all_hidden_inputs['name:' + input.name] = input.value;
                if (input.id === 'fan_gate_id') result.fan_gate_id = input.value;
                if (input.id === 'steps_select') result.steps_select = input.value;
            }

            // Get all slide classes
            const slides = document.querySelectorAll('.fangate-slider-content');
            for (const slide of slides) {
                result.slide_classes.push(slide.className);
            }

            // Get all skipper button IDs with onclick details
            const skippers = document.querySelectorAll('[id*="skipper"]');
            for (const sk of skippers) {
                result.skipper_ids.push({
                    id: sk.id,
                    tag: sk.tagName,
                    text: sk.textContent.trim().substring(0, 50),
                    onclick: sk.getAttribute('onclick') || '',
                    href: sk.getAttribute('href') || '',
                });
            }

            return result;
        }""")

        self._gate_id = meta.get("fan_gate_id")
        self._steps = meta.get("steps_select")
        self._csrf_token = meta.get("csrf_meta") or meta.get("csrf_input") or meta.get("jquery_csrf")

        # Track skippable status
        hidden = meta.get("all_hidden_inputs", {})
        is_skip_val = hidden.get("is_skippable") or hidden.get("name:is_skippable") or "1"
        self._is_skippable = is_skip_val != "0"

        logger.info("Gate metadata: id=%s steps=%s skippable=%s", self._gate_id, self._steps, self._is_skippable)
        logger.info("  CSRF: meta=%s input=%s jquery=%s",
                     meta.get("csrf_meta"), meta.get("csrf_input"), meta.get("jquery_csrf"))
        logger.info("  jumpGate exists: %s, source: %s",
                     meta.get("jumpGate_exists"), meta.get("jumpGate_source"))
        logger.info("  rX5mPQjW7s exists: %s", meta.get("rX5mPQjW7s_exists"))
        logger.info("  Hidden inputs: %s", meta.get("all_hidden_inputs"))
        logger.info("  Slide classes: %s", meta.get("slide_classes"))
        logger.info("  Skipper buttons: %s", meta.get("skipper_ids"))

        # Also get XSRF-TOKEN from cookies
        cookies = await page.context.cookies()
        for cookie in cookies:
            if cookie["name"] in ("XSRF-TOKEN", "laravel_session"):
                logger.info("  Cookie: %s = %s...", cookie["name"], cookie["value"][:50])

    async def _click_initial_download(self, page: Page) -> None:
        """Click the initial Download button to reveal the gate steps."""
        logger.info("Clicking initial Download button")
        try:
            btn = await page.query_selector('#gateDownloadButton')
            if btn:
                await btn.click(force=True)
                logger.info("Playwright-clicked #gateDownloadButton")
                return
        except Exception as e:
            logger.debug("Playwright click failed: %s", e)

        try:
            btns = await page.query_selector_all('a.hype-btn-green, a.hype-btn')
            for btn in btns:
                text = await btn.inner_text()
                if 'download' in text.lower():
                    await btn.click(force=True)
                    logger.info("Playwright-clicked button: %s", text.strip())
                    return
        except Exception as e:
            logger.debug("Button search failed: %s", e)

        clicked = await page.evaluate("""() => {
            const btn = document.querySelector('#gateDownloadButton');
            if (btn) { btn.click(); return 'JS: gateDownloadButton'; }
            return null;
        }""")
        logger.info("Fallback click: %s", clicked)

    async def _handle_email(self, page: Page, config: Config) -> None:
        """Handle email input step.

        Uses dot-alias addressing to avoid Hypeddit's per-email rate limit.
        Gmail ignores dots, so g.nak@gmail.com delivers to gnak@gmail.com.

        Important: Do NOT call /verifyEmailAddress API directly — let the
        jQuery click handler on the submit button do it. Calling the API
        ourselves first consumes the attempt counter, then the button's
        handler gets "attempts over" and fails to register completion.
        """
        logger.info("Filling email form")

        # Generate a unique email alias to avoid "attempts over" rate limiting
        email = self._generate_email_alias(config.user.email)
        logger.info("Using email alias: %s (base: %s)", email, config.user.email)

        # Fill via JS (.value set) since the email slide may not be visible
        await js_fill(page, "#email_name", config.user.name)
        logger.info("Filled name: %s", config.user.name)

        await js_fill(page, "#email_address", email)
        logger.info("Filled email: %s", email)

        await random_delay(500, 1000)

        # Do NOT call /verifyEmailAddress API here — the button's jQuery
        # click handler calls it internally. If we call it first, we consume
        # the "attempt" and the handler gets "attempts over".

        # Intercept the verifyEmailAddress response to log the result
        email_api_result = []
        async def capture_email_response(response):
            if "verifyEmailAddress" in response.url:
                try:
                    body = await response.text()
                    email_api_result.append(body)
                    logger.info("Email API (from button handler): %s", body[:200])
                except Exception:
                    pass

        page.on("response", capture_email_response)

        # NOTE: We don't call /verifyEmailAddress here anymore.
        # Instead, we rely on the jQuery click handler below.
        email_result = "skipped (let button handler do it)"
        # Legacy log line kept for compatibility:
        logger.info("Email API: %s", str(email_result)[:200])

        # Click submit button — the jQuery handler will call /verifyEmailAddress
        # and if successful, will call jumpGate() to advance + register completion.
        clicked = False
        try:
            btn = await page.query_selector('#email_to_downloads_next')
            if btn:
                await btn.click(force=True)
                logger.info("Clicked email submit (Playwright real click)")
                clicked = True
        except Exception as e:
            logger.debug("Playwright email submit failed: %s", e)

        if not clicked:
            if await js_click(page, "#email_to_downloads_next"):
                logger.info("Clicked email submit (JS fallback)")
                clicked = True

        if clicked:
            # Wait for jQuery handler to call /verifyEmailAddress and process
            await random_delay(4000, 6000)
            # Log captured email API response
            if email_api_result:
                logger.info("Email verify result: %s", email_api_result[-1][:200])
            else:
                logger.warning("No email API response captured after button click")

        # Clean up response listener
        try:
            page.remove_listener("response", capture_email_response)
        except Exception:
            pass

    async def _complete_missing_steps(self, page: Page, config: Config, result: GateResult) -> None:
        """Check server-side pathway and complete any steps that were skipped client-side.

        When Hypeddit's JS auto-advances past steps (e.g. SC OAuth already done
        in browser), the server may not have recorded those completions. This
        method queries /getGatePathway and fills in the gaps.
        """
        if not self._gate_id:
            return

        csrf_token = self._csrf_token or ""
        steps = (self._steps or "").split(",")
        step_types = [s for s in steps if s and s != "dw"]

        # Query server for which steps are already completed
        pathway = await page.evaluate(f"""async () => {{
            try {{
                const fd = new URLSearchParams();
                fd.append('fan_gate_id', '{self._gate_id}');
                const r = await fetch('/getGatePathway', {{
                    method: 'POST', body: fd.toString(), credentials: 'include',
                    headers: {{
                        'Content-Type': 'application/x-www-form-urlencoded',
                        'X-Requested-With': 'XMLHttpRequest',
                        'X-CSRF-TOKEN': '{csrf_token}',
                    }},
                }});
                return await r.json();
            }} catch(e) {{
                return {{ error: e.message }};
            }}
        }}""")
        logger.info("getGatePathway before download: %s", pathway)

        completed = set()
        if isinstance(pathway, dict):
            skip_steps = pathway.get("skip_gate_steps", [])
            if isinstance(skip_steps, list):
                completed = set(skip_steps)

        missing = [s for s in step_types if s not in completed]
        if not missing:
            logger.info("All steps completed server-side")
            return

        logger.info("Missing steps server-side: %s (completed: %s)", missing, completed)

        # Complete missing steps
        for step in missing:
            if step == "sc" and GateStepType.SOUNDCLOUD_OAUTH not in result.steps_completed:
                logger.info("Completing missing SC OAuth step")
                await self._handle_soundcloud(page, config)
                result.steps_completed.append(GateStepType.SOUNDCLOUD_OAUTH)
            elif step == "email" and GateStepType.EMAIL not in result.steps_completed:
                logger.info("Completing missing email step")
                await self._handle_email(page, config)
                result.steps_completed.append(GateStepType.EMAIL)
            else:
                # For social steps (ig, sp, tk, etc), call /setGatePathwayOr
                logger.info("Registering missing step '%s' via API", step)
                await page.evaluate(f"""async () => {{
                    const fd = new URLSearchParams();
                    fd.append('fan_gate_id', '{self._gate_id}');
                    fd.append('skipSteps[]', '{step}');
                    fd.append('selectedStep', '{step}');
                    await fetch('/setGatePathwayOr', {{
                        method: 'POST', body: fd.toString(), credentials: 'include',
                        headers: {{
                            'Content-Type': 'application/x-www-form-urlencoded',
                            'X-Requested-With': 'XMLHttpRequest',
                            'X-CSRF-TOKEN': '{csrf_token}',
                        }},
                    }});
                }}""")

    async def _handle_soundcloud(self, page: Page, config: Config) -> None:
        """Handle SoundCloud step (comment + Connect via OAuth).

        Flow:
        1. Fill SC comment text
        2. Save comment via /setSC API
        3. Extract OAuth URL from button's data-onclick attribute
        4. Open popup via window.open (preserves window.opener)
        5. Click Allow on SC authorization page
        6. Wait for popup to close (auth2.php callback calls self.close())
        7. Call /windowopenerlog to register SC step completion
        """
        logger.info("Handling SoundCloud step")

        # Fill comment field
        comment = random.choice(config.comments)
        filled = await page.evaluate(f"""() => {{
            // Fill the comment textarea/input
            const selectors = ['#sc_comment_text', 'textarea', 'input[type="text"]:not([type="hidden"]):not([type="email"])'];
            for (const sel of selectors) {{
                const containers = [
                    document.querySelector('.current-slide'),
                    document.querySelector('.fangate-slider-content.sc'),
                    document,
                ];
                for (const container of containers) {{
                    if (!container) continue;
                    const el = container.querySelector(sel);
                    if (el) {{
                        el.value = {repr(comment)};
                        el.dispatchEvent(new Event('input', {{bubbles: true}}));
                        el.dispatchEvent(new Event('change', {{bubbles: true}}));
                        return true;
                    }}
                }}
            }}
            return false;
        }}""")
        if filled:
            logger.info("Filled comment: %s", comment)
            await random_delay(500, 1000)

        # Save SC comment via API (like the mobile flow does)
        if self._gate_id and self._csrf_token:
            sc_result = await page.evaluate(f"""async () => {{
                const fd = new URLSearchParams();
                fd.append('fan_gate_id', '{self._gate_id}');
                fd.append('comment_sc', {repr(comment)});
                const r = await fetch('/setSC', {{
                    method: 'POST', body: fd.toString(), credentials: 'include',
                    headers: {{
                        'Content-Type': 'application/x-www-form-urlencoded',
                        'X-Requested-With': 'XMLHttpRequest',
                        'X-CSRF-TOKEN': '{self._csrf_token}',
                    }},
                }});
                return await r.text();
            }}""")
            logger.info("SC comment API: %s", sc_result)

        # Extract OAuth URL from button's data-onclick attribute
        oauth_url = await page.evaluate("""() => {
            const btns = document.querySelectorAll('#login_to_sc');
            for (const btn of btns) {
                const attr = btn.getAttribute('data-onclick') || btn.getAttribute('onclick') || '';
                const match = attr.match(/PopupCenterDual\\('([^']+)'/);
                if (match) return match[1];
            }
            return null;
        }""")

        if oauth_url:
            logger.info("SC OAuth URL extracted: %s", oauth_url[:100])

            # Open popup via window.open (preserves window.opener for callback)
            try:
                async with page.expect_popup(timeout=10000) as popup_info:
                    await page.evaluate(
                        f"window.open('{oauth_url}', 'sc_popup', 'width=800,height=500')"
                    )
                popup = await popup_info.value
                logger.info("SC OAuth popup opened (window.opener preserved)")

                await popup.wait_for_load_state("domcontentloaded")
                await random_delay(2000, 3000)

                # Handle the OAuth popup
                if "soundcloud.com" in popup.url:
                    await self._handle_sc_oauth_popup(popup)

                # Wait for popup to close (auth2.php callback calls self.close())
                for _ in range(20):
                    import asyncio as _aio
                    await _aio.sleep(1)
                    if popup.is_closed():
                        logger.info("SC OAuth popup closed (auth callback complete)")
                        break
                else:
                    if not popup.is_closed():
                        try:
                            await popup.close()
                        except Exception:
                            pass

            except Exception as e:
                logger.warning("SC OAuth popup failed: %s", e)

            # Register SC step via /windowopenerlog (what the callback's
            # localStorage event handler normally does)
            if self._gate_id:
                await page.evaluate(f"""async () => {{
                    const fd = new URLSearchParams();
                    fd.append('elementID', 'login_to_sc');
                    fd.append('fangate_id', '{self._gate_id}');
                    await fetch('/windowopenerlog', {{
                        method: 'POST', body: fd.toString(), credentials: 'include',
                        headers: {{
                            'Content-Type': 'application/x-www-form-urlencoded',
                            'X-Requested-With': 'XMLHttpRequest',
                            'X-CSRF-TOKEN': '{self._csrf_token}',
                        }},
                    }});
                }}""")
                logger.info("Called /windowopenerlog for SC step")

            # Wait for server processing
            await random_delay(3000, 5000)

            # Check if slide auto-advanced
            new_state = await detect_screen_state(page)
            if new_state["screen"] != "soundcloud":
                logger.info("SC step auto-advanced to: %s", new_state["screen"])
                return
        else:
            # No OAuth URL found - try clicking the button directly
            logger.info("No OAuth URL in button, trying direct click")
            clicked = False

            try:
                selectors = [
                    '.current-slide a.login-to-soundcloud-common',
                    '.current-slide a.hype-btn-soundcloud',
                    '.current-slide a.hype-btn-green',
                    '.fangate-slider-content.sc a.hype-btn-green',
                ]
                for sel in selectors:
                    btn = await page.query_selector(sel)
                    if btn:
                        btn_id = await btn.get_attribute("id") or ""
                        text = await btn.inner_text()
                        if "skipper" in btn_id or text.strip().lower() in ("next", "skip"):
                            continue
                        await btn.click(force=True)
                        clicked = True
                        logger.info("SC Connect clicked: %s", text.strip())
                        break
            except Exception as e:
                logger.warning("SC button click failed: %s", e)

            if clicked:
                # Wait for OAuth popup
                try:
                    new_page = await page.context.wait_for_event("page", timeout=10000)
                    if new_page:
                        await new_page.wait_for_load_state("domcontentloaded")
                        if "soundcloud.com" in new_page.url:
                            await self._handle_sc_oauth_popup(new_page)
                        try:
                            await new_page.wait_for_event("close", timeout=30000)
                        except Exception:
                            try:
                                await new_page.close()
                            except Exception:
                                pass
                except Exception:
                    logger.info("No OAuth popup (may already be authorized)")

                await random_delay(5000, 8000)
                new_state = await detect_screen_state(page)
                if new_state["screen"] != "soundcloud":
                    logger.info("SC step auto-advanced to: %s", new_state["screen"])
                    return

        # If we're still on SC step, the OAuth might have failed or wasn't needed
        logger.info("Still on SC step after Connect click, will try to advance")

    async def _handle_sc_oauth_popup(self, popup: Page) -> None:
        """Handle the SoundCloud OAuth authorization popup.

        Flow: SC login page → Continue with Facebook → FB auto-auth → redirect back
        """
        await random_delay(2000, 3000)
        try:
            await take_screenshot(popup, "sc_oauth_popup")
        except Exception:
            pass

        # Check if this is a login page or an authorization page
        page_text = await popup.evaluate("() => document.body?.innerText || ''")
        logger.info("OAuth popup text (first 200): %s", page_text[:200])

        if "sign in" in page_text.lower() or "create an account" in page_text.lower():
            # This is a login page - click "Continue with Facebook"
            logger.info("SC OAuth shows login page, clicking Continue with Facebook")
            try:
                # Try multiple selectors for the Facebook button
                fb_btn = None
                fb_selectors = [
                    'button:has-text("Continue with Facebook")',
                    'button:has-text("Facebook")',
                ]
                for sel in fb_selectors:
                    try:
                        fb_btn = popup.locator(sel).first
                        if await fb_btn.count() > 0:
                            break
                        fb_btn = None
                    except Exception:
                        fb_btn = None

                if not fb_btn:
                    # Try via query_selector with text matching
                    btns = await popup.query_selector_all('button')
                    for btn in btns:
                        text = await btn.inner_text()
                        if 'facebook' in text.lower():
                            fb_btn = btn
                            break

                if fb_btn:
                    # Click Facebook button - redirects in-page (not a new popup)
                    logger.info("Clicking Facebook login button")
                    if hasattr(fb_btn, 'click'):
                        await fb_btn.click()
                    else:
                        await fb_btn.click()

                    # Wait for FB page to load (in-page redirect)
                    await random_delay(3000, 5000)
                    try:
                        await popup.wait_for_load_state("domcontentloaded", timeout=10000)
                    except Exception:
                        pass

                    if not popup.is_closed():
                        try:
                            await take_screenshot(popup, "fb_login_page")
                        except Exception:
                            pass

                        # FB shows "Log in as X" button if already logged in
                        logger.info("FB page URL: %s", popup.url)
                        fb_text = await popup.evaluate("() => document.body?.innerText || ''")
                        logger.info("FB page text (first 200): %s", fb_text[:200])

                        # Click the "Log in as X" / "Continue as X" button
                        login_clicked = False

                        # Try various selectors for FB's login/continue button
                        fb_login_selectors = [
                            # Japanese: "Xとしてログイン"
                            'div[role="button"][aria-label*="ログイン"]',
                            'span[data-sigil="touchable"]',
                            # Generic login/continue buttons
                            'button[name="__CONFIRM__"]',
                            'input[name="__CONFIRM__"]',
                            '#loginbutton',
                            'button[type="submit"]',
                        ]
                        for sel in fb_login_selectors:
                            try:
                                btn = await popup.query_selector(sel)
                                if btn:
                                    text = await btn.inner_text()
                                    logger.info("FB button found: %s (%s)", sel, text.strip())
                                    await btn.click()
                                    login_clicked = True
                                    logger.info("Clicked FB login button: %s", text.strip())
                                    break
                            except Exception:
                                continue

                        if not login_clicked:
                            # Try text-based: look for button with "ログイン" or "Log in" or "Continue"
                            try:
                                btns = await popup.query_selector_all('div[role="button"], button, input[type="submit"], a[role="button"]')
                                for btn in btns:
                                    try:
                                        text = await btn.inner_text()
                                    except Exception:
                                        text = await btn.get_attribute("value") or ""
                                    text_lower = text.strip().lower()
                                    if any(kw in text_lower for kw in ["ログイン", "log in", "continue", "続行"]):
                                        # Skip "キャンセル" (Cancel)
                                        if "キャンセル" in text or "cancel" in text_lower:
                                            continue
                                        await btn.click()
                                        login_clicked = True
                                        logger.info("Clicked FB button by text: %s", text.strip())
                                        break
                            except Exception as e:
                                logger.debug("FB text button search failed: %s", e)

                        if login_clicked:
                            logger.info("FB login confirmed, waiting for redirect...")
                            # Wait for redirect chain: FB → SC OAuth → Hypeddit callback
                            await random_delay(5000, 8000)
                        else:
                            logger.warning("Could not find FB login button")

                else:
                    logger.warning("Could not find Facebook login button")
            except Exception as e:
                logger.warning("Facebook login flow failed: %s", e)

        elif "authorize" in page_text.lower() or "connect" in page_text.lower() or "allow" in page_text.lower() or "access" in page_text.lower():
            # Authorization page - click Allow/Connect/Authorize
            logger.info("SC OAuth shows authorization page, clicking Allow")
            try:
                # Try #submit_approval first (SC's actual Allow button ID)
                auth_btn = await popup.query_selector('#submit_approval')
                if auth_btn:
                    await auth_btn.click()
                    logger.info("Clicked #submit_approval (Allow) button")
                else:
                    # Fallback: search by text
                    auth_btn = popup.locator('button:has-text("Allow"), button:has-text("Connect"), button:has-text("Authorize")').first
                    if await auth_btn.count() > 0:
                        await auth_btn.click()
                        logger.info("Clicked Allow/Connect/Authorize button")
                    else:
                        # Last resort: click submit button
                        submit = await popup.query_selector('button[type="submit"]')
                        if submit:
                            await submit.click()
                            logger.info("Clicked submit button")
            except Exception as e:
                logger.warning("Could not click authorize button: %s", e)

        # After handling, wait for redirects and check each state
        # Poll the popup state for up to 30 seconds
        for check in range(10):
            await random_delay(2000, 3000)
            try:
                if popup.is_closed():
                    logger.info("OAuth popup closed (auth completed)")
                    return
            except Exception:
                logger.info("OAuth popup closed (auth completed)")
                return

            try:
                current_url = popup.url
                logger.info("OAuth popup URL: %s", current_url)
                await take_screenshot(popup, f"sc_oauth_check_{check}")

                page_text = await popup.evaluate("() => document.body?.innerText || ''")

                # SC Authorization page: click "Allow"
                if "allow" in page_text.lower() and "soundcloud" in page_text.lower():
                    logger.info("SC authorization page detected, clicking Allow")
                    # Try multiple selectors
                    allow_clicked = False
                    allow_selectors = [
                        'button:has-text("Allow")',
                        'input[value="Allow"]',
                        'button[type="submit"]',
                        'input[type="submit"]',
                    ]
                    for sel in allow_selectors:
                        try:
                            btn = popup.locator(sel).first
                            if await btn.count() > 0:
                                await btn.click()
                                allow_clicked = True
                                logger.info("Clicked Allow via: %s", sel)
                                break
                        except Exception:
                            continue

                    if not allow_clicked:
                        # Try query_selector
                        btns = await popup.query_selector_all('button, input[type="submit"]')
                        for btn in btns:
                            try:
                                text = await btn.inner_text()
                            except Exception:
                                text = await btn.get_attribute("value") or ""
                            if "allow" in text.strip().lower():
                                await btn.click()
                                allow_clicked = True
                                logger.info("Clicked Allow button: %s", text.strip())
                                break

                    if allow_clicked:
                        logger.info("Allow clicked, waiting for redirect to Hypeddit...")
                        await random_delay(5000, 8000)
                        continue

                # FB login page: click login button
                if "facebook" in current_url.lower() and ("ログイン" in page_text or "log in" in page_text.lower()):
                    logger.info("Still on FB login page, looking for login button")
                    btns = await popup.query_selector_all('div[role="button"], button, input[type="submit"]')
                    for btn in btns:
                        try:
                            text = await btn.inner_text()
                        except Exception:
                            text = await btn.get_attribute("value") or ""
                        if any(kw in text for kw in ["ログイン", "Log in", "Continue", "続行"]):
                            if "キャンセル" not in text and "cancel" not in text.lower():
                                await btn.click()
                                logger.info("Clicked FB button: %s", text.strip())
                                break

                # Check if redirected back to Hypeddit (auth complete)
                if "hypeddit.com" in current_url:
                    logger.info("Redirected to Hypeddit callback, auth should be complete")
                    await random_delay(2000, 3000)
                    try:
                        await popup.close()
                    except Exception:
                        pass
                    return

            except Exception as e:
                logger.debug("Popup check failed: %s", e)
                return

    async def _handle_social_step(self, page: Page, platform: str) -> None:
        """Handle a social link step (IG, TikTok, Spotify, etc.)."""
        platform_to_class = {
            "instagram": "ig", "tiktok": "tk", "spotify": "sp",
            "youtube": "yt", "facebook": "fb", "twitter": "tw",
            "apple_music": "am",
        }
        step_class = platform_to_class.get(platform, platform)
        logger.info("Handling social step: %s (class: %s)", platform, step_class)

        # Find and click action buttons using Playwright real click (not JS click)
        container_sel = f'.fangate-slider-content.{step_class}.current-slide, .current-slide'
        action_btns = await page.query_selector_all(
            f'{container_sel} a.hype-btn, {container_sel} button.hype-btn, '
            f'{container_sel} a.hype-btn-social, {container_sel} a.hype-btn-green'
        )
        action_count = 0
        for btn in action_btns:
            try:
                btn_id = await btn.get_attribute("id") or ""
                text = (await btn.inner_text()).strip().lower()
                if "skipper" in btn_id or text in ("next", "skip"):
                    continue
                await btn.click(force=True)
                action_count += 1
                logger.info("Clicked %s action button: %s (id=%s)", platform, text, btn_id)
            except Exception as e:
                logger.debug("Button click failed: %s", e)

        if action_count == 0:
            # Fallback to JS click
            action_count = await page.evaluate(f"""() => {{
                const container = document.querySelector('.fangate-slider-content.{step_class}.current-slide') ||
                                  document.querySelector('.current-slide');
                if (!container) return 0;
                const links = container.querySelectorAll('a.hype-btn, button.hype-btn, a.hype-btn-social, a.hype-btn-green');
                let clicked = 0;
                for (const link of links) {{
                    const id = link.id || '';
                    const text = link.textContent.trim().toLowerCase();
                    if (id.includes('skipper') || text === 'next' || text === 'skip') continue;
                    link.click();
                    clicked++;
                }}
                return clicked;
            }}""")
            logger.info("Clicked %d action(s) via JS fallback", action_count)

        # Handle new tabs that opened
        if action_count > 0:
            try:
                new_page = await page.context.wait_for_event("page", timeout=5000)
                if new_page:
                    await new_page.wait_for_load_state("domcontentloaded")
                    logger.info("Opened %s tab: %s", platform, new_page.url)
                    await random_delay(3000, 5000)
                    try:
                        await new_page.close()
                    except Exception:
                        pass
            except Exception:
                pass

        await random_delay(1000, 2000)

        # Click Next/Skip button using Playwright real click
        await self._try_click_next_playwright(page, step_class)

        # Wait for server to process
        await random_delay(3000, 5000)

        # Check if auto-advanced
        new_state = await detect_screen_state(page)
        if new_state["screen"] != platform:
            logger.info("Step auto-advanced to: %s", new_state["screen"])

    async def _wait_for_auto_advance(self, page: Page, current_screen: str, max_checks: int = 3) -> bool:
        """Wait for the page's own JS to auto-advance the slide after a step action.

        Returns True if the slide auto-advanced (server-side), False if still stuck.
        """
        for i in range(max_checks):
            await random_delay(1000, 2000)
            new_state = await detect_screen_state(page)
            if new_state["screen"] != current_screen:
                logger.info("Auto-advanced: %s -> %s (after %d checks)",
                            current_screen, new_state["screen"], i + 1)
                return True
        logger.info("No auto-advance from '%s' after %d checks", current_screen, max_checks)
        return False

    async def _advance_slide(self, page: Page) -> bool:
        """Advance to the next slide using server-side API + CSS manipulation.

        Strategy:
        1. Register skip with /setGatePathwayOr API (server-side)
        2. Try skipper button click (triggers server + client JS)
        3. If slide didn't change, do CSS manipulation (server already notified)
        """
        current_class = await page.evaluate("""() => {
            const current = document.querySelector('.fangate-slider-content.current-slide');
            if (!current) return null;
            const classes = current.className.split(/\\s+/);
            const stepTypes = ['sc', 'ig', 'tk', 'sp', 'yt', 'fb', 'tw', 'am', 'email', 'dw'];
            return classes.find(c => stepTypes.includes(c)) || null;
        }""")

        if not current_class:
            logger.warning("No current slide step type found")
            return False

        logger.info("Advancing from step: %s", current_class)

        # Step 1: Register skip server-side via /setGatePathwayOr
        api_ok = False
        if self._gate_id:
            csrf_token = self._csrf_token or ""
            api_result = await page.evaluate(f"""async () => {{
                try {{
                    let token = '{csrf_token}';
                    if (!token) {{
                        const meta = document.querySelector('meta[name="csrf-token"]');
                        if (meta) token = meta.getAttribute('content');
                    }}

                    const fd = new URLSearchParams();
                    fd.append('fan_gate_id', '{self._gate_id}');
                    fd.append('skipSteps[]', '{current_class}');
                    fd.append('selectedStep', '{current_class}');

                    const response = await fetch('/setGatePathwayOr', {{
                        method: 'POST',
                        body: fd.toString(),
                        credentials: 'include',
                        headers: {{
                            'Content-Type': 'application/x-www-form-urlencoded',
                            'X-Requested-With': 'XMLHttpRequest',
                            'X-CSRF-TOKEN': token,
                        }},
                    }});
                    const text = await response.text();
                    return {{ status: response.status, body: text.substring(0, 200) }};
                }} catch(e) {{
                    return {{ status: 0, body: 'error: ' + e.message }};
                }}
            }}""")
            logger.info("Skip API: status=%s body=%s", api_result.get("status"), api_result.get("body"))
            api_ok = api_result.get("status") == 200

        # Step 2: Try skipper button click (may trigger client-side JS transition)
        skip_result = await page.evaluate(f"""() => {{
            const selectors = [
                '#skipper_{current_class}_channel',
                '.current-slide [id*="skipper"]',
                '.fangate-slider-content.{current_class} [id*="skipper"]',
            ];
            for (const sel of selectors) {{
                const el = document.querySelector(sel);
                if (el) {{
                    el.click();
                    return 'clicked: ' + sel + ' (id=' + el.id + ')';
                }}
            }}
            return null;
        }}""")

        if skip_result:
            logger.info("Skipper click: %s", skip_result)
            await random_delay(2000, 3000)

            if await self._check_slide_changed(page, current_class):
                return True

        # Step 3: Try jumpGate
        jump_result = await page.evaluate(f"""() => {{
            const current = document.querySelector('.fangate-slider-content.current-slide');
            if (!current) return 'no current slide';
            if (typeof jumpGate !== 'function') return 'jumpGate not found';
            try {{
                jumpGate(current, 'skip');
                return 'jumpGate called';
            }} catch(e) {{
                return 'jumpGate error: ' + e.message;
            }}
        }}""")
        logger.info("jumpGate result: %s", jump_result)

        if "called" in str(jump_result):
            await random_delay(2000, 3000)
            if await self._check_slide_changed(page, current_class):
                return True

        # Step 4: CSS manipulation to advance visually
        # Server was already notified via API in step 1, so this is safe
        if api_ok:
            logger.info("API registered skip, doing CSS advance")
        else:
            logger.warning("API skip failed, CSS advance may cause download to fail")

        # Use steps_select to find the correct next step
        steps_select = self._steps or ""
        css_result = await page.evaluate(f"""() => {{
            const current = document.querySelector('.fangate-slider-content.current-slide');
            if (!current) return 'no current slide';

            // Get the step order from steps_select (e.g. "dw,email,sc,ig")
            const stepsOrder = '{steps_select}'.split(',').filter(s => s && s !== 'dw');
            const stepTypes = ['sc', 'ig', 'tk', 'sp', 'yt', 'fb', 'tw', 'am', 'email', 'dw'];

            // Find current step type
            const currentType = Array.from(current.classList).find(c => stepTypes.includes(c));
            const currentIdx = stepsOrder.indexOf(currentType);

            // First try: use upcomming-slide if it exists
            const upcoming = document.querySelector('.fangate-slider-content.upcomming-slide');
            if (current && upcoming) {{
                current.classList.remove('current-slide', 'zindex');
                current.classList.add('move-left');
                upcoming.classList.remove('upcomming-slide');
                upcoming.classList.add('current-slide', 'zindex');
                const nextType = Array.from(upcoming.classList).find(c => stepTypes.includes(c));
                return 'CSS advanced to ' + (nextType || 'unknown');
            }}

            // Second try: use steps_select order to find next step's slide
            if (currentIdx >= 0 && currentIdx < stepsOrder.length - 1) {{
                const nextStepType = stepsOrder[currentIdx + 1];
                const nextSlide = document.querySelector('.fangate-slider-content.' + nextStepType);
                if (nextSlide) {{
                    current.classList.remove('current-slide', 'zindex');
                    current.classList.add('move-left');
                    nextSlide.classList.remove('upcomming-slide');
                    nextSlide.classList.add('current-slide', 'zindex');
                    return 'CSS advanced via steps_select to ' + nextStepType;
                }}
            }}

            // Third try: next step is 'dw' (download)
            const dwSlide = document.querySelector('.fangate-slider-content.dw');
            if (dwSlide && dwSlide !== current) {{
                current.classList.remove('current-slide', 'zindex');
                current.classList.add('move-left');
                dwSlide.classList.remove('upcomming-slide');
                dwSlide.classList.add('current-slide', 'zindex');
                return 'CSS advanced to dw (download)';
            }}

            // Last resort: next sibling
            const next = current.nextElementSibling;
            if (next && next.classList.contains('fangate-slider-content')) {{
                current.classList.remove('current-slide', 'zindex');
                current.classList.add('move-left');
                next.classList.remove('upcomming-slide');
                next.classList.add('current-slide', 'zindex');
                const nextType = Array.from(next.classList).find(c => stepTypes.includes(c));
                return 'CSS advanced via sibling to ' + (nextType || 'unknown');
            }}

            return 'no slides to advance';
        }}""")
        logger.info("CSS advance: %s", css_result)
        await random_delay(500, 1000)
        return 'CSS advanced' in str(css_result)

    async def _check_slide_changed(self, page: Page, previous_class: str) -> bool:
        """Check if the current slide has changed from the previous one."""
        new_class = await page.evaluate("""() => {
            const current = document.querySelector('.fangate-slider-content.current-slide');
            if (!current) return 'none';
            const classes = current.className.split(/\\s+/);
            const stepTypes = ['sc', 'ig', 'tk', 'sp', 'yt', 'fb', 'tw', 'am', 'email', 'dw'];
            return classes.find(c => stepTypes.includes(c)) || current.className;
        }""")

        if new_class != previous_class:
            logger.info("Slide advanced: %s -> %s", previous_class, new_class)
            return True
        return False

    async def _try_click_next_playwright(self, page: Page, step_class: str = "") -> bool:
        """Try to click Next/Skip button using Playwright real click."""
        # Try skipper button first
        skipper_selectors = [
            f'#skipper_{step_class}_channel',
            '.current-slide [id*="skipper"]',
            f'.fangate-slider-content.{step_class} [id*="skipper"]',
        ]
        for sel in skipper_selectors:
            try:
                btn = await page.query_selector(sel)
                if btn:
                    await btn.click(force=True)
                    text = await btn.inner_text()
                    logger.info("Clicked skipper (Playwright): %s text=%s", sel, text.strip())
                    return True
            except Exception:
                continue

        # Try Next/Skip text buttons
        btns = await page.query_selector_all('.current-slide button, .current-slide a.hype-btn')
        for btn in btns:
            try:
                text = (await btn.inner_text()).strip().lower()
                if text in ("next", "skip"):
                    await btn.click(force=True)
                    logger.info("Clicked Next/Skip (Playwright): %s", text)
                    return True
            except Exception:
                continue

        # Fallback to JS
        return await self._try_click_next(page, step_class)

    async def _try_click_next(self, page: Page, step_class: str = "") -> bool:
        """Try to click Next/Skip button on current step."""
        clicked = await page.evaluate(f"""() => {{
            const containers = [
                document.querySelector('.current-slide'),
                {f"document.querySelector('.fangate-slider-content.{step_class}')," if step_class else ""}
            ].filter(Boolean);

            for (const container of containers) {{
                const nexts = container.querySelectorAll(
                    'button.button-next, a.button-next, button[id*="skipper"], a[id*="skipper"]'
                );
                for (const btn of nexts) {{ btn.click(); return 'clicked: ' + (btn.id || btn.textContent.trim()); }}

                const allBtns = container.querySelectorAll('button, a.hype-btn');
                for (const btn of allBtns) {{
                    const text = btn.textContent.trim().toLowerCase();
                    if (text === 'next' || text === 'skip') {{
                        btn.click();
                        return 'clicked text: ' + text;
                    }}
                }}
            }}
            return null;
        }}""")
        if clicked:
            logger.info("Next/Skip: %s", clicked)
            await random_delay(1000, 2000)
        return bool(clicked)

    async def _handle_final_download(self, page: Page, config: Config) -> str | None:
        """Handle the final download step."""
        import asyncio as _asyncio

        logger.info("Attempting final download")
        self._dump_api_log()
        await random_delay(1000, 2000)

        output_dir = Path(config.download.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Strategy: Intercept the /gate/download/ul response to get the real download URL,
        # then click the download button and wait for both the API response and download event.

        download_api_body = []

        async def intercept_download_response(response):
            if "gate/download/ul" in response.url and response.status == 200:
                try:
                    body = await response.text()
                    download_api_body.append(body)
                    logger.info("Intercepted download API body: %s", body[:500])
                except Exception as e:
                    logger.debug("Could not read download response body: %s", e)

        page.on("response", intercept_download_response)

        # Method 1: Click download button + expect_download + intercept API response
        dl_selectors = [
            '.dw.current-slide a.free_dwln',
            '.dw.current-slide a.hype-btn-green',
            '.dw.current-slide a.hype-btn',
            '.current-slide a.free_dwln',
            '.current-slide a.hype-btn-green',
            'a.free_dwln',
            '.dw a.hype-btn-green',
            '.dw a.hype-btn',
        ]

        clicked_btn = None
        for sel in dl_selectors:
            try:
                btn = await page.query_selector(sel)
                if btn:
                    text = await btn.inner_text()
                    logger.info("Download button found: sel=%s text=%s", sel, text.strip())
                    clicked_btn = btn
                    break
            except Exception:
                continue

        if clicked_btn:
            # Try expect_download first
            try:
                async with page.expect_download(timeout=20000) as download_info:
                    await clicked_btn.click(force=True)
                download = await download_info.value
                save_path = str(output_dir / download.suggested_filename)
                await download.save_as(save_path)
                logger.info("Downloaded: %s", save_path)
                page.remove_listener("response", intercept_download_response)
                return save_path
            except Exception as e:
                logger.info("expect_download timed out: %s", e)

            # Download event failed. Wait a bit for the API response to arrive.
            await random_delay(2000, 3000)

            # Check if we got the download API response body
            if download_api_body:
                dl_url = self._extract_download_url(download_api_body[-1])
                if dl_url:
                    logger.info("Got download URL from intercepted API: %s", dl_url)
                    result = await self._download_from_url(page, dl_url, output_dir)
                    if result:
                        page.remove_listener("response", intercept_download_response)
                        return result

        # Method 2: If button click triggered "DOWNLOAD STARTED" page,
        # the JS already called the API. Check if we can find the URL in the page.
        page_text = await page.evaluate("() => document.body?.innerText || ''")
        if "download started" in page_text.lower():
            logger.info("Page shows 'DOWNLOAD STARTED' - download was triggered by page JS")
            # The download URL might be in the intercepted response
            if download_api_body:
                dl_url = self._extract_download_url(download_api_body[-1])
                if dl_url:
                    result = await self._download_from_url(page, dl_url, output_dir)
                    if result:
                        page.remove_listener("response", intercept_download_response)
                        return result

        # Method 3: Manually POST to /gate/download/ul with full form data from the page
        logger.info("Trying manual API call with full form data...")
        dl_result = await page.evaluate("""async () => {
            try {
                // Collect all hidden input values (the page stores gate state in them)
                const inputs = document.querySelectorAll('input[type="hidden"]');
                const formData = new URLSearchParams();
                for (const input of inputs) {
                    if (input.name) formData.append(input.name, input.value);
                }
                formData.append('download_action', 'DOWNLOAD');
                formData.append('download_visit', 'true');
                formData.append('profile_downloads', 'true');

                // Get CSRF token
                let token = '';
                const meta = document.querySelector('meta[name="csrf-token"]');
                if (meta) token = meta.getAttribute('content');
                if (!token) {
                    const inp = document.querySelector('input[name="_token"]');
                    if (inp) token = inp.value;
                }

                const headers = {
                    'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                    'X-Requested-With': 'XMLHttpRequest',
                    'Accept': 'application/json, text/javascript, */*; q=0.01',
                };
                if (token) headers['X-CSRF-TOKEN'] = token;

                const response = await fetch('/gate/download/ul', {
                    method: 'POST',
                    body: formData.toString(),
                    credentials: 'include',
                    headers: headers,
                });
                const text = await response.text();
                return { status: response.status, body: text.substring(0, 2000) };
            } catch(e) {
                return { error: e.message };
            }
        }""")
        logger.info("Manual API result: %s", dl_result)

        if isinstance(dl_result, dict) and dl_result.get("body"):
            dl_url = self._extract_download_url(dl_result["body"])
            if dl_url:
                result = await self._download_from_url(page, dl_url, output_dir)
                if result:
                    page.remove_listener("response", intercept_download_response)
                    return result

        page.remove_listener("response", intercept_download_response)
        logger.error("All download methods failed")
        return None

    def _extract_download_url(self, body: str) -> str | None:
        """Extract a download URL from an API response body."""
        import json as _json
        import re as _re

        body = body.strip()

        # Check if it's a direct URL
        if body.startswith("http"):
            return body.split()[0].strip('"\'')

        # Try JSON
        try:
            data = _json.loads(body)
            # Common JSON response fields for download URLs
            for key in ("url", "download_url", "file_url", "link", "redirect", "location"):
                if key in data and isinstance(data[key], str) and data[key].startswith("http"):
                    return data[key]
            # Check nested
            if isinstance(data, dict):
                for v in data.values():
                    if isinstance(v, str) and v.startswith("http") and any(
                        ext in v.lower() for ext in [".mp3", ".wav", ".zip", ".flac", "download"]
                    ):
                        return v
        except (ValueError, TypeError):
            pass

        # Regex for URLs in HTML/text
        urls = _re.findall(r'https?://[^\s"\'<>]+', body)
        for url in urls:
            if any(ext in url.lower() for ext in [".mp3", ".wav", ".zip", ".flac", "download", "s3.amazonaws"]):
                return url

        if urls:
            logger.info("Found URLs in response but none look like downloads: %s", urls[:5])

        return None

    async def _download_from_url(self, page: Page, url: str, output_dir: Path) -> str | None:
        """Download a file from a direct URL."""
        import httpx

        logger.info("Downloading from URL: %s", url)

        # Method A: Try Playwright download
        try:
            async with page.expect_download(timeout=30000) as download_info:
                await page.evaluate(f"window.open('{url}', '_blank')")
            download = await download_info.value
            save_path = str(output_dir / download.suggested_filename)
            await download.save_as(save_path)
            logger.info("Downloaded via Playwright: %s", save_path)
            return save_path
        except Exception as e:
            logger.info("Playwright download failed: %s", e)

        # Method B: Direct HTTP download using cookies from browser
        try:
            cookies = await page.context.cookies()
            cookie_header = "; ".join(f"{c['name']}={c['value']}" for c in cookies if "hypeddit" in c.get("domain", ""))

            async with httpx.AsyncClient(follow_redirects=True, timeout=60.0) as client:
                resp = await client.get(url, headers={
                    "Cookie": cookie_header,
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                })
                if resp.status_code == 200 and len(resp.content) > 1000:
                    # Determine filename from Content-Disposition or URL
                    filename = None
                    cd = resp.headers.get("content-disposition", "")
                    if "filename=" in cd:
                        import re as _re
                        match = _re.search(r'filename[*]?=["\']?([^"\';\n]+)', cd)
                        if match:
                            filename = match.group(1).strip()
                    if not filename:
                        from urllib.parse import urlparse, unquote
                        filename = unquote(urlparse(url).path.split("/")[-1]) or "download.mp3"

                    save_path = str(output_dir / filename)
                    with open(save_path, "wb") as f:
                        f.write(resp.content)
                    logger.info("Downloaded via httpx: %s (%d bytes)", save_path, len(resp.content))
                    return save_path
                else:
                    logger.warning("HTTP download: status=%d size=%d", resp.status_code, len(resp.content))
        except Exception as e:
            logger.warning("httpx download failed: %s", e)

        return None
