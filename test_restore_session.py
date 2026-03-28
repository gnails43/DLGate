"""FIX v6: Save session cookie before OAuth, restore it after popup closes.
Root cause: popup's auth2.php Set-Cookie overwrites the main page's session.
Fix: Save the session before OAuth, restore it after, so download uses the correct session.
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
    logger.info("=== FIX v6: Save/restore session cookie ===")

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
    logger.info("Gate: id=%s steps=%s comment_sc=%s", gate_id, steps, comment_sc)

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

    # === SAVE ALL HYPEDDIT COOKIES BEFORE OAUTH ===
    cookies_before = await ctx.cookies("https://hypeddit.com")
    session_before = [c for c in cookies_before if c["name"] == "laravel_session"]
    xsrf_before = [c for c in cookies_before if c["name"] == "XSRF-TOKEN"]
    logger.info("Session BEFORE: %s", session_before[0]["value"][:40] if session_before else "NONE")
    logger.info("XSRF BEFORE: %s", xsrf_before[0]["value"][:40] if xsrf_before else "NONE")

    # Save the FULL cookie objects for restoration
    saved_cookies = [c for c in cookies_before if c["name"] in ("laravel_session", "XSRF-TOKEN")]

    # Get OAuth URL
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
        logger.info("Opening popup (natural flow)...")
        try:
            async with page.expect_popup(timeout=15000) as pi:
                await page.evaluate(f"window.open('{oauth_url}', 'sc', 'width=800,height=600')")
            popup = await pi.value

            await popup.wait_for_load_state("domcontentloaded")
            await asyncio.sleep(3)

            auth_btn = await popup.query_selector('#submit_approval')
            if auth_btn:
                await auth_btn.click()
                logger.info("Clicked Allow")

            for i in range(30):
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

    # Check what cookies look like now (should be overwritten by auth2.php)
    cookies_after = await ctx.cookies("https://hypeddit.com")
    session_after = [c for c in cookies_after if c["name"] == "laravel_session"]
    logger.info("Session AFTER (overwritten by popup): %s", session_after[0]["value"][:40] if session_after else "NONE")

    session_changed = (
        session_before and session_after and
        session_before[0]["value"] != session_after[0]["value"]
    )
    logger.info("Session changed: %s", session_changed)

    # === RESTORE THE ORIGINAL SESSION COOKIES ===
    if session_changed:
        logger.info("Restoring original session cookies...")
        # Clear the overwritten cookies first
        await ctx.clear_cookies()
        # Add back ALL cookies except the overwritten ones
        cookies_to_restore = []
        for c in cookies_before:
            # Playwright's add_cookies needs specific format
            cookie = {
                "name": c["name"],
                "value": c["value"],
                "domain": c["domain"],
                "path": c["path"],
            }
            if c.get("expires", -1) > 0:
                cookie["expires"] = c["expires"]
            if c.get("httpOnly"):
                cookie["httpOnly"] = True
            if c.get("secure"):
                cookie["secure"] = True
            if c.get("sameSite"):
                cookie["sameSite"] = c["sameSite"]
            cookies_to_restore.append(cookie)

        await ctx.add_cookies(cookies_to_restore)

        # Verify
        cookies_restored = await ctx.cookies("https://hypeddit.com")
        session_restored = [c for c in cookies_restored if c["name"] == "laravel_session"]
        logger.info("Session RESTORED: %s", session_restored[0]["value"][:40] if session_restored else "NONE")
        logger.info("Match original: %s",
                     session_restored[0]["value"] == session_before[0]["value"] if session_restored and session_before else "N/A")

    # Call windowopenerlog
    await page.evaluate(f"""async () => {{
        const fd = new URLSearchParams();
        fd.append('elementID', 'login_to_sc');
        fd.append('fangate_id', '{gate_id}');
        await fetch('/windowopenerlog', {{ method:'POST', body:fd.toString(), credentials:'include',
            headers:{{'Content-Type':'application/x-www-form-urlencoded','X-Requested-With':'XMLHttpRequest','X-CSRF-TOKEN':'{csrf}'}}
        }});
    }}""")

    # Advance slides
    await page.evaluate("""() => {
        if (typeof rX5mPQjW7s === 'function') rX5mPQjW7s('login_to_sc');
        // Enable button
        $('#gateDownloadButton').removeClass('disable hy-btn-lightgray disabled');
    }""")
    await asyncio.sleep(2)

    # === DOWNLOAD ===
    dl = await page.evaluate("""() => {
        return new Promise((resolve) => {
            const origAjax = $.ajax;
            $.ajax = function(opts) {
                if (opts.url && opts.url.includes('download')) {
                    const origSuccess = opts.success;
                    opts.success = function(res) {
                        resolve(JSON.stringify(res));
                        if (origSuccess) origSuccess.call(this, res);
                    };
                    const origError = opts.error;
                    opts.error = function(xhr) {
                        resolve(JSON.stringify({error: true, response: xhr.responseText?.substring(0, 500)}));
                        if (origError) origError.apply(this, arguments);
                    };
                }
                return origAjax.call(this, opts);
            };
            $('#gateDownloadButton').trigger('click');
            setTimeout(() => resolve('TIMEOUT'), 15000);
        });
    }""")
    logger.info("=== DOWNLOAD: %s ===", dl[:500])

    try:
        dj = json.loads(dl)
        if dj.get("download_status"):
            logger.info("🎉🎉🎉 SUCCESS! URL: %s", dj.get("URL", "")[:200])
        else:
            logger.warning("❌ FAILED: social_currency=%s dl=%s", dj.get("social_currency"), json.dumps(dj)[:200])
    except:
        pass

    await asyncio.sleep(10)
    await ctx.close()
    await pw.stop()


if __name__ == "__main__":
    asyncio.run(main())
