"""Full flow test using REAL browser profile (SC/FB already logged in).
Tests email (jQuery trigger fix) + SC OAuth + download.
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
COMMENT = "Great track!"
# Use the REAL DLGate browser profile
PROFILE_DIR = str(Path("C:/GitHub/DLGate/.claude/worktrees/vigilant-ramanujan/.browser_profile").resolve())


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
    logger.info("=== REAL PROFILE TEST: email (jQuery trigger) + SC OAuth + download ===")
    logger.info("Profile: %s", PROFILE_DIR)

    Path(PROFILE_DIR).mkdir(parents=True, exist_ok=True)

    # Clean lock files
    import glob, os
    for pat in ["SingletonLock", "SingletonSocket", "SingletonCookie"]:
        for f in glob.glob(os.path.join(PROFILE_DIR, pat)):
            try: os.remove(f)
            except: pass

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

    api_log = []

    async def on_response(resp):
        url = resp.url
        kws = ["setGate", "download/ul", "verifyEmail", "getGatePathway", "windowopener", "setSC", "auth2"]
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

    # Process each step based on current screen
    for iteration in range(10):
        screen = await page.evaluate("""() => {
            const cur = document.querySelector('.fangate-slider-content.current-slide');
            if (!cur) return 'none';
            const cls = cur.className;
            const tokens = cls.split(/\\s+/);
            if (tokens.includes('dw')) return 'dw';
            if (tokens.includes('email')) return 'email';
            if (tokens.includes('sc')) return 'sc';
            for (const t of ['ig','tk','sp','yt','fb','tw','am']) {
                if (tokens.includes(t)) return t;
            }
            return 'unknown:' + cls;
        }""")
        logger.info("--- Iteration %d: screen=%s ---", iteration, screen)

        if screen == "email":
            email = generate_email_alias(EMAIL)
            logger.info("Email: %s", email)

            await page.evaluate(f"""() => {{
                const name = document.querySelector('#email_name');
                if (name) {{ name.value = {repr(NAME)}; name.dispatchEvent(new Event('input', {{bubbles:true}})); }}
                const addr = document.querySelector('#email_address');
                if (addr) {{ addr.value = {repr(email)}; addr.dispatchEvent(new Event('input', {{bubbles:true}})); }}
            }}""")
            await asyncio.sleep(1)

            # jQuery trigger (confirmed working)
            await page.evaluate("""() => {
                (jQuery || $)('#email_to_downloads_next').trigger('click');
            }""")
            logger.info("Email: jQuery trigger click")
            await asyncio.sleep(5)

            # Check result
            verify = [e for e in api_log if "verifyEmail" in e.get("url", "")]
            if verify:
                logger.info("Email verify: %s", verify[-1].get("body"))
            else:
                logger.warning("No verifyEmailAddress response!")

            # Try to advance slide
            new_screen = await page.evaluate("""() => {
                const cur = document.querySelector('.fangate-slider-content.current-slide');
                return cur ? cur.className : 'none';
            }""")
            if "email" in new_screen:
                logger.info("Still on email, advancing via CSS")
                await page.evaluate("""() => {
                    const cur = document.querySelector('.fangate-slider-content.email.current-slide');
                    if (cur) {
                        cur.classList.remove('current-slide');
                        cur.classList.add('move-left');
                    }
                    // Find next slide in steps order
                    const steps = (document.querySelector('#steps_select')?.value || '').split(',');
                    const emailIdx = steps.indexOf('email');
                    for (let i = emailIdx + 1; i < steps.length; i++) {
                        const next = document.querySelector('.fangate-slider-content.' + steps[i]);
                        if (next) {
                            next.classList.remove('upcomming-slide');
                            next.classList.add('current-slide', 'zindex');
                            break;
                        }
                    }
                }""")
                await asyncio.sleep(1)

        elif screen == "sc":
            logger.info("SC OAuth step")

            # Fill comment
            await page.evaluate(f"""() => {{
                const ta = document.querySelector('#sc_comment_text') || document.querySelector('.current-slide textarea');
                if (ta) {{ ta.value = {repr(COMMENT)}; ta.dispatchEvent(new Event('input', {{bubbles:true}})); }}
            }}""")

            # Save comment
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
            logger.info("OAuth URL: %s", (oauth_url or "")[:120])

            if oauth_url:
                popup = None
                try:
                    async with page.expect_popup(timeout=15000) as popup_info:
                        await page.evaluate(f"window.open('{oauth_url}', 'sc_popup', 'width=800,height=500')")
                    popup = await popup_info.value
                    await popup.wait_for_load_state("domcontentloaded")
                    await asyncio.sleep(3)

                    # Handle popup
                    for check in range(15):
                        if popup.is_closed():
                            logger.info("Popup closed after %ds (auth complete)", check * 2)
                            break

                        popup_url = popup.url
                        popup_text = await popup.evaluate("() => document.body?.innerText || ''")
                        logger.info("Popup check %d: url=%s text=%s", check, popup_url[:80], popup_text[:100])

                        if "soundcloud.com" in popup_url:
                            # Try Allow button first
                            auth_btn = await popup.query_selector('#submit_approval')
                            if auth_btn:
                                await auth_btn.click()
                                logger.info("Clicked Allow (#submit_approval)")
                                await asyncio.sleep(3)
                                continue

                            # Check for login page
                            if "sign in" in popup_text.lower():
                                logger.info("SC login page - clicking Continue with Facebook")
                                btns = await popup.query_selector_all('button')
                                for btn in btns:
                                    text = await btn.inner_text()
                                    if 'facebook' in text.lower():
                                        await btn.click()
                                        await asyncio.sleep(5)
                                        break

                        elif "facebook.com" in popup_url:
                            logger.info("On Facebook page")
                            # Try clicking login/continue buttons
                            fb_btns = await popup.query_selector_all('div[role="button"], button, input[type="submit"]')
                            for fb_btn in fb_btns:
                                try:
                                    t = await fb_btn.inner_text()
                                except:
                                    t = await fb_btn.get_attribute("value") or ""
                                if any(kw in t for kw in ["ログイン", "Log in", "Continue", "続行"]):
                                    if "キャンセル" not in t and "cancel" not in t.lower():
                                        await fb_btn.click()
                                        logger.info("Clicked FB: %s", t.strip())
                                        break
                            await asyncio.sleep(5)

                        elif "hypeddit.com" in popup_url:
                            logger.info("Redirected to Hypeddit (auth2.php callback)")
                            await asyncio.sleep(2)
                            # auth2.php should auto-close

                        await asyncio.sleep(2)

                except Exception as e:
                    logger.error("SC OAuth error: %s", e)

                if popup and not popup.is_closed():
                    try:
                        logger.info("Force closing popup. URL: %s", popup.url)
                        await popup.close()
                    except:
                        pass

                # Call /windowopenerlog
                if gate_id:
                    wol = await page.evaluate(f"""async () => {{
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
                    logger.info("/windowopenerlog: %s", json.dumps(wol))

                await asyncio.sleep(2)

            # Advance to next slide
            await page.evaluate("""() => {
                const cur = document.querySelector('.fangate-slider-content.sc.current-slide');
                if (cur) {
                    cur.classList.remove('current-slide');
                    cur.classList.add('move-left');
                }
                const steps = (document.querySelector('#steps_select')?.value || '').split(',');
                const scIdx = steps.indexOf('sc');
                for (let i = scIdx + 1; i < steps.length; i++) {
                    const next = document.querySelector('.fangate-slider-content.' + steps[i]);
                    if (next) {
                        next.classList.remove('upcomming-slide');
                        next.classList.add('current-slide', 'zindex');
                        break;
                    }
                }
                // If no next found, show dw
                const dw = document.querySelector('.fangate-slider-content.dw');
                if (dw && !document.querySelector('.fangate-slider-content.current-slide')) {
                    dw.classList.add('current-slide', 'zindex');
                }
            }""")
            await asyncio.sleep(1)

        elif screen == "dw":
            logger.info("=== DOWNLOAD SLIDE REACHED ===")

            # Check pathway
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
            logger.info("getGatePathway: %s", json.dumps(pathway))

            # Try download
            dl = await page.evaluate(f"""async () => {{
                const fd = new URLSearchParams();
                document.querySelectorAll('input[type="hidden"]').forEach(i => {{
                    if (i.name) fd.append(i.name, i.value);
                }});
                for (const s of ['email', 'sc']) {{
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
            logger.info("=== DOWNLOAD: %s ===", json.dumps(dl))

            try:
                body = json.loads(dl.get("body", "{}"))
                logger.info("download_status=%s social_currency=%s URL=%s",
                            body.get("download_status"), body.get("social_currency"),
                            (body.get("URL") or "")[:100])
                if body.get("download_status") and body.get("URL"):
                    logger.info("SUCCESS! Download URL obtained!")
                else:
                    logger.warning("FAILED: download_status=%s", body.get("download_status"))
            except:
                pass
            break

        elif screen in ("ig", "tk", "sp", "yt", "fb", "tw", "am"):
            logger.info("Social step: %s (clicking through)", screen)
            await page.evaluate(f"""() => {{
                const cur = document.querySelector('.current-slide');
                if (cur) {{
                    const btns = cur.querySelectorAll('a.hype-btn, a.hype-btn-green');
                    btns.forEach(b => {{ if (!b.id.includes('skipper')) b.click(); }});
                }}
            }}""")
            await asyncio.sleep(3)
            # Close extra tabs
            for p in ctx.pages:
                if p != page:
                    try: await p.close()
                    except: pass
            # Skip
            await page.evaluate(f"""() => {{
                const sk = document.querySelector('#skipper_{screen}_channel') ||
                           document.querySelector('.current-slide [id*="skipper"]');
                if (sk) sk.click();
            }}""")
            await asyncio.sleep(2)

        elif screen == "none":
            await page.evaluate("document.querySelector('#gateDownloadButton')?.click()")
            await asyncio.sleep(3)

        else:
            logger.warning("Unknown: %s", screen)
            break

    # Full API log
    logger.info("=== API LOG (%d) ===", len(api_log))
    for i, e in enumerate(api_log):
        logger.info("  [%d] %d %s body=%s", i, e["status"], e["url"], e.get("body", "")[:200])

    logger.info("Browser open for 15s...")
    await asyncio.sleep(15)
    await ctx.close()
    await pw.stop()


if __name__ == "__main__":
    asyncio.run(main())
