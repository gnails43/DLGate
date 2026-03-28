"""FIX v4: Inject session cookies into popup's auth2.php request.
Root cause: redirect_uri is HTTP, but laravel_session cookie is Secure.
Fix: Intercept the popup's auth2.php request and add cookies manually.
"""
import asyncio
import json
import random
import logging
from pathlib import Path

from playwright.async_api import async_playwright

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

TEST_URL = "https://hypeddit.com/houzmusic/onemoretimevalmeredithzrx"
PROFILE_DIR = str(Path("C:/GitHub/DLGate/.claude/worktrees/vigilant-ramanujan/.browser_profile").resolve())


async def main():
    pw = await async_playwright().start()
    logger.info("=== FIX v4: Inject cookies into popup auth2.php ===")

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

    # === STEP 1: Load gate ===
    await page.goto(TEST_URL, wait_until="domcontentloaded")
    await asyncio.sleep(3)
    await page.evaluate("document.cookie='teb3456767win=;expires=Thu,01 Jan 1970 00:00:00 UTC;path=/;'")

    gate_id = await page.evaluate("document.querySelector('#fan_gate_id')?.value||''")
    csrf = await page.evaluate("document.querySelector('meta[name=\"csrf-token\"]')?.getAttribute('content')||''")
    steps = await page.evaluate("document.querySelector('#steps_select')?.value||''")
    logger.info("Gate: id=%s steps=%s", gate_id, steps)

    # Activate
    await page.evaluate("document.querySelector('#gateDownloadButton')?.click()")
    await asyncio.sleep(3)
    csrf = await page.evaluate("document.querySelector('meta[name=\"csrf-token\"]')?.getAttribute('content')||''")

    # === STEP 2: SC Comment ===
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
        const b = document.querySelectorAll('#login_to_sc');
        for (const btn of b) {
            const a = btn.getAttribute('data-onclick')||'';
            const m = a.match(/PopupCenterDual\\('([^']+)'/);
            if (m) return m[1];
        }
        return null;
    }""")
    logger.info("OAuth URL: %s", (oauth_url or "")[:120])

    # === STEP 3: Get current cookies to inject ===
    cookies = await ctx.cookies("https://hypeddit.com")
    cookie_header = "; ".join(f"{c['name']}={c['value']}" for c in cookies if c['name'] in ('laravel_session', 'XSRF-TOKEN'))
    logger.info("Cookie header to inject: %s", cookie_header[:100])

    if oauth_url:
        try:
            async with page.expect_popup(timeout=15000) as pi:
                await page.evaluate(f"window.open('{oauth_url}', 'sc', 'width=800,height=600')")
            popup = await pi.value

            # Route handler: intercept auth2.php requests and ADD cookies + force HTTPS
            async def inject_cookies(route):
                url = route.request.url
                if "hypeddit.com/auth2.php" in url:
                    # Force HTTPS
                    if url.startswith("http://"):
                        url = "https://" + url[7:]

                    logger.info("INTERCEPTING auth2.php, adding cookies, forcing HTTPS")
                    logger.info("  URL: %s", url[:150])

                    # Get fresh cookies
                    fresh_cookies = await ctx.cookies("https://hypeddit.com")
                    fresh_cookie_header = "; ".join(
                        f"{c['name']}={c['value']}" for c in fresh_cookies
                        if c['name'] in ('laravel_session', 'XSRF-TOKEN')
                    )
                    logger.info("  Injecting cookies: %s", fresh_cookie_header[:80])

                    # Fetch auth2.php with correct cookies from the MAIN page context
                    # Use page.evaluate to make the request from the main page
                    headers = dict(route.request.headers)
                    headers['cookie'] = fresh_cookie_header

                    # Continue the request with modified headers and HTTPS URL
                    await route.continue_(url=url, headers=headers)
                else:
                    await route.continue_()

            await popup.route("**/*auth2*", inject_cookies)
            await popup.wait_for_load_state("domcontentloaded")
            await asyncio.sleep(3)

            # Click Allow
            auth_btn = await popup.query_selector('#submit_approval')
            if auth_btn:
                await auth_btn.click()
                logger.info("Clicked Allow")

            # Wait for popup to process auth2.php and close
            for i in range(30):
                await asyncio.sleep(1)
                if popup.is_closed():
                    logger.info("Popup closed after %ds", i+1)
                    break
            else:
                # Check what auth2.php page shows
                try:
                    text = await popup.evaluate("document.body?.innerText || ''")
                    logger.info("Popup text: %s", text[:200])
                except:
                    pass
                try:
                    await popup.close()
                except:
                    pass

        except Exception as e:
            logger.error("OAuth error: %s", e)

    await asyncio.sleep(2)

    # === STEP 4: Trigger what auth2.php would do ===
    # Set localStorage and trigger storage event
    logger.info("Triggering localStorage hypeChildWindow...")
    await page.evaluate("""() => {
        // Simulate what auth2.php does as fallback
        localStorage.setItem('hypeChildWindow', 'login_to_sc');
    }""")
    # The storage event only fires in OTHER windows, not the one that set it
    # So we need to manually trigger the handler
    await page.evaluate("""() => {
        // Manually call the handler functions
        if (typeof rX5mPQjW7s === 'function') {
            rX5mPQjW7s('login_to_sc');
        }
        if (typeof u98YzPqL1 === 'function') {
            u98YzPqL1('login_to_sc');
        }
    }""")
    await asyncio.sleep(2)

    # Check slide state
    slide_state = await page.evaluate("""() => {
        const slides = document.querySelectorAll('.fangate-slider-content');
        return Array.from(slides).map(s => ({
            classes: s.className.substring(0, 100),
            visible: s.offsetParent !== null,
        }));
    }""")
    logger.info("Slide state: %s", json.dumps(slide_state))

    # === STEP 5: Check pathway and download ===
    pathway = await page.evaluate(f"""async () => {{
        const fd = new URLSearchParams();
        fd.append('fan_gate_id', '{gate_id}');
        const r = await fetch('/getGatePathway', {{ method:'POST', body:fd.toString(), credentials:'include',
            headers:{{'Content-Type':'application/x-www-form-urlencoded','X-Requested-With':'XMLHttpRequest','X-CSRF-TOKEN':'{csrf}'}}
        }});
        return await r.json();
    }}""")
    logger.info("getGatePathway: %s", json.dumps(pathway))

    # Try download using the NATIVE jQuery mechanism
    logger.info("=== Attempting download via native jQuery click ===")
    dl = await page.evaluate("""() => {
        return new Promise((resolve) => {
            // Override the ajax to capture the download response
            const origAjax = $.ajax;
            $.ajax = function(opts) {
                if (opts.url && opts.url.includes('download')) {
                    const origSuccess = opts.success;
                    opts.success = function(res) {
                        resolve(JSON.stringify(res));
                        if (origSuccess) origSuccess.call(this, res);
                    };
                    const origError = opts.error;
                    opts.error = function(xhr, status, err) {
                        resolve(JSON.stringify({error: status, detail: err}));
                        if (origError) origError.call(this, xhr, status, err);
                    };
                }
                return origAjax.call(this, opts);
            };

            // Click the download button
            $('#gateDownloadButton').trigger('click');

            // Timeout
            setTimeout(() => resolve('TIMEOUT'), 15000);
        });
    }""")
    logger.info("=== DOWNLOAD (native): %s ===", dl[:500])

    # Also try direct download API call
    dl2 = await page.evaluate(f"""async () => {{
        const fd = new URLSearchParams();
        document.querySelectorAll('input[type="hidden"]').forEach(i => {{
            if (i.name) fd.append(i.name, i.value);
        }});
        fd.append('download_action', 'DOWNLOAD');
        fd.append('download_visit', 'true');
        const r = await fetch('/gate/download/ul', {{ method:'POST', body:fd.toString(), credentials:'include',
            headers:{{'Content-Type':'application/x-www-form-urlencoded','X-Requested-With':'XMLHttpRequest','X-CSRF-TOKEN':'{csrf}'}}
        }});
        return await r.text();
    }}""")
    logger.info("=== DOWNLOAD (direct): %s ===", dl2[:500])

    try:
        dj = json.loads(dl2)
        if dj.get("download_status"):
            logger.info("SUCCESS! URL: %s", dj.get("URL", "")[:200])
        else:
            logger.warning("FAILED: %s", json.dumps(dj)[:300])
    except:
        pass

    await asyncio.sleep(10)
    await ctx.close()
    await pw.stop()


if __name__ == "__main__":
    asyncio.run(main())
