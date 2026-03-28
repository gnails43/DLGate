"""Test: Let popup flow COMPLETELY naturally - no interception at all.
The popup's auth2.php may use the state parameter to update the main session.
"""
import asyncio
import json
import logging
from pathlib import Path

from playwright.async_api import async_playwright

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

SC_ONLY_URL = "https://hypeddit.com/lukewaveblackzushi/nacho"  # SC-only gate
PROFILE_DIR = str(Path("C:/GitHub/DLGate/.claude/worktrees/vigilant-ramanujan/.browser_profile").resolve())


async def main():
    pw = await async_playwright().start()
    logger.info("=== NATURAL FLOW: No interception ===")

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

    # Track auth2.php requests/responses
    async def on_request(req):
        if "auth2" in req.url:
            headers = dict(req.headers)
            has_session = "laravel_session" in headers.get("cookie", "")
            logger.info("auth2 REQUEST: url=%s has_session=%s", req.url[:100], has_session)

    async def on_response(resp):
        if "auth2" in resp.url:
            all_h = await resp.all_headers()
            logger.info("auth2 RESPONSE: status=%d url=%s", resp.status, resp.url[:80])
            # Check for set-cookie
            sc = all_h.get("set-cookie", "")
            if sc:
                logger.info("  Set-Cookie: %s", sc[:200])
            # Check for location (redirect)
            loc = all_h.get("location", "")
            if loc:
                logger.info("  Location: %s", loc[:200])

    ctx.on("request", on_request)
    ctx.on("response", on_response)

    # Load gate
    await page.goto(SC_ONLY_URL, wait_until="domcontentloaded")
    await asyncio.sleep(3)
    await page.evaluate("document.cookie='teb3456767win=;expires=Thu,01 Jan 1970 00:00:00 UTC;path=/;'")

    gate_id = await page.evaluate("document.querySelector('#fan_gate_id')?.value||''")
    csrf = await page.evaluate("document.querySelector('meta[name=\"csrf-token\"]')?.getAttribute('content')||''")
    steps = await page.evaluate("document.querySelector('#steps_select')?.value||''")
    comment_sc = await page.evaluate("document.querySelector('#comment_sc')?.value||''")
    logger.info("Gate: id=%s steps=%s comment_sc=%s", gate_id, steps, comment_sc)

    # Activate
    await page.evaluate("document.querySelector('#gateDownloadButton')?.click()")
    await asyncio.sleep(3)
    csrf = await page.evaluate("document.querySelector('meta[name=\"csrf-token\"]')?.getAttribute('content')||''")

    # Set SC comment if needed
    if comment_sc == '1':
        await page.evaluate(f"""async () => {{
            const fd = new URLSearchParams();
            fd.append('fan_gate_id', '{gate_id}');
            fd.append('comment_sc', 'Great track!');
            await fetch('/setSC', {{ method:'POST', body:fd.toString(), credentials:'include',
                headers:{{'Content-Type':'application/x-www-form-urlencoded','X-Requested-With':'XMLHttpRequest','X-CSRF-TOKEN':'{csrf}'}}
            }});
        }}""")
        await page.evaluate("$('#sc_comment_text').val('Great track!')")

    # Get session BEFORE OAuth
    cookies = await ctx.cookies("https://hypeddit.com")
    session = [c for c in cookies if c["name"] == "laravel_session"]
    logger.info("Session BEFORE OAuth: %s", session[0]["value"][:40] if session else "NONE")

    # Get OAuth URL and open popup NATURALLY
    oauth_url = await page.evaluate("""() => {
        const b = document.querySelectorAll('#login_to_sc');
        for (const btn of b) {
            const a = btn.getAttribute('data-onclick')||'';
            const m = a.match(/PopupCenterDual\\('([^']+)'/);
            if (m) return m[1];
        }
        return null;
    }""")

    if oauth_url:
        logger.info("Opening popup NATURALLY (no interception)...")
        try:
            async with page.expect_popup(timeout=15000) as pi:
                await page.evaluate(f"window.open('{oauth_url}', 'sc', 'width=800,height=600')")
            popup = await pi.value

            # NO ROUTE INTERCEPTION - let everything flow naturally
            await popup.wait_for_load_state("domcontentloaded")
            await asyncio.sleep(3)

            # Click Allow if visible
            auth_btn = await popup.query_selector('#submit_approval')
            if auth_btn:
                await auth_btn.click()
                logger.info("Clicked Allow")
            else:
                text = await popup.evaluate("document.body?.innerText || ''")
                logger.info("No Allow button. Page: %s", text[:200])

            # Wait for popup to close (auth2.php's JS should close it)
            for i in range(30):
                await asyncio.sleep(1)
                if popup.is_closed():
                    logger.info("Popup closed naturally after %ds", i+1)
                    break
                # Check what's on the popup
                try:
                    url = popup.url
                    if "auth2" in url:
                        text = await popup.evaluate("document.body?.innerText || ''")
                        logger.info("Popup on auth2.php: %s", text[:100])
                except:
                    break
            else:
                logger.warning("Popup didn't close after 30s")
                try:
                    text = await popup.evaluate("document.body?.innerText || ''")
                    logger.info("Popup final text: %s", text[:200])
                    await popup.close()
                except:
                    pass

        except Exception as e:
            logger.error("OAuth: %s", e)

    await asyncio.sleep(2)

    # Get session AFTER OAuth
    cookies = await ctx.cookies("https://hypeddit.com")
    session = [c for c in cookies if c["name"] == "laravel_session"]
    logger.info("Session AFTER OAuth: %s", session[0]["value"][:40] if session else "NONE")

    # Check if localStorage was set
    hype_child = await page.evaluate("localStorage.getItem('hypeChildWindow') || 'NOT SET'")
    logger.info("localStorage.hypeChildWindow: %s", hype_child)

    # Check slide state (did auth2.php's JS change anything?)
    slide_state = await page.evaluate("""() => {
        return Array.from(document.querySelectorAll('.fangate-slider-content')).map(s => ({
            class: s.className.substring(0, 80),
            visible: s.offsetParent !== null || s.style.display !== 'none',
        }));
    }""")
    logger.info("Slide state: %s", json.dumps(slide_state))

    # Call windowopenerlog manually (in case it wasn't triggered)
    await page.evaluate(f"""async () => {{
        const fd = new URLSearchParams();
        fd.append('elementID', 'login_to_sc');
        fd.append('fangate_id', '{gate_id}');
        await fetch('/windowopenerlog', {{ method:'POST', body:fd.toString(), credentials:'include',
            headers:{{'Content-Type':'application/x-www-form-urlencoded','X-Requested-With':'XMLHttpRequest','X-CSRF-TOKEN':'{csrf}'}}
        }});
    }}""")

    # Trigger completion
    await page.evaluate("""() => {
        if (typeof rX5mPQjW7s === 'function') rX5mPQjW7s('login_to_sc');
    }""")
    await asyncio.sleep(2)

    # Download
    csrf = await page.evaluate("document.querySelector('meta[name=\"csrf-token\"]')?.getAttribute('content')||''")

    dl = await page.evaluate(f"""() => {{
        return new Promise((resolve) => {{
            // Enable button
            $('#gateDownloadButton').removeClass('disable hy-btn-lightgray disabled');
            const origAjax = $.ajax;
            $.ajax = function(opts) {{
                if (opts.url && opts.url.includes('download')) {{
                    const origSuccess = opts.success;
                    opts.success = function(res) {{
                        resolve(JSON.stringify(res));
                        if (origSuccess) origSuccess.call(this, res);
                    }};
                    const origError = opts.error;
                    opts.error = function(xhr) {{
                        resolve(JSON.stringify({{error: true, response: xhr.responseText?.substring(0, 500)}}));
                        if (origError) origError.apply(this, arguments);
                    }};
                }}
                return origAjax.call(this, opts);
            }};
            $('#gateDownloadButton').trigger('click');
            setTimeout(() => resolve('TIMEOUT'), 15000);
        }});
    }}""")
    logger.info("=== DOWNLOAD: %s ===", dl[:500])

    try:
        dj = json.loads(dl)
        if dj.get("download_status"):
            logger.info("🎉🎉🎉 SUCCESS! URL: %s", dj.get("URL", "")[:200])
        else:
            logger.warning("❌ FAILED: social_currency=%s", dj.get("social_currency"))
    except:
        pass

    await asyncio.sleep(5)
    await ctx.close()
    await pw.stop()


if __name__ == "__main__":
    asyncio.run(main())
