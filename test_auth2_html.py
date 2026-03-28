"""Capture the FULL auth2.php HTML and check window.opener from popup."""
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
PROFILE_DIR = str(Path("C:/GitHub/DLGate/.claude/worktrees/vigilant-ramanujan/.browser_profile").resolve())


def generate_email_alias(base_email: str) -> str:
    local, domain = base_email.split("@", 1)
    local = local.split("+")[0].replace(".", "")
    positions = sorted(random.sample(range(1, len(local)), min(random.randint(1, 3), len(local) - 1)))
    parts, prev = [], 0
    for pos in positions:
        parts.append(local[prev:pos])
        prev = pos
    parts.append(local[prev:])
    return ".".join(parts) + f"@{domain}"


async def main():
    pw = await async_playwright().start()

    import glob, os
    for pat in ["SingletonLock", "SingletonSocket", "SingletonCookie"]:
        for f in glob.glob(os.path.join(PROFILE_DIR, pat)):
            try: os.remove(f)
            except: pass

    ctx = await pw.chromium.launch_persistent_context(
        user_data_dir=PROFILE_DIR, headless=False, channel="chrome",
        viewport={"width": 1280, "height": 900}, accept_downloads=True,
        args=["--disable-blink-features=AutomationControlled"],
        ignore_default_args=["--enable-automation"],
    )
    page = ctx.pages[0] if ctx.pages else await ctx.new_page()

    await page.goto(TEST_URL, wait_until="domcontentloaded")
    await asyncio.sleep(3)
    await page.evaluate("document.cookie='teb3456767win=;expires=Thu,01 Jan 1970 00:00:00 UTC;path=/;'")
    await page.evaluate("document.querySelector('#gateDownloadButton')?.click()")
    await asyncio.sleep(3)

    csrf = await page.evaluate("document.querySelector('meta[name=\"csrf-token\"]')?.getAttribute('content')||''")
    gate_id = await page.evaluate("document.querySelector('#fan_gate_id')?.value||''")

    # Email step
    email = generate_email_alias(EMAIL)
    await page.evaluate(f"""() => {{
        document.querySelector('#email_name').value = {repr(NAME)};
        document.querySelector('#email_address').value = {repr(email)};
    }}""")
    await asyncio.sleep(0.5)
    await page.evaluate("(jQuery||$)('#email_to_downloads_next').trigger('click');")
    await asyncio.sleep(5)

    # Advance to SC
    await page.evaluate("""() => {
        const e = document.querySelector('.fangate-slider-content.email.current-slide');
        if (e) { e.classList.remove('current-slide'); e.classList.add('move-left'); }
        const s = document.querySelector('.fangate-slider-content.sc');
        if (s) { s.classList.remove('upcomming-slide'); s.classList.add('current-slide','zindex'); }
    }""")
    await asyncio.sleep(1)

    # SC comment
    await page.evaluate(f"""async () => {{
        const fd = new URLSearchParams();
        fd.append('fan_gate_id', '{gate_id}');
        fd.append('comment_sc', 'Great track!');
        await fetch('/setSC', {{ method:'POST', body:fd.toString(), credentials:'include',
            headers:{{'Content-Type':'application/x-www-form-urlencoded','X-Requested-With':'XMLHttpRequest','X-CSRF-TOKEN':'{csrf}'}}
        }});
    }}""")

    # Get OAuth URL
    oauth_url = await page.evaluate("""() => {
        const btns = document.querySelectorAll('#login_to_sc');
        for (const b of btns) {
            const a = b.getAttribute('data-onclick')||'';
            const m = a.match(/PopupCenterDual\\('([^']+)'/);
            if (m) return m[1];
        }
        return null;
    }""")
    logger.info("OAuth URL: %s", (oauth_url or "")[:120])

    if not oauth_url:
        logger.error("No OAuth URL found!")
        await ctx.close()
        await pw.stop()
        return

    # Open popup but DON'T let it auto-close - intercept auth2.php
    try:
        async with page.expect_popup(timeout=15000) as popup_info:
            await page.evaluate(f"window.open('{oauth_url}', 'sc_popup', 'width=800,height=600')")
        popup = await popup_info.value
        await popup.wait_for_load_state("domcontentloaded")
        await asyncio.sleep(3)

        # Check window.opener from popup BEFORE OAuth
        opener_check_before = await popup.evaluate("""() => {
            return {
                has_opener: !!window.opener,
                opener_closed: window.opener ? window.opener.closed : null,
                opener_location: null,
            };
        }""")
        logger.info("Popup window.opener BEFORE click: %s", json.dumps(opener_check_before))

        # Click Allow
        auth_btn = await popup.query_selector('#submit_approval')
        if auth_btn:
            # BEFORE clicking, inject code to prevent self.close() so we can inspect
            await popup.evaluate("""() => {
                // Override self.close to capture the moment
                const origClose = window.close.bind(window);
                window.__auth2_html = null;
                window.__close_called = false;
                window.close = function() {
                    window.__close_called = true;
                    window.__auth2_html = document.documentElement.outerHTML;
                    // Still close after a delay
                    setTimeout(origClose, 5000);
                };
            }""")

            await auth_btn.click()
            logger.info("Clicked Allow, waiting for auth2.php redirect...")
            await asyncio.sleep(5)

            # Check if we're now on auth2.php
            if not popup.is_closed():
                popup_url = popup.url
                logger.info("Popup URL after Allow: %s", popup_url[:150])

                # Get the FULL HTML
                try:
                    full_html = await popup.evaluate("() => document.documentElement.outerHTML")
                    # Save to file for inspection
                    with open("auth2_response.html", "w", encoding="utf-8") as f:
                        f.write(full_html)
                    logger.info("Saved auth2 response to auth2_response.html (%d chars)", len(full_html))

                    # Extract inline scripts
                    scripts = await popup.evaluate("""() => {
                        const scripts = [];
                        document.querySelectorAll('script:not([src])').forEach(s => {
                            scripts.push(s.textContent.trim());
                        });
                        return scripts;
                    }""")
                    logger.info("=== INLINE SCRIPTS (%d) ===", len(scripts))
                    for i, s in enumerate(scripts):
                        if s:  # Skip empty scripts
                            logger.info("Script %d (%d chars): %s", i, len(s), s[:500])

                    # Check window.opener
                    opener_check = await popup.evaluate("""() => {
                        try {
                            return {
                                has_opener: !!window.opener,
                                opener_closed: window.opener ? window.opener.closed : null,
                                opener_origin: null,
                                close_called: window.__close_called,
                                auth2_html_captured: !!window.__auth2_html,
                            };
                        } catch(e) {
                            return { error: e.message };
                        }
                    }""")
                    logger.info("window.opener state: %s", json.dumps(opener_check))

                    # Try to access window.opener.document
                    opener_access = await popup.evaluate("""() => {
                        try {
                            if (!window.opener) return 'opener is null';
                            if (window.opener.closed) return 'opener is closed';
                            // Try to read from opener
                            const title = window.opener.document.title;
                            const gateId = window.opener.document.querySelector('#fan_gate_id')?.value;
                            return { title, gateId, accessible: true };
                        } catch(e) {
                            return { error: e.message, accessible: false };
                        }
                    }""")
                    logger.info("window.opener access test: %s", json.dumps(opener_access))

                except Exception as e:
                    logger.error("Failed to read popup: %s", e)

                # Now let the popup close
                try:
                    await popup.evaluate("window.close()")
                except:
                    pass

            # Wait for close
            for _ in range(10):
                await asyncio.sleep(1)
                if popup.is_closed():
                    break

        else:
            logger.error("No Allow button found!")
            popup_text = await popup.evaluate("() => document.body?.innerText || ''")
            logger.info("Popup text: %s", popup_text[:300])

    except Exception as e:
        logger.error("OAuth flow error: %s", e)

    # Now check main page after all this
    await asyncio.sleep(2)

    # Check if anything changed on main page
    after_state = await page.evaluate("""() => {
        const inputs = {};
        document.querySelectorAll('input[type="hidden"]').forEach(i => {
            if (i.name || i.id) inputs[(i.id || i.name)] = i.value;
        });
        // Check for sc-specific inputs
        const scInputs = {};
        document.querySelectorAll('input').forEach(i => {
            if ((i.name || '').includes('sc') || (i.id || '').includes('sc')) {
                scInputs[(i.id || i.name)] = i.value;
            }
        });
        return { total_hidden: Object.keys(inputs).length, sc_inputs: scInputs };
    }""")
    logger.info("Main page state after OAuth: %s", json.dumps(after_state))

    # Download attempt
    dl = await page.evaluate(f"""async () => {{
        const fd = new URLSearchParams();
        document.querySelectorAll('input[type="hidden"]').forEach(i => {{
            if (i.name) fd.append(i.name, i.value);
        }});
        for (const s of ['email','sc']) fd.append('skip_gate_steps[]', s);
        const r = await fetch('/gate/download/ul', {{ method:'POST', body:fd.toString(), credentials:'include',
            headers:{{'Content-Type':'application/x-www-form-urlencoded','X-Requested-With':'XMLHttpRequest','X-CSRF-TOKEN':'{csrf}'}}
        }});
        return {{ status:r.status, body:(await r.text()).substring(0,500) }};
    }}""")
    logger.info("DOWNLOAD: %s", json.dumps(dl))

    await asyncio.sleep(10)
    await ctx.close()
    await pw.stop()


if __name__ == "__main__":
    asyncio.run(main())
