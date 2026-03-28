"""Diagnostic test: Mobile UA vs Desktop UA for email+SC gates.

Tests whether mobile user agent makes jumpGate() call /setGatePathwayOr
and whether that fixes the download_status:false issue.
"""
import asyncio
import json
import random
import logging
from pathlib import Path

from playwright.async_api import async_playwright

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# iPhone UA - matches jumpGate()'s check for "iPhone"
MOBILE_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 "
    "Mobile/15E148 Safari/604.1"
)

TEST_URL = "https://hypeddit.com/spinrealrecords/bijwtfdubtopshelf01"
EMAIL = "gna.k.fujisaki43@gmail.com"
NAME = "Kentaro"
PROFILE_DIR = str(Path("C:/GitHub/DLGate/.chrome-profile-test-mobile").resolve())

# All API calls captured
api_log = []


def generate_email_alias(base_email: str) -> str:
    local, domain = base_email.split("@", 1)
    local = local.split("+")[0].replace(".", "")
    if len(local) < 2:
        return base_email
    positions = sorted(random.sample(range(1, len(local)), min(random.randint(1, 3), len(local) - 1)))
    parts = []
    prev = 0
    for pos in positions:
        parts.append(local[prev:pos])
        prev = pos
    parts.append(local[prev:])
    return ".".join(parts) + f"@{domain}"


async def main():
    pw = await async_playwright().start()

    logger.info("=== TEST: Mobile UA on email+SC gate ===")
    logger.info("URL: %s", TEST_URL)
    logger.info("UA: %s", MOBILE_UA)

    Path(PROFILE_DIR).mkdir(parents=True, exist_ok=True)

    ctx = await pw.chromium.launch_persistent_context(
        user_data_dir=PROFILE_DIR,
        headless=False,
        channel="chrome",
        user_agent=MOBILE_UA,
        viewport={"width": 390, "height": 844},  # iPhone viewport
        accept_downloads=True,
        args=["--disable-blink-features=AutomationControlled"],
        ignore_default_args=["--enable-automation"],
    )

    page = ctx.pages[0] if ctx.pages else await ctx.new_page()

    # Capture ALL network requests/responses
    async def on_request(req):
        if "hypeddit.com" in req.url and not any(ext in req.url for ext in [".css", ".js", ".png", ".jpg", ".gif", ".ico", ".svg", ".woff"]):
            entry = {"type": "req", "method": req.method, "url": req.url, "data": req.post_data}
            api_log.append(entry)
            if any(kw in req.url for kw in ["setGate", "download", "verify", "getGate", "windowopener", "setSC", "auth2"]):
                logger.info(">>> API REQ: %s %s data=%s", req.method, req.url, req.post_data)

    async def on_response(resp):
        url = resp.url
        if "hypeddit.com" in url and any(kw in url for kw in ["setGate", "download", "verify", "getGate", "windowopener", "setSC", "auth2", "Pathway"]):
            try:
                body = await resp.text()
            except:
                body = "(could not read)"
            entry = {"type": "resp", "status": resp.status, "url": url, "body": body[:500]}
            api_log.append(entry)
            logger.info("<<< API RESP: %d %s body=%s", resp.status, url, body[:300])

    page.on("request", on_request)
    page.on("response", on_response)

    # Navigate to gate
    logger.info("Navigating to gate...")
    await page.goto(TEST_URL, wait_until="domcontentloaded")
    await asyncio.sleep(3)

    # Clear email rate limit cookie
    await page.evaluate("""() => {
        document.cookie = 'teb3456767win=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;';
    }""")

    # Take screenshot
    await page.screenshot(path="test_mobile_01_loaded.png")
    logger.info("Screenshot: test_mobile_01_loaded.png")

    # Extract gate metadata
    meta = await page.evaluate("""() => {
        const result = {};
        const inputs = document.querySelectorAll('input[type="hidden"]');
        for (const i of inputs) {
            if (i.id) result[i.id] = i.value;
        }
        result.jumpGate_exists = typeof jumpGate === 'function';
        if (typeof jumpGate === 'function') {
            result.jumpGate_source = jumpGate.toString().substring(0, 500);
        }
        // Check what UA jumpGate sees
        result.navigator_ua = navigator.userAgent;
        result.is_mobile_check = /FBMD|Instagram|Android|iPhone|musical_ly/i.test(navigator.userAgent);
        return result;
    }""")
    logger.info("Gate metadata: %s", json.dumps(meta, indent=2, ensure_ascii=False))

    gate_id = meta.get("fan_gate_id")
    steps = meta.get("steps_select", "")
    logger.info("Gate ID: %s, Steps: %s", gate_id, steps)
    logger.info("Mobile UA detected by jumpGate: %s", meta.get("is_mobile_check"))

    # Click Download button
    logger.info("Clicking Download button...")
    await page.evaluate("""() => {
        const btn = document.querySelector('#gateDownloadButton');
        if (btn) btn.click();
    }""")
    await asyncio.sleep(3)
    await page.screenshot(path="test_mobile_02_after_dl_click.png")

    # Re-extract metadata (CSRF token may now be available)
    meta2 = await page.evaluate("""() => {
        const result = {};
        const csrfMeta = document.querySelector('meta[name="csrf-token"]');
        if (csrfMeta) result.csrf = csrfMeta.getAttribute('content');
        const csrfInput = document.querySelector('input[name="_token"]');
        if (csrfInput) result.csrf_input = csrfInput.value;
        // Current slide
        const cur = document.querySelector('.fangate-slider-content.current-slide');
        if (cur) result.current_slide = cur.className;
        // All slides
        const slides = document.querySelectorAll('.fangate-slider-content');
        result.all_slides = Array.from(slides).map(s => s.className);
        return result;
    }""")
    logger.info("After activate: %s", json.dumps(meta2, indent=2))
    csrf = meta2.get("csrf") or meta2.get("csrf_input") or ""

    # Detect current step
    current_slide = meta2.get("current_slide", "")
    logger.info("Current slide: %s", current_slide)

    # Process steps based on what's visible
    # We'll loop through slides
    for iteration in range(10):
        state = await page.evaluate("""() => {
            const cur = document.querySelector('.fangate-slider-content.current-slide');
            if (!cur) return {screen: 'none', cls: ''};
            const cls = cur.className;
            const tokens = cls.split(/\\s+/);
            if (tokens.includes('dw')) return {screen: 'download', cls};
            if (tokens.includes('email')) return {screen: 'email', cls};
            if (tokens.includes('sc')) return {screen: 'sc', cls};
            for (const t of ['ig','tk','sp','yt','fb','tw','am']) {
                if (tokens.includes(t)) return {screen: t, cls};
            }
            return {screen: 'unknown', cls};
        }""")
        screen = state["screen"]
        logger.info("=== Iteration %d: screen=%s ===", iteration, screen)
        await page.screenshot(path=f"test_mobile_{iteration+3:02d}_{screen}.png")

        if screen == "email":
            logger.info("--- Handling EMAIL step ---")
            email = generate_email_alias(EMAIL)
            logger.info("Using email: %s", email)

            # Fill email fields via JS
            await page.evaluate(f"""() => {{
                const name = document.querySelector('#email_name');
                if (name) {{ name.value = {repr(NAME)}; name.dispatchEvent(new Event('input', {{bubbles:true}})); }}
                const addr = document.querySelector('#email_address');
                if (addr) {{ addr.value = {repr(email)}; addr.dispatchEvent(new Event('input', {{bubbles:true}})); }}
            }}""")
            await asyncio.sleep(1)

            # Click submit button - let jQuery handler call /verifyEmailAddress
            await page.evaluate("""() => {
                const btn = document.querySelector('#email_to_downloads_next');
                if (btn) btn.click();
            }""")
            logger.info("Clicked email submit, waiting for jQuery handler...")
            await asyncio.sleep(5)

            # Check if jumpGate was called (on mobile it should call /setGatePathwayOr)
            logger.info("Checking API log for setGatePathwayOr calls...")
            sgpo_calls = [e for e in api_log if "setGatePathwayOr" in e.get("url", "")]
            logger.info("setGatePathwayOr calls so far: %d", len(sgpo_calls))
            for c in sgpo_calls:
                logger.info("  %s", c)

        elif screen == "sc":
            logger.info("--- Handling SC step ---")
            # Fill comment
            await page.evaluate("""() => {
                const ta = document.querySelector('#sc_comment_text') || document.querySelector('textarea');
                if (ta) { ta.value = 'Great track!'; ta.dispatchEvent(new Event('input', {bubbles:true})); }
            }""")
            await asyncio.sleep(1)

            # Save SC comment via API
            if gate_id and csrf:
                await page.evaluate(f"""async () => {{
                    const fd = new URLSearchParams();
                    fd.append('fan_gate_id', '{gate_id}');
                    fd.append('comment_sc', 'Great track!');
                    await fetch('/setSC', {{
                        method: 'POST', body: fd.toString(), credentials: 'include',
                        headers: {{
                            'Content-Type': 'application/x-www-form-urlencoded',
                            'X-Requested-With': 'XMLHttpRequest',
                            'X-CSRF-TOKEN': '{csrf}',
                        }},
                    }});
                }}""")

            # Extract OAuth URL
            oauth_url = await page.evaluate("""() => {
                const btns = document.querySelectorAll('#login_to_sc');
                for (const btn of btns) {
                    const attr = btn.getAttribute('data-onclick') || btn.getAttribute('onclick') || '';
                    const match = attr.match(/PopupCenterDual\\('([^']+)'/);
                    if (match) return match[1];
                }
                return null;
            }""")
            logger.info("SC OAuth URL: %s", oauth_url)

            if oauth_url:
                # Open popup
                try:
                    async with page.expect_popup(timeout=10000) as popup_info:
                        await page.evaluate(f"window.open('{oauth_url}', 'sc_popup', 'width=800,height=500')")
                    popup = await popup_info.value
                    await popup.wait_for_load_state("domcontentloaded")
                    await asyncio.sleep(3)

                    popup_text = await popup.evaluate("() => document.body?.innerText || ''")
                    logger.info("Popup text (first 200): %s", popup_text[:200])

                    # Try clicking Allow (#submit_approval)
                    auth_btn = await popup.query_selector('#submit_approval')
                    if auth_btn:
                        await auth_btn.click()
                        logger.info("Clicked #submit_approval")
                    else:
                        # Try other buttons
                        logger.info("No #submit_approval found, checking for login...")
                        # Check for FB login
                        btns = await popup.query_selector_all('button')
                        for btn in btns:
                            text = await btn.inner_text()
                            if 'facebook' in text.lower():
                                await btn.click()
                                logger.info("Clicked Facebook button: %s", text)
                                await asyncio.sleep(5)
                                break

                    # Wait for popup to close
                    for _ in range(20):
                        await asyncio.sleep(1)
                        if popup.is_closed():
                            logger.info("SC popup closed")
                            break
                    else:
                        logger.warning("SC popup did not close after 20s")
                        try:
                            await popup.close()
                        except:
                            pass

                except Exception as e:
                    logger.error("SC OAuth failed: %s", e)

                # Call /windowopenerlog
                if gate_id:
                    await page.evaluate(f"""async () => {{
                        const fd = new URLSearchParams();
                        fd.append('elementID', 'login_to_sc');
                        fd.append('fangate_id', '{gate_id}');
                        await fetch('/windowopenerlog', {{
                            method: 'POST', body: fd.toString(), credentials: 'include',
                            headers: {{
                                'Content-Type': 'application/x-www-form-urlencoded',
                                'X-Requested-With': 'XMLHttpRequest',
                                'X-CSRF-TOKEN': '{csrf}',
                            }},
                        }});
                    }}""")
                    logger.info("Called /windowopenerlog")

                await asyncio.sleep(3)

            # Check if jumpGate was auto-called on mobile
            sgpo_calls = [e for e in api_log if "setGatePathwayOr" in e.get("url", "")]
            logger.info("setGatePathwayOr calls after SC: %d", len(sgpo_calls))
            for c in sgpo_calls:
                logger.info("  %s", c)

            # Try clicking next/skipper
            await page.evaluate("""() => {
                const skipper = document.querySelector('#skipper_sc_channel') ||
                                document.querySelector('.current-slide [id*="skipper"]');
                if (skipper) { skipper.click(); return 'clicked skipper'; }
                return 'no skipper';
            }""")
            await asyncio.sleep(3)

        elif screen == "download":
            logger.info("--- DOWNLOAD STEP ---")

            # Check getGatePathway BEFORE download
            pathway = await page.evaluate(f"""async () => {{
                const fd = new URLSearchParams();
                fd.append('fan_gate_id', '{gate_id}');
                const r = await fetch('/getGatePathway', {{
                    method: 'POST', body: fd.toString(), credentials: 'include',
                    headers: {{
                        'Content-Type': 'application/x-www-form-urlencoded',
                        'X-Requested-With': 'XMLHttpRequest',
                        'X-CSRF-TOKEN': '{csrf}',
                    }},
                }});
                return await r.json();
            }}""")
            logger.info("getGatePathway BEFORE download: %s", json.dumps(pathway))

            # If steps not complete, manually call /setGatePathwayOr for each
            completed = set(pathway.get("skip_gate_steps", []) if isinstance(pathway.get("skip_gate_steps"), list) else [])
            step_types = [s for s in steps.split(",") if s and s != "dw"]
            missing = [s for s in step_types if s not in completed]

            if missing:
                logger.info("Missing steps: %s, calling /setGatePathwayOr for each", missing)
                for step in missing:
                    result = await page.evaluate(f"""async () => {{
                        const fd = new URLSearchParams();
                        fd.append('fan_gate_id', '{gate_id}');
                        fd.append('skipSteps[]', '{step}');
                        fd.append('selectedStep', '{step}');
                        const r = await fetch('/setGatePathwayOr', {{
                            method: 'POST', body: fd.toString(), credentials: 'include',
                            headers: {{
                                'Content-Type': 'application/x-www-form-urlencoded',
                                'X-Requested-With': 'XMLHttpRequest',
                                'X-CSRF-TOKEN': '{csrf}',
                            }},
                        }});
                        return {{ status: r.status, body: (await r.text()).substring(0, 300) }};
                    }}""")
                    logger.info("setGatePathwayOr(%s): %s", step, json.dumps(result))

                # Re-check pathway
                pathway2 = await page.evaluate(f"""async () => {{
                    const fd = new URLSearchParams();
                    fd.append('fan_gate_id', '{gate_id}');
                    const r = await fetch('/getGatePathway', {{
                        method: 'POST', body: fd.toString(), credentials: 'include',
                        headers: {{
                            'Content-Type': 'application/x-www-form-urlencoded',
                            'X-Requested-With': 'XMLHttpRequest',
                            'X-CSRF-TOKEN': '{csrf}',
                        }},
                    }});
                    return await r.json();
                }}""")
                logger.info("getGatePathway AFTER setGatePathwayOr: %s", json.dumps(pathway2))

            # Try download
            dl_result = await page.evaluate(f"""async () => {{
                // Collect all hidden inputs
                const inputs = {{}};
                document.querySelectorAll('input[type="hidden"]').forEach(i => {{
                    if (i.name) inputs[i.name] = i.value;
                }});

                const fd = new URLSearchParams();
                for (const [k, v] of Object.entries(inputs)) {{
                    fd.append(k, v);
                }}
                // Ensure skip_gate_steps are included
                const stepTypes = ['email', 'sc', 'ig', 'tk', 'sp', 'yt', 'fb', 'tw', 'am'];
                for (const s of stepTypes) {{
                    if (!fd.getAll('skip_gate_steps[]').includes(s)) {{
                        fd.append('skip_gate_steps[]', s);
                    }}
                }}

                const r = await fetch('/gate/download/ul', {{
                    method: 'POST', body: fd.toString(), credentials: 'include',
                    headers: {{
                        'Content-Type': 'application/x-www-form-urlencoded',
                        'X-Requested-With': 'XMLHttpRequest',
                        'X-CSRF-TOKEN': '{csrf}',
                    }},
                }});
                return {{ status: r.status, body: (await r.text()).substring(0, 500) }};
            }}""")
            logger.info("=== DOWNLOAD RESULT: %s ===", json.dumps(dl_result))

            # Parse download response
            try:
                dl_body = json.loads(dl_result.get("body", "{}"))
                logger.info("download_status: %s", dl_body.get("download_status"))
                logger.info("social_currency: %s", dl_body.get("social_currency"))
                logger.info("URL: %s", dl_body.get("URL"))
            except:
                pass

            break

        elif screen in ("ig", "tk", "sp", "yt", "fb", "tw", "am"):
            logger.info("--- Social step: %s ---", screen)
            # Click action buttons
            await page.evaluate(f"""() => {{
                const cur = document.querySelector('.current-slide');
                if (!cur) return;
                const links = cur.querySelectorAll('a.hype-btn, a.hype-btn-green, a.hype-btn-social');
                for (const l of links) {{
                    if (!l.id.includes('skipper')) l.click();
                }}
            }}""")
            await asyncio.sleep(3)
            # Close any new tabs
            pages = ctx.pages
            for p in pages:
                if p != page:
                    try: await p.close()
                    except: pass
            # Click skipper
            await page.evaluate(f"""() => {{
                const sk = document.querySelector('#skipper_{screen}_channel') ||
                           document.querySelector('.current-slide [id*="skipper"]');
                if (sk) sk.click();
            }}""")
            await asyncio.sleep(3)

        elif screen == "none":
            # Try clicking download button
            await page.evaluate("""() => {
                const btn = document.querySelector('#gateDownloadButton');
                if (btn) btn.click();
            }""")
            await asyncio.sleep(3)

        else:
            logger.warning("Unknown screen: %s, trying to advance", screen)
            await page.evaluate("""() => {
                const cur = document.querySelector('.current-slide');
                if (cur && typeof jumpGate === 'function') jumpGate(cur, 'skip');
            }""")
            await asyncio.sleep(3)

    # Dump full API log
    logger.info("=== FULL API LOG (%d entries) ===", len(api_log))
    for i, entry in enumerate(api_log):
        if entry["type"] == "req":
            logger.info("  [%d] >>> %s %s data=%s", i, entry["method"], entry["url"], entry.get("data"))
        else:
            logger.info("  [%d] <<< %d %s body=%s", i, entry["status"], entry["url"], entry.get("body", "")[:200])

    # Keep browser open for inspection
    logger.info("=== Test complete. Browser stays open for 30s ===")
    await asyncio.sleep(30)

    await ctx.close()
    await pw.stop()


if __name__ == "__main__":
    asyncio.run(main())
