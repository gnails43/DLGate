"""Simulate a REAL USER flow as closely as possible.
Click buttons the way the page expects, watch all network activity.
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
    logger.info("=== REAL USER simulation ===")

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

    # Monitor ALL relevant network
    async def on_response(resp):
        url = resp.url
        if "hypeddit.com" in url:
            short = url.split("hypeddit.com")[-1][:80]
            kws = ["download", "auth2", "setSC", "getSC", "Pathway", "windowopener", "verify"]
            if any(k.lower() in short.lower() for k in kws):
                try:
                    body = await resp.text()
                except:
                    body = "?"
                logger.info("  <<< %d %s %s", resp.status, short, body[:200])

    page.on("response", on_response)

    # Step 1: Load gate
    logger.info("STEP 1: Loading gate...")
    await page.goto(SC_ONLY_URL, wait_until="domcontentloaded")
    await asyncio.sleep(3)

    # Clear popup cookie
    await page.evaluate("document.cookie='teb3456767win=;expires=Thu,01 Jan 1970 00:00:00 UTC;path=/;'")

    gate_id = await page.evaluate("document.querySelector('#fan_gate_id')?.value||''")
    csrf = await page.evaluate("document.querySelector('meta[name=\"csrf-token\"]')?.getAttribute('content')||''")
    steps = await page.evaluate("document.querySelector('#steps_select')?.value||''")
    comment_sc = await page.evaluate("document.querySelector('#comment_sc')?.value||''")
    logger.info("gate_id=%s steps=%s comment_sc=%s", gate_id, steps, comment_sc)

    # Step 2: Click the big download button (gateDownloadButton)
    logger.info("STEP 2: Clicking Download button...")
    await page.evaluate("document.querySelector('#gateDownloadButton')?.click()")
    await asyncio.sleep(3)

    # Step 3: Fill in SC comment if needed
    if comment_sc == '1':
        logger.info("STEP 3: Filling SC comment via JS...")
        await page.evaluate("$('#sc_comment_text').val('Great track!')")
        await asyncio.sleep(0.5)

    # Step 4: Click the SC login button
    logger.info("STEP 4: Clicking SC login button...")
    sc_btn = await page.query_selector('#login_to_sc')
    if sc_btn:
        # Save session before popup
        cookies_before = await ctx.cookies("https://hypeddit.com")
        session_before = {c["name"]: c for c in cookies_before if c["name"] in ("laravel_session", "XSRF-TOKEN")}

        # Click using the native jQuery handler (eval data-onclick)
        try:
            async with page.expect_popup(timeout=15000) as pi:
                # Trigger the jQuery click handler which calls eval(data-onclick)
                await page.evaluate("$('#login_to_sc').trigger('click')")
            popup = await pi.value
            logger.info("Popup opened: %s", popup.url[:80])

            # Wait for SC authorization page
            await popup.wait_for_load_state("domcontentloaded")
            await asyncio.sleep(3)

            # Check if we need to click Allow
            auth_btn = await popup.query_selector('#submit_approval')
            if auth_btn:
                logger.info("Clicking SC Allow button...")
                await auth_btn.click()
            else:
                text = await popup.evaluate("document.body?.innerText || ''")
                logger.info("No Allow button. Page: %s", text[:200])

            # Wait for popup to process and close
            logger.info("Waiting for popup to close (auth2.php processing)...")
            for i in range(40):
                await asyncio.sleep(1)
                if popup.is_closed():
                    logger.info("Popup closed after %ds", i+1)
                    break
                try:
                    url = popup.url
                    if i % 5 == 4:
                        logger.info("Popup still open at %ds: %s", i+1, url[:80])
                except:
                    logger.info("Popup may have closed (error getting URL)")
                    break
            else:
                logger.warning("Popup didn't close after 40s")
                try:
                    text = await popup.evaluate("document.body?.innerText || ''")
                    logger.info("Popup text: %s", text[:200])
                    await popup.close()
                except:
                    pass

        except Exception as e:
            logger.error("Popup error: %s", e)

        # Check session after popup
        cookies_after = await ctx.cookies("https://hypeddit.com")
        session_after = {c["name"]: c for c in cookies_after if c["name"] in ("laravel_session", "XSRF-TOKEN")}

        session_changed = session_before.get("laravel_session", {}).get("value") != session_after.get("laravel_session", {}).get("value")
        logger.info("Session changed by popup: %s", session_changed)

        if session_changed:
            logger.info("  Before: %s", session_before.get("laravel_session", {}).get("value", "")[:40])
            logger.info("  After:  %s", session_after.get("laravel_session", {}).get("value", "")[:40])

            # RESTORE the original session
            logger.info("Restoring original session...")
            for cookie_name in ("laravel_session", "XSRF-TOKEN"):
                if cookie_name in session_before:
                    old = session_before[cookie_name]
                    # We can't easily restore just one cookie, so let's set it via browser
                    await ctx.add_cookies([{
                        "name": old["name"],
                        "value": old["value"],
                        "domain": old["domain"],
                        "path": old["path"],
                        "secure": old.get("secure", False),
                        "httpOnly": old.get("httpOnly", False),
                        "sameSite": old.get("sameSite", "Lax"),
                        "expires": old.get("expires", -1),
                    }])

            cookies_check = await ctx.cookies("https://hypeddit.com")
            session_check = [c for c in cookies_check if c["name"] == "laravel_session"]
            logger.info("Session restored: %s",
                        session_check[0]["value"][:40] == session_before.get("laravel_session", {}).get("value", "")[:40]
                        if session_check else "FAILED")

    await asyncio.sleep(2)

    # Step 5: Check localStorage
    hype = await page.evaluate("localStorage.getItem('hypeChildWindow')")
    logger.info("localStorage.hypeChildWindow = %s", hype)

    # Step 6: Trigger slide transition and windowopenerlog
    logger.info("STEP 6: Triggering completion...")
    await page.evaluate("""() => {
        if (typeof rX5mPQjW7s === 'function') rX5mPQjW7s('login_to_sc');
        if (typeof u98YzPqL1 === 'function') u98YzPqL1('login_to_sc');
        // Also enable the download button
        $('#gateDownloadButton').removeClass('disable hy-btn-lightgray disabled');
    }""")
    await asyncio.sleep(3)

    # Step 7: Check slide state and download status
    slide_state = await page.evaluate("""() => {
        return Array.from(document.querySelectorAll('.fangate-slider-content')).map(s => ({
            class: s.className.substring(0, 60),
        }));
    }""")
    logger.info("Slides: %s", json.dumps(slide_state))

    # Step 8: Download
    logger.info("STEP 8: Attempting download...")
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
                    opts.error = function(xhr) {
                        resolve('ERROR: ' + (xhr.responseText || '').substring(0, 500));
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
            logger.warning("❌ FAILED: social_currency=%s", dj.get("social_currency"))
            logger.warning("Full response: %s", json.dumps(dj))
    except:
        pass

    await asyncio.sleep(10)
    await ctx.close()
    await pw.stop()


if __name__ == "__main__":
    asyncio.run(main())
