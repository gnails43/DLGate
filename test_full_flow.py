"""Full flow test: email (jQuery trigger) + SC OAuth + download.
Tests the complete gate flow on a non-skippable email+SC gate.
"""
import asyncio
import json
import random
import logging
from pathlib import Path

from playwright.async_api import async_playwright

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

TEST_URL = "https://hypeddit.com/spinrealrecords/bijwtfdubtopshelf01"
EMAIL = "gna.k.fujisaki43@gmail.com"
NAME = "Kentaro"
COMMENT = "Great track! 🔥"
PROFILE_DIR = str(Path("C:/GitHub/DLGate/.chrome-profile-test-flow").resolve())


def generate_email_alias(base_email: str) -> str:
    local, domain = base_email.split("@", 1)
    local = local.split("+")[0].replace(".", "")
    if len(local) < 2:
        return base_email
    positions = sorted(random.sample(range(1, len(local)), min(random.randint(1, 3), len(local) - 1)))
    parts, prev = [], 0
    for pos in positions:
        parts.append(local[prev:pos])
        prev = pos
    parts.append(local[prev:])
    return ".".join(parts) + f"@{domain}"


async def main():
    pw = await async_playwright().start()
    logger.info("=== FULL FLOW TEST: email + SC OAuth + download ===")

    Path(PROFILE_DIR).mkdir(parents=True, exist_ok=True)
    ctx = await pw.chromium.launch_persistent_context(
        user_data_dir=PROFILE_DIR,
        headless=False,
        channel="chrome",
        viewport={"width": 1280, "height": 900},
        accept_downloads=True,
        args=["--disable-blink-features=AutomationControlled"],
        ignore_default_args=["--enable-automation"],
    )
    page = ctx.pages[0] if ctx.pages else await ctx.new_page()

    # Track key API responses
    api_log = []

    async def on_response(resp):
        url = resp.url
        kws = ["setGate", "download", "verify", "getGate", "windowopener", "setSC", "Pathway", "auth2"]
        if "hypeddit.com" in url and any(kw in url for kw in kws):
            try:
                body = await resp.text()
            except:
                body = "(unreadable)"
            api_log.append({"status": resp.status, "url": url, "body": body[:500]})
            logger.info("<<< %d %s body=%s", resp.status, url, body[:300])

    page.on("response", on_response)

    # Navigate
    await page.goto(TEST_URL, wait_until="domcontentloaded")
    await asyncio.sleep(3)

    # Clear rate limit cookie
    await page.evaluate("""() => {
        document.cookie = 'teb3456767win=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;';
    }""")

    # Get metadata
    meta = await page.evaluate("""() => {
        const r = {};
        document.querySelectorAll('input[type="hidden"]').forEach(i => {
            if (i.id) r[i.id] = i.value;
        });
        r.csrf = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';
        return r;
    }""")
    gate_id = meta.get("fan_gate_id", "")
    steps = meta.get("steps_select", "")
    csrf = meta.get("csrf", "")
    logger.info("Gate: id=%s steps=%s skippable=%s", gate_id, steps, meta.get("is_skippable"))

    # Activate gate
    await page.evaluate("document.querySelector('#gateDownloadButton')?.click()")
    await asyncio.sleep(3)
    csrf = await page.evaluate("document.querySelector('meta[name=\"csrf-token\"]')?.getAttribute('content') || ''")

    # === STEP 1: EMAIL ===
    logger.info("=== STEP 1: EMAIL ===")

    # Detect current slide
    screen = await page.evaluate("""() => {
        const cur = document.querySelector('.fangate-slider-content.current-slide');
        if (!cur) return 'none';
        if (cur.className.includes('email')) return 'email';
        if (cur.className.includes(' sc ') || cur.className.includes(' sc')) return 'sc';
        if (cur.className.includes('dw')) return 'dw';
        return cur.className;
    }""")
    logger.info("Current screen: %s", screen)

    if screen == "email":
        email = generate_email_alias(EMAIL)
        logger.info("Using email: %s", email)

        # Fill form
        await page.evaluate(f"""() => {{
            const name = document.querySelector('#email_name');
            if (name) {{ name.value = {repr(NAME)}; name.dispatchEvent(new Event('input', {{bubbles:true}})); }}
            const addr = document.querySelector('#email_address');
            if (addr) {{ addr.value = {repr(email)}; addr.dispatchEvent(new Event('input', {{bubbles:true}})); }}
        }}""")
        await asyncio.sleep(1)

        # Click via jQuery trigger (confirmed working in diagnostic)
        click_method = await page.evaluate("""() => {
            if (typeof jQuery !== 'undefined') {
                jQuery('#email_to_downloads_next').trigger('click');
                return 'jquery';
            }
            document.querySelector('#email_to_downloads_next')?.click();
            return 'native';
        }""")
        logger.info("Email click method: %s", click_method)
        await asyncio.sleep(5)

        # Check email API result
        verify_calls = [e for e in api_log if "verifyEmailAddress" in e.get("url", "")]
        if verify_calls:
            logger.info("Email verify result: %s", verify_calls[-1].get("body"))
        else:
            logger.warning("No verifyEmailAddress response captured!")

        # Wait for slide advance
        await asyncio.sleep(2)

    # Check what screen we're on now
    screen = await page.evaluate("""() => {
        const cur = document.querySelector('.fangate-slider-content.current-slide');
        if (!cur) return 'none';
        const cls = cur.className;
        if (cls.includes('email')) return 'email';
        if (cls.includes(' sc') || cls.match(/\\bsc\\b/)) return 'sc';
        if (cls.includes('dw')) return 'dw';
        return cls;
    }""")
    logger.info("After email, screen: %s", screen)

    # If still on email, try to manually advance
    if screen == "email":
        logger.info("Still on email - trying jumpGate to advance...")
        await page.evaluate("""() => {
            const slide = document.querySelector('.fangate-slider-content.email');
            if (slide && typeof jumpGate === 'function') {
                jumpGate(slide, 'submit');
            }
        }""")
        await asyncio.sleep(2)

        # CSS advance fallback
        await page.evaluate("""() => {
            const cur = document.querySelector('.fangate-slider-content.current-slide');
            if (cur && cur.className.includes('email')) {
                cur.classList.remove('current-slide');
                cur.classList.add('move-left');
                // Find SC slide
                const sc = document.querySelector('.fangate-slider-content.sc');
                if (sc) {
                    sc.classList.remove('upcomming-slide');
                    sc.classList.add('current-slide', 'zindex');
                } else {
                    // Find DW slide
                    const dw = document.querySelector('.fangate-slider-content.dw');
                    if (dw) {
                        dw.classList.remove('upcomming-slide');
                        dw.classList.add('current-slide', 'zindex');
                    }
                }
            }
        }""")
        await asyncio.sleep(1)

        screen = await page.evaluate("""() => {
            const cur = document.querySelector('.fangate-slider-content.current-slide');
            if (!cur) return 'none';
            const cls = cur.className;
            if (cls.includes(' sc') || cls.match(/\\bsc\\b/)) return 'sc';
            if (cls.includes('dw')) return 'dw';
            if (cls.includes('email')) return 'email';
            return cls;
        }""")
        logger.info("After manual advance, screen: %s", screen)

    # === STEP 2: SC OAuth ===
    if screen == "sc":
        logger.info("=== STEP 2: SC OAuth ===")

        # Fill comment
        await page.evaluate(f"""() => {{
            const ta = document.querySelector('#sc_comment_text') || document.querySelector('.current-slide textarea');
            if (ta) {{ ta.value = {repr(COMMENT)}; ta.dispatchEvent(new Event('input', {{bubbles:true}})); }}
        }}""")
        await asyncio.sleep(1)

        # Save comment via API
        if gate_id and csrf:
            await page.evaluate(f"""async () => {{
                const fd = new URLSearchParams();
                fd.append('fan_gate_id', '{gate_id}');
                fd.append('comment_sc', {repr(COMMENT)});
                await fetch('/setSC', {{
                    method: 'POST', body: fd.toString(), credentials: 'include',
                    headers: {{
                        'Content-Type': 'application/x-www-form-urlencoded',
                        'X-Requested-With': 'XMLHttpRequest',
                        'X-CSRF-TOKEN': '{csrf}',
                    }},
                }});
            }}""")
            logger.info("SC comment saved")

        # Get OAuth URL
        oauth_url = await page.evaluate("""() => {
            const btns = document.querySelectorAll('#login_to_sc');
            for (const btn of btns) {
                const attr = btn.getAttribute('data-onclick') || btn.getAttribute('onclick') || '';
                const match = attr.match(/PopupCenterDual\\('([^']+)'/);
                if (match) return match[1];
            }
            return null;
        }""")
        logger.info("SC OAuth URL: %s", (oauth_url or "")[:120])

        if oauth_url:
            try:
                async with page.expect_popup(timeout=15000) as popup_info:
                    await page.evaluate(f"window.open('{oauth_url}', 'sc_popup', 'width=800,height=500')")
                popup = await popup_info.value
                await popup.wait_for_load_state("domcontentloaded")
                await asyncio.sleep(3)

                popup_url = popup.url
                popup_text = await popup.evaluate("() => document.body?.innerText || ''")
                logger.info("Popup URL: %s", popup_url)
                logger.info("Popup text (first 200): %s", popup_text[:200])

                # Handle SC OAuth page
                if "soundcloud.com" in popup_url:
                    # Check if auth page (Allow button)
                    auth_btn = await popup.query_selector('#submit_approval')
                    if auth_btn:
                        await auth_btn.click()
                        logger.info("Clicked #submit_approval (Allow)")
                    elif "sign in" in popup_text.lower() or "create" in popup_text.lower():
                        # Login page - try Facebook
                        logger.info("SC login page - trying Facebook button")
                        btns = await popup.query_selector_all('button')
                        for btn in btns:
                            text = await btn.inner_text()
                            if 'facebook' in text.lower():
                                await btn.click()
                                logger.info("Clicked Facebook: %s", text)
                                await asyncio.sleep(5)
                                await popup.wait_for_load_state("domcontentloaded")

                                # Handle FB login
                                if not popup.is_closed():
                                    fb_text = await popup.evaluate("() => document.body?.innerText || ''")
                                    logger.info("FB page text: %s", fb_text[:200])
                                    # Click login/continue
                                    fb_btns = await popup.query_selector_all('div[role="button"], button, input[type="submit"]')
                                    for fb_btn in fb_btns:
                                        try:
                                            t = await fb_btn.inner_text()
                                        except:
                                            t = await fb_btn.get_attribute("value") or ""
                                        if any(kw in t for kw in ["ログイン", "Log in", "Continue", "続行"]):
                                            if "キャンセル" not in t and "cancel" not in t.lower():
                                                await fb_btn.click()
                                                logger.info("Clicked FB: %s", t)
                                                break
                                    await asyncio.sleep(5)
                                break

                # Wait for popup to close (auth2.php callback)
                for i in range(30):
                    await asyncio.sleep(1)
                    if popup.is_closed():
                        logger.info("SC popup closed after %ds", i+1)
                        break
                else:
                    logger.warning("Popup still open after 30s")
                    if not popup.is_closed():
                        try:
                            current_url = popup.url
                            logger.info("Final popup URL: %s", current_url)
                            # Check for auth page one more time
                            auth_btn = await popup.query_selector('#submit_approval')
                            if auth_btn:
                                await auth_btn.click()
                                logger.info("Late click on #submit_approval")
                                await asyncio.sleep(5)
                            await popup.close()
                        except:
                            pass

            except Exception as e:
                logger.error("SC OAuth flow error: %s", e)

            # Call /windowopenerlog
            if gate_id:
                wol_result = await page.evaluate(f"""async () => {{
                    const fd = new URLSearchParams();
                    fd.append('elementID', 'login_to_sc');
                    fd.append('fangate_id', '{gate_id}');
                    const r = await fetch('/windowopenerlog', {{
                        method: 'POST', body: fd.toString(), credentials: 'include',
                        headers: {{
                            'Content-Type': 'application/x-www-form-urlencoded',
                            'X-Requested-With': 'XMLHttpRequest',
                            'X-CSRF-TOKEN': '{csrf}',
                        }},
                    }});
                    return {{ status: r.status, body: (await r.text()).substring(0, 300) }};
                }}""")
                logger.info("/windowopenerlog result: %s", json.dumps(wol_result))

            await asyncio.sleep(3)

    # === Advance to download ===
    logger.info("=== Advancing to download slide ===")

    # CSS advance to DW
    await page.evaluate("""() => {
        // Move all non-dw slides to left
        document.querySelectorAll('.fangate-slider-content').forEach(s => {
            if (!s.className.includes('dw')) {
                s.classList.remove('current-slide', 'upcomming-slide', 'zindex');
                s.classList.add('move-left');
            }
        });
        // Show DW slide
        const dw = document.querySelector('.fangate-slider-content.dw');
        if (dw) {
            dw.classList.remove('upcomming-slide', 'move-left');
            dw.classList.add('current-slide', 'zindex');
        }
    }""")
    await asyncio.sleep(1)

    # === Check pathway status ===
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
    logger.info("getGatePathway before download: %s", json.dumps(pathway))

    # === DOWNLOAD ===
    logger.info("=== DOWNLOAD ATTEMPT ===")
    dl = await page.evaluate(f"""async () => {{
        const fd = new URLSearchParams();
        document.querySelectorAll('input[type="hidden"]').forEach(i => {{
            if (i.name) fd.append(i.name, i.value);
        }});
        // Add skip steps for all step types
        for (const s of ['email', 'sc', 'ig', 'tk', 'sp', 'yt', 'fb', 'tw', 'am']) {{
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
    logger.info("=== DOWNLOAD RESULT: %s ===", json.dumps(dl))

    try:
        dl_body = json.loads(dl.get("body", "{}"))
        dl_status = dl_body.get("download_status")
        dl_url = dl_body.get("URL", "")
        sc = dl_body.get("social_currency")
        logger.info("download_status=%s social_currency=%s URL=%s", dl_status, sc, dl_url[:100] if dl_url else "")

        if dl_status and dl_url:
            logger.info("🎉 DOWNLOAD SUCCESS! URL: %s", dl_url[:200])
        else:
            logger.warning("❌ DOWNLOAD FAILED: social_currency=%s", sc)
    except Exception as e:
        logger.error("Parse error: %s", e)

    # Full API log
    logger.info("=== FULL API LOG (%d) ===", len(api_log))
    for i, e in enumerate(api_log):
        logger.info("  [%d] %d %s body=%s", i, e["status"], e["url"], e.get("body", "")[:200])

    logger.info("Browser open for 20s...")
    await asyncio.sleep(20)
    await ctx.close()
    await pw.stop()


if __name__ == "__main__":
    asyncio.run(main())
