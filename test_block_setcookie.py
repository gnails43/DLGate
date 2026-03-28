"""FIX v7: Block auth2.php's Set-Cookie to prevent session overwrite.
Intercept auth2.php response and strip Set-Cookie headers.
"""
import asyncio
import json
import logging
from pathlib import Path

from playwright.async_api import async_playwright

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

SC_ONLY_URL = "https://hypeddit.com/lukewaveblackzushi/nacho"
PROFILE_DIR = str(Path("C:/GitHub/DLGate/.claude/worktrees/vigilant-ramanujan/.browser_profile").resolve())


async def main():
    pw = await async_playwright().start()
    logger.info("=== FIX v7: Block Set-Cookie from auth2.php ===")

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

    await page.goto(SC_ONLY_URL, wait_until="domcontentloaded")
    await asyncio.sleep(3)
    await page.evaluate("document.cookie='teb3456767win=;expires=Thu,01 Jan 1970 00:00:00 UTC;path=/;'")

    gate_id = await page.evaluate("document.querySelector('#fan_gate_id')?.value||''")
    csrf = await page.evaluate("document.querySelector('meta[name=\"csrf-token\"]')?.getAttribute('content')||''")
    steps = await page.evaluate("document.querySelector('#steps_select')?.value||''")
    comment_sc = await page.evaluate("document.querySelector('#comment_sc')?.value||''")
    logger.info("Gate: id=%s steps=%s", gate_id, steps)

    # Activate
    await page.evaluate("document.querySelector('#gateDownloadButton')?.click()")
    await asyncio.sleep(3)
    csrf = await page.evaluate("document.querySelector('meta[name=\"csrf-token\"]')?.getAttribute('content')||''")

    # SC Comment
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

    # Download BEFORE OAuth (baseline)
    dl_before = await page.evaluate("""() => {
        return new Promise((resolve) => {
            const origAjax = $.ajax;
            $.ajax = function(opts) {
                if (opts.url && opts.url.includes('download')) {
                    const origSuccess = opts.success;
                    opts.success = function(res) {
                        resolve(JSON.stringify(res));
                        if (origSuccess) origSuccess.call(this, res);
                    };
                    opts.error = function(xhr) {
                        resolve('ERROR: ' + xhr.responseText?.substring(0, 200));
                    };
                }
                return origAjax.call(this, opts);
            };
            // Remove disabled
            $('#gateDownloadButton').removeClass('disable hy-btn-lightgray disabled');
            $('#gateDownloadButton').trigger('click');
            setTimeout(() => resolve('TIMEOUT'), 10000);
        });
    }""")
    logger.info("Download BEFORE OAuth: %s", dl_before[:300])

    # Get session
    cookies = await ctx.cookies("https://hypeddit.com")
    session_before = [c for c in cookies if c["name"] == "laravel_session"]
    logger.info("Session: %s", session_before[0]["value"][:40] if session_before else "NONE")

    # OAuth URL
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
        try:
            async with page.expect_popup(timeout=15000) as pi:
                await page.evaluate(f"window.open('{oauth_url}', 'sc', 'width=800,height=600')")
            popup = await pi.value

            # Intercept auth2.php: let it process but BLOCK Set-Cookie by fulfilling with the response body
            async def block_setcookie(route):
                url = route.request.url
                if "hypeddit.com/auth2.php" in url:
                    logger.info("Intercepting auth2.php to block Set-Cookie...")
                    # Let the request go through but use fetch to get the response
                    # and fulfill without the Set-Cookie
                    https_url = url.replace("http://", "https://") if url.startswith("http://") else url

                    # Fetch from a new API request context that includes cookies
                    # Use the main page's fetch to ensure correct session
                    result = await page.evaluate(f"""async () => {{
                        const r = await fetch('{https_url}', {{ credentials: 'include' }});
                        return {{ status: r.status, body: await r.text() }};
                    }}""")

                    logger.info("auth2 fetched via main page: status=%d", result.get("status", 0))
                    # Fulfill the route without Set-Cookie headers
                    await route.fulfill(
                        status=result.get("status", 200),
                        content_type="text/html",
                        body=result.get("body", ""),
                        # No headers = no Set-Cookie
                    )
                else:
                    await route.continue_()

            await popup.route("**/*auth2*", block_setcookie)
            await popup.wait_for_load_state("domcontentloaded")
            await asyncio.sleep(3)

            auth_btn = await popup.query_selector('#submit_approval')
            if auth_btn:
                await auth_btn.click()
                logger.info("Clicked Allow")

            for i in range(20):
                await asyncio.sleep(1)
                if popup.is_closed():
                    logger.info("Popup closed after %ds", i+1)
                    break
            else:
                try: await popup.close()
                except: pass

        except Exception as e:
            logger.error("OAuth: %s", e)

    await asyncio.sleep(1)

    # Check session after - should be SAME as before (Set-Cookie blocked)
    cookies = await ctx.cookies("https://hypeddit.com")
    session_after = [c for c in cookies if c["name"] == "laravel_session"]
    logger.info("Session AFTER (should be same): %s", session_after[0]["value"][:40] if session_after else "NONE")
    if session_before and session_after:
        logger.info("Session preserved: %s", session_before[0]["value"] == session_after[0]["value"])

    # Trigger completion
    await page.evaluate("""() => {
        if (typeof rX5mPQjW7s === 'function') rX5mPQjW7s('login_to_sc');
        if (typeof u98YzPqL1 === 'function') u98YzPqL1('login_to_sc');
    }""")
    await asyncio.sleep(2)

    # Download AFTER OAuth
    dl_after = await page.evaluate("""() => {
        return new Promise((resolve) => {
            const origAjax = $.ajax;
            $.ajax = function(opts) {
                if (opts.url && opts.url.includes('download')) {
                    const origSuccess = opts.success;
                    opts.success = function(res) {
                        resolve(JSON.stringify(res));
                        if (origSuccess) origSuccess.call(this, res);
                    };
                    opts.error = function(xhr) {
                        resolve('ERROR: ' + xhr.responseText?.substring(0, 200));
                    };
                }
                return origAjax.call(this, opts);
            };
            $('#gateDownloadButton').removeClass('disable hy-btn-lightgray disabled');
            $('#gateDownloadButton').trigger('click');
            setTimeout(() => resolve('TIMEOUT'), 10000);
        });
    }""")
    logger.info("=== Download AFTER OAuth: %s ===", dl_after[:500])

    try:
        dj = json.loads(dl_after)
        if dj.get("download_status"):
            logger.info("🎉🎉🎉 SUCCESS! URL: %s", dj.get("URL", "")[:200])
        else:
            logger.warning("❌ FAILED: social_currency=%s", dj.get("social_currency"))
    except:
        pass

    await asyncio.sleep(10)
    await ctx.close()
    await pw.stop()


if __name__ == "__main__":
    asyncio.run(main())
