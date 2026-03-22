from __future__ import annotations

import logging
import random
from pathlib import Path

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

    async def can_handle(self, url: str) -> bool:
        return "hypeddit.com" in url

    async def process(self, page: Page, track: Track, config: Config) -> GateResult:
        result = GateResult(track=track)
        gate_url = track.gate_url or track.url

        try:
            logger.info("Processing Hypeddit gate: %s", gate_url)

            # Set up network request interception BEFORE loading the page
            self._api_requests = []
            page.on("request", self._capture_request)
            page.on("response", self._capture_response)

            await page.goto(gate_url, wait_until="domcontentloaded")
            await random_delay(2000, 3000)

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
                    await self._advance_slide(page)
                    await random_delay(1000, 2000)

                elif screen == "email":
                    await self._handle_email(page, config)
                    result.steps_completed.append(GateStepType.EMAIL)
                    await self._advance_slide(page)
                    await random_delay(1000, 2000)

                elif screen == "soundcloud":
                    await self._handle_soundcloud(page, config)
                    result.steps_completed.append(GateStepType.SOUNDCLOUD_OAUTH)
                    await self._advance_slide(page)
                    await random_delay(2000, 3000)

                elif screen in ("instagram", "tiktok", "spotify", "youtube",
                                "facebook", "twitter", "apple_music"):
                    await self._handle_social_step(page, screen)
                    result.steps_completed.append(GateStepType.SOCIAL_LINK)
                    await self._advance_slide(page)
                    await random_delay(1000, 2000)

                elif screen == "download_ready":
                    download_path = await self._handle_final_download(page, config)
                    if download_path:
                        result.status = ProcessStatus.SUCCESS
                        result.download_path = download_path
                        result.steps_completed.append(GateStepType.DOWNLOAD)
                    else:
                        result.status = ProcessStatus.FAILED
                        result.error_message = "Download failed"
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

        logger.info("Gate metadata: id=%s steps=%s", self._gate_id, self._steps)
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
        """Handle email input step."""
        logger.info("Filling email form")
        if await js_fill(page, "#email_name", config.user.name):
            logger.info("Filled name: %s", config.user.name)
        if await js_fill(page, "#email_address", config.user.email):
            logger.info("Filled email: %s", config.user.email)
        if await js_click(page, "#email_to_downloads_next"):
            logger.info("Clicked email submit")
            await random_delay(2000, 4000)

    async def _handle_soundcloud(self, page: Page, config: Config) -> None:
        """Handle SoundCloud step (comment + Connect via OAuth)."""
        logger.info("Handling SoundCloud step")

        # Fill comment field if present
        comment = random.choice(config.comments)
        filled = await page.evaluate(f"""() => {{
            const containers = [
                document.querySelector('.current-slide'),
                document.querySelector('.fangate-slider-content.sc'),
            ];
            for (const container of containers) {{
                if (!container) continue;
                const ta = container.querySelector('textarea, input[type="text"]:not([type="hidden"]):not([type="email"])');
                if (ta) {{
                    ta.value = {repr(comment)};
                    ta.dispatchEvent(new Event('input', {{bubbles: true}}));
                    ta.dispatchEvent(new Event('change', {{bubbles: true}}));
                    return true;
                }}
            }}
            return false;
        }}""")
        if filled:
            logger.info("Filled comment: %s", comment)
            await random_delay(500, 1000)

        # Click Connect button with Playwright real click (MUST be real click to open popup)
        clicked = False

        # First, find the button's details via JS to know what we're looking for
        btn_info = await page.evaluate("""() => {
            const containers = [
                document.querySelector('.fangate-slider-content.sc.current-slide'),
                document.querySelector('.current-slide'),
                document.querySelector('.fangate-slider-content.sc'),
            ];
            for (const container of containers) {
                if (!container) continue;
                const btns = container.querySelectorAll('a, button');
                const results = [];
                for (const btn of btns) {
                    const id = btn.id || '';
                    if (id.includes('skipper')) continue;
                    const text = btn.textContent.trim().toLowerCase();
                    if (text === 'next' || text === 'skip') continue;
                    if (btn.className.includes('hype-btn') || text.includes('connect') || text.includes('soundcloud')) {
                        results.push({
                            tag: btn.tagName,
                            id: id,
                            classes: btn.className,
                            text: btn.textContent.trim(),
                            href: btn.getAttribute('href') || '',
                            onclick: btn.getAttribute('onclick') || '',
                        });
                    }
                }
                if (results.length > 0) return results;
            }
            return [];
        }""")
        logger.info("SC buttons found: %s", btn_info)

        # Try multiple Playwright selector strategies
        try:
            selectors = [
                # SC-specific connect buttons
                '.current-slide a.login-to-soundcloud-common',
                '.current-slide a.hype-btn-soundcloud',
                '.current-slide a[id*="login_sp"]',
                '.current-slide a[id*="login_sc"]',
                '.current-slide #login_sp',
                # Generic button selectors in current slide
                '.current-slide a.hype-btn-green',
                '.current-slide button.hype-btn-green',
                '.current-slide a.hype-btn',
                # Wider selectors
                '.fangate-slider-content.sc a.hype-btn-green',
                '.fangate-slider-content.sc a.hype-btn',
                '.fangate-slider-content.sc button.hype-btn-green',
            ]
            for sel in selectors:
                btn = await page.query_selector(sel)
                if btn:
                    text = await btn.inner_text()
                    btn_id = await btn.get_attribute("id") or ""
                    if "skipper" in btn_id or text.strip().lower() in ("next", "skip"):
                        continue
                    logger.info("SC button found with selector %s: text=%s id=%s", sel, text.strip(), btn_id)
                    await btn.click(force=True)
                    logger.info("SC Connect clicked (Playwright real click): %s", text.strip())
                    clicked = True
                    break
        except Exception as e:
            logger.warning("Playwright SC click failed: %s", e)

        # Fallback: use Playwright's text-based locator (also real click)
        if not clicked:
            try:
                connect_btn = page.get_by_text("Connect", exact=False).first
                if connect_btn:
                    await connect_btn.click(force=True)
                    logger.info("SC Connect clicked via text locator")
                    clicked = True
            except Exception as e:
                logger.debug("Text locator failed: %s", e)

        # Last resort: JS click (WARNING: may not open popup)
        if not clicked:
            logger.warning("No Playwright match for SC button, using JS click (popup may not open)")
            result = await page.evaluate("""() => {
                const sc = document.querySelector('.fangate-slider-content.sc.current-slide') ||
                           document.querySelector('.fangate-slider-content.sc') ||
                           document.querySelector('.current-slide');
                if (!sc) return null;
                const btns = sc.querySelectorAll('a.hype-btn-green, button.hype-btn-green, a.hype-btn, button.hype-btn');
                for (const btn of btns) {
                    const id = btn.id || '';
                    if (id.includes('skipper')) continue;
                    const text = btn.textContent.trim().toLowerCase();
                    if (text === 'next' || text === 'skip') continue;
                    btn.click();
                    return btn.textContent.trim();
                }
                return null;
            }""")
            if result:
                clicked = True
                logger.info("SC Connect clicked (JS fallback): %s", result)

        if clicked:
            # Wait for OAuth popup and auto-authorize
            try:
                new_page = await page.context.wait_for_event("page", timeout=10000)
                if new_page:
                    await new_page.wait_for_load_state("domcontentloaded")
                    logger.info("OAuth popup opened: %s", new_page.url)

                    # Auto-handle the SoundCloud OAuth popup
                    if "soundcloud.com" in new_page.url:
                        await self._handle_sc_oauth_popup(new_page)

                    # Wait for popup to close (redirect completes)
                    try:
                        await new_page.wait_for_event("close", timeout=30000)
                        logger.info("OAuth popup closed successfully")
                    except Exception:
                        logger.warning("OAuth popup didn't close, forcing close")
                        try:
                            await new_page.close()
                        except Exception:
                            pass
            except Exception:
                logger.info("No OAuth popup (may already be authorized)")

            # Wait for server to process the OAuth callback and slide transition
            await random_delay(5000, 8000)

            # Check if slide auto-advanced after OAuth
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

        elif "authorize" in page_text.lower() or "connect" in page_text.lower():
            # Authorization page - click Connect/Authorize
            logger.info("SC OAuth shows authorization page, clicking Connect")
            try:
                auth_btn = popup.locator('button:has-text("Connect"), button:has-text("Authorize")').first
                if await auth_btn.count() > 0:
                    await auth_btn.click()
                    logger.info("Clicked Connect/Authorize button")
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

        # Click action buttons (follow/like links, not Next/Skip)
        action_count = await page.evaluate(f"""() => {{
            const container = document.querySelector('.fangate-slider-content.{step_class}.current-slide') ||
                              document.querySelector('.current-slide') ||
                              document.querySelector('.fangate-slider-content.{step_class}');
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
        logger.info("Clicked %d action(s) for %s", action_count, platform)

        # Handle new tabs
        if action_count > 0:
            try:
                new_page = await page.context.wait_for_event("page", timeout=5000)
                if new_page:
                    await new_page.wait_for_load_state("domcontentloaded")
                    logger.info("Opened %s tab: %s", platform, new_page.url)
                    await random_delay(2000, 4000)
                    try:
                        await new_page.close()
                    except Exception:
                        pass
            except Exception:
                pass

        await random_delay(500, 1500)

        # Click Next/Skip button - this should trigger the server-side registration
        await self._try_click_next(page, step_class)

        # Wait for server to process
        await random_delay(2000, 3000)

        # Check if auto-advanced
        new_state = await detect_screen_state(page)
        if new_state["screen"] != platform:
            logger.info("Step auto-advanced to: %s", new_state["screen"])

    async def _advance_slide(self, page: Page) -> bool:
        """Advance to the next slide using server-side API calls.

        Strategy:
        1. Click skipper button (triggers AJAX to /setGatePathwayOr)
        2. Wait for server response
        3. If slide didn't change, try calling jumpGate() directly
        4. If still stuck, call the API via fetch() with gate_id
        5. NO CSS manipulation - if server won't advance, we log and continue
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

        # Method 1: Click the skipper button (most reliable - triggers AJAX)
        skip_result = await page.evaluate(f"""() => {{
            // Try multiple skipper selectors
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
            # Wait for AJAX response and slide transition
            await random_delay(3000, 5000)

            if await self._check_slide_changed(page, current_class):
                return True
            logger.info("Skipper click didn't advance slide")

        # Method 2: Call jumpGate directly
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
            await random_delay(3000, 5000)
            if await self._check_slide_changed(page, current_class):
                return True
            logger.info("jumpGate didn't advance slide either")

        # Method 3: Try calling the Hypeddit API directly via fetch with CSRF token
        if self._gate_id:
            csrf_token = self._csrf_token or ""
            api_result = await page.evaluate(f"""async () => {{
                try {{
                    // Get CSRF token from multiple sources
                    let token = '{csrf_token}';
                    if (!token) {{
                        const meta = document.querySelector('meta[name="csrf-token"]');
                        if (meta) token = meta.getAttribute('content');
                    }}
                    if (!token) {{
                        const input = document.querySelector('input[name="_token"]');
                        if (input) token = input.value;
                    }}
                    // Try from cookie
                    if (!token) {{
                        const match = document.cookie.match(/XSRF-TOKEN=([^;]+)/);
                        if (match) token = decodeURIComponent(match[1]);
                    }}

                    const formData = new FormData();
                    formData.append('fan_gate_id', '{self._gate_id}');
                    formData.append('step', '{current_class}');
                    formData.append('action', 'skip');
                    if (token) formData.append('_token', token);

                    const headers = {{}};
                    if (token) {{
                        headers['X-CSRF-TOKEN'] = token;
                        headers['X-XSRF-TOKEN'] = token;
                    }}
                    headers['X-Requested-With'] = 'XMLHttpRequest';

                    const response = await fetch('/setGatePathwayOr', {{
                        method: 'POST',
                        body: formData,
                        credentials: 'include',
                        headers: headers,
                    }});
                    const text = await response.text();
                    return 'fetch: ' + response.status + ' token=' + (token ? token.substring(0, 20) + '...' : 'NONE') + ' body=' + text.substring(0, 200);
                }} catch(e) {{
                    return 'fetch error: ' + e.message;
                }}
            }}""")
            logger.info("Direct API call: %s", api_result)
            await random_delay(2000, 3000)

            if await self._check_slide_changed(page, current_class):
                return True

        # Method 4: Try using Hypeddit's slide transition function
        transition_result = await page.evaluate(f"""() => {{
            if (typeof rX5mPQjW7s === 'function') {{
                try {{
                    // This function takes an element ID to transition to
                    const upcoming = document.querySelector('.fangate-slider-content.upcomming-slide');
                    if (upcoming) {{
                        // Get the data-group number
                        const group = upcoming.getAttribute('data-group');
                        if (group) {{
                            rX5mPQjW7s(group);
                            return 'transition called with group ' + group;
                        }}
                    }}
                    return 'no upcoming slide or group';
                }} catch(e) {{
                    return 'transition error: ' + e.message;
                }}
            }}
            return 'transition function not found';
        }}""")
        logger.info("Transition function: %s", transition_result)

        if "called" in str(transition_result):
            await random_delay(2000, 3000)
            if await self._check_slide_changed(page, current_class):
                return True

        # Method 5 (last resort): CSS manipulation to at least visually advance
        # This WON'T register server-side, but lets us see what's next
        logger.warning("All server-side methods failed, falling back to CSS (download may not work)")
        css_result = await page.evaluate("""() => {
            const current = document.querySelector('.fangate-slider-content.current-slide');
            const upcoming = document.querySelector('.fangate-slider-content.upcomming-slide');
            if (!current || !upcoming) return 'no slides to advance';
            current.classList.remove('current-slide', 'zindex');
            current.classList.add('move-left');
            upcoming.classList.remove('upcomming-slide');
            upcoming.classList.add('current-slide', 'zindex');
            return 'CSS advanced (server NOT notified)';
        }""")
        logger.warning("CSS fallback: %s", css_result)
        await random_delay(500, 1000)
        return css_result.startswith('CSS advanced')

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
        logger.info("Attempting final download")

        # Log all API requests so far for debugging
        self._dump_api_log()

        await random_delay(1000, 2000)

        # Method 1: Try Playwright's download event with real click
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
        for sel in dl_selectors:
            try:
                btn = await page.query_selector(sel)
                if btn:
                    text = await btn.inner_text()
                    href = await btn.get_attribute("href")
                    onclick = await btn.get_attribute("onclick")
                    logger.info("Download button: sel=%s text=%s href=%s onclick=%s",
                                sel, text.strip(), href, onclick)
                    try:
                        async with page.expect_download(timeout=15000) as download_info:
                            await btn.click(force=True)
                        download = await download_info.value
                        save_path = str(Path(config.download.output_dir) / download.suggested_filename)
                        await download.save_as(save_path)
                        logger.info("Downloaded: %s", save_path)
                        return save_path
                    except Exception as e:
                        logger.warning("Download via %s failed: %s", sel, e)
            except Exception:
                continue

        # Method 2: Call the /gate/download/ul API directly
        logger.info("Trying direct download API call...")
        dl_url = await page.evaluate(f"""async () => {{
            try {{
                // Try the download API endpoint we found in network logs
                const gateId = document.querySelector('#fan_gate_id')?.value || '{self._gate_id or ""}';
                if (!gateId) return {{ error: 'no gate_id' }};

                const formData = new FormData();
                formData.append('fan_gate_id', gateId);

                const response = await fetch('/gate/download/ul', {{
                    method: 'POST',
                    body: formData,
                    credentials: 'include',
                }});
                const text = await response.text();
                return {{ status: response.status, body: text.substring(0, 500) }};
            }} catch(e) {{
                return {{ error: e.message }};
            }}
        }}""")
        logger.info("Download API response: %s", dl_url)

        # If the API returned a URL, try to download it
        if isinstance(dl_url, dict) and dl_url.get("body"):
            body = dl_url["body"]
            # Check if it's a direct URL
            if body.startswith("http"):
                logger.info("Got download URL from API: %s", body)
                try:
                    async with page.expect_download(timeout=30000) as download_info:
                        await page.evaluate(f"window.location.href = '{body}'")
                    download = await download_info.value
                    save_path = str(Path(config.download.output_dir) / download.suggested_filename)
                    await download.save_as(save_path)
                    logger.info("Downloaded via API URL: %s", save_path)
                    return save_path
                except Exception as e:
                    logger.warning("API URL download failed: %s", e)

        # Method 3: Extract download URL from page source/scripts/onclick handlers
        page_dl_url = await page.evaluate("""() => {
            // Check onclick handlers of download buttons
            const btns = document.querySelectorAll('.dw a, .current-slide a, a.free_dwln');
            for (const btn of btns) {
                const onclick = btn.getAttribute('onclick') || '';
                // Look for URL in onclick
                const match = onclick.match(/(https?:\/\/[^'"\\s]+)/);
                if (match) return { source: 'onclick', url: match[1] };
                // Check data attributes
                for (const attr of btn.attributes) {
                    if (attr.value && attr.value.startsWith('http') &&
                        (attr.value.includes('download') || attr.value.includes('.mp3') ||
                         attr.value.includes('.wav') || attr.value.includes('.zip'))) {
                        return { source: 'data-attr', url: attr.value };
                    }
                }
            }

            // Check hidden inputs for download URLs
            const inputs = document.querySelectorAll('input[type="hidden"]');
            for (const input of inputs) {
                if (input.value && (input.value.includes('.mp3') || input.value.includes('.wav') ||
                    input.value.includes('.zip') || input.value.includes('/download'))) {
                    return { source: 'hidden-input', url: input.value, id: input.id };
                }
            }

            // Check inline scripts
            const scripts = document.querySelectorAll('script:not([src])');
            for (const script of scripts) {
                const text = script.textContent;
                const patterns = [
                    /download_url\s*[:=]\s*['"](https?:\/\/[^'"]+)/,
                    /file_url\s*[:=]\s*['"](https?:\/\/[^'"]+)/,
                    /downloadFile\s*\(\s*['"](https?:\/\/[^'"]+)/,
                ];
                for (const pattern of patterns) {
                    const match = text.match(pattern);
                    if (match) return { source: 'script', url: match[1] };
                }
            }

            return null;
        }""")

        if page_dl_url and page_dl_url.get("url"):
            logger.info("Found download URL: source=%s url=%s", page_dl_url["source"], page_dl_url["url"])
            try:
                async with page.expect_download(timeout=30000) as download_info:
                    await page.goto(page_dl_url["url"])
                download = await download_info.value
                save_path = str(Path(config.download.output_dir) / download.suggested_filename)
                await download.save_as(save_path)
                logger.info("Downloaded: %s", save_path)
                return save_path
            except Exception as e:
                logger.error("Page source download failed: %s", e)

        # Method 4: Click download and watch for navigation/network
        logger.info("Trying click + network monitoring...")
        download_requests = []

        def capture_download_req(request):
            url = request.url
            if any(ext in url.lower() for ext in ['.mp3', '.wav', '.zip', '.flac', '/download']):
                download_requests.append(url)

        page.on("request", capture_download_req)

        # Click all download-like buttons
        await page.evaluate("""() => {
            const btns = document.querySelectorAll('a, button');
            for (const btn of btns) {
                const text = btn.textContent.trim().toLowerCase();
                if (text.includes('download') && !text.includes('top 100')) {
                    btn.click();
                }
            }
        }""")

        await random_delay(5000, 8000)

        page.remove_listener("request", capture_download_req)

        if download_requests:
            logger.info("Captured download URLs from network: %s", download_requests)
            for url in download_requests:
                try:
                    async with page.expect_download(timeout=30000) as download_info:
                        await page.goto(url)
                    download = await download_info.value
                    save_path = str(Path(config.download.output_dir) / download.suggested_filename)
                    await download.save_as(save_path)
                    logger.info("Downloaded from network capture: %s", save_path)
                    return save_path
                except Exception as e:
                    logger.warning("Network capture download failed for %s: %s", url, e)

        logger.error("All download methods failed")
        return None
