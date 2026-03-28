"""FIX v5: Intercept auth2.php in popup, fetch it from main page, relay response.
This ensures auth2.php gets the correct session cookies.
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
    logger.info("=== FIX v5: Fetch auth2 from main page, relay to popup ===")

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

    gate_id = await page.evaluate("document.querySelector('#fan_gate_id')?.value||''")
    csrf = await page.evaluate("document.querySelector('meta[name=\"csrf-token\"]')?.getAttribute('content')||''")
    steps = await page.evaluate("document.querySelector('#steps_select')?.value||''")
    logger.info("Gate: id=%s steps=%s", gate_id, steps)

    # Activate
    await page.evaluate("document.querySelector('#gateDownloadButton')?.click()")
    await asyncio.sleep(3)
    csrf = await page.evaluate("document.querySelector('meta[name=\"csrf-token\"]')?.getAttribute('content')||''")

    # SC Comment
    await page.evaluate(f"""async () => {{
        const fd = new URLSearchParams();
        fd.append('fan_gate_id', '{gate_id}');
        fd.append('comment_sc', 'Great track!');
        await fetch('/setSC', {{ method:'POST', body:fd.toString(), credentials:'include',
            headers:{{'Content-Type':'application/x-www-form-urlencoded','X-Requested-With':'XMLHttpRequest','X-CSRF-TOKEN':'{csrf}'}}
        }});
    }}""")

    oauth_url = await page.evaluate("""() => {
        const b = document.querySelectorAll('#login_to_sc');
        for (const btn of b) {
            const a = btn.getAttribute('data-onclick')||'';
            const m = a.match(/PopupCenterDual\\('([^']+)'/);
            if (m) return m[1];
        }
        return null;
    }""")

    auth2_captured = None

    if oauth_url:
        try:
            async with page.expect_popup(timeout=15000) as pi:
                await page.evaluate(f"window.open('{oauth_url}', 'sc', 'width=800,height=600')")
            popup = await pi.value

            async def intercept_and_relay(route):
                url = route.request.url
                if "hypeddit.com/auth2.php" in url:
                    nonlocal auth2_captured
                    auth2_captured = url

                    # Force HTTPS for the fetch from main page
                    https_url = url.replace("http://", "https://") if url.startswith("http://") else url
                    logger.info("INTERCEPTED auth2.php: %s", url[:120])
                    logger.info("Fetching via main page with HTTPS: %s", https_url[:120])

                    # Fetch auth2.php from the MAIN PAGE context (has correct cookies)
                    result = await page.evaluate(f"""async () => {{
                        try {{
                            const r = await fetch('{https_url}', {{
                                method: 'GET',
                                credentials: 'include',
                                redirect: 'follow',
                            }});
                            const body = await r.text();
                            const headers = {{}};
                            r.headers.forEach((v, k) => {{ headers[k] = v; }});
                            return {{ status: r.status, body: body, headers: headers }};
                        }} catch(e) {{
                            return {{ error: e.message }};
                        }}
                    }}""")

                    if result.get("error"):
                        logger.error("Fetch error: %s", result["error"])
                        await route.fulfill(status=500, body="Error fetching auth2.php")
                    else:
                        logger.info("auth2.php response: status=%d body_len=%d",
                                   result["status"], len(result.get("body", "")))
                        body = result["body"]
                        logger.info("auth2.php body preview: %s", body[:300])

                        # Relay the response to the popup
                        await route.fulfill(
                            status=result["status"],
                            content_type=result.get("headers", {}).get("content-type", "text/html"),
                            body=body,
                        )
                else:
                    await route.continue_()

            await popup.route("**/*auth2*", intercept_and_relay)
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
                try:
                    text = await popup.evaluate("document.body?.innerText || ''")
                    logger.info("Popup still open. Text: %s", text[:200])
                except:
                    pass
                try: await popup.close()
                except: pass

        except Exception as e:
            logger.error("OAuth error: %s", e)

    await asyncio.sleep(2)

    # Trigger the completion handlers
    logger.info("Triggering completion handlers...")
    await page.evaluate("""() => {
        if (typeof rX5mPQjW7s === 'function') rX5mPQjW7s('login_to_sc');
        if (typeof u98YzPqL1 === 'function') u98YzPqL1('login_to_sc');
    }""")
    await asyncio.sleep(2)

    # Check current session
    cookies = await ctx.cookies("https://hypeddit.com")
    session = [c for c in cookies if c["name"] == "laravel_session"]
    logger.info("Current session: %s", session[0]["value"][:40] if session else "NONE")

    # Get fresh CSRF
    csrf = await page.evaluate("document.querySelector('meta[name=\"csrf-token\"]')?.getAttribute('content')||''")

    # === Download ===
    dl = await page.evaluate(f"""async () => {{
        const fd = new URLSearchParams();
        document.querySelectorAll('input[type="hidden"]').forEach(i => {{
            if (i.name) fd.append(i.name, i.value);
        }});
        fd.append('download_action', 'DOWNLOAD');
        fd.append('download_visit', 'true');

        // Add SC comment
        fd.append('sc_comment_text', 'Great track!');
        fd.append('time', String(Math.floor(Math.random() * 313000)));
        fd.append('page', 'nonsingle');

        const r = await fetch('/gate/download/ul', {{ method:'POST', body:fd.toString(), credentials:'include',
            headers:{{'Content-Type':'application/x-www-form-urlencoded','X-Requested-With':'XMLHttpRequest','X-CSRF-TOKEN':'{csrf}'}}
        }});
        return await r.text();
    }}""")
    logger.info("=== DOWNLOAD: %s ===", dl[:500])

    try:
        dj = json.loads(dl)
        if dj.get("download_status"):
            logger.info("🎉🎉🎉 SUCCESS! URL: %s", dj.get("URL", "")[:200])
        else:
            sc = dj.get("social_currency")
            logger.warning("❌ FAILED: %s", json.dumps(dj)[:300])
    except:
        pass

    await asyncio.sleep(10)
    await ctx.close()
    await pw.stop()


if __name__ == "__main__":
    asyncio.run(main())
