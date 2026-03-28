"""Track session cookies and check if auth2.php popup has same session.
Also test: does email verify incrementally change social_currency?
"""
import asyncio
import json
import random
import logging
from pathlib import Path

from playwright.async_api import async_playwright

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

TEST_URL = "https://hypeddit.com/houzmusic/onemoretimevalmeredithzrx"  # sc,sp only
EMAIL = "gna.k.fujisaki43@gmail.com"
NAME = "Kentaro"
PROFILE_DIR = str(Path("C:/GitHub/DLGate/.claude/worktrees/vigilant-ramanujan/.browser_profile").resolve())


def gen_alias(email):
    local, domain = email.split("@", 1)
    local = local.split("+")[0].replace(".", "")
    pos = sorted(random.sample(range(1, len(local)), min(random.randint(1, 3), len(local) - 1)))
    parts, prev = [], 0
    for p in pos:
        parts.append(local[prev:p])
        prev = p
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

    # Intercept ALL Set-Cookie headers from auth2.php
    auth2_request_cookies = []
    auth2_response_headers = []

    async def on_request(req):
        if "auth2.php" in req.url:
            headers = dict(req.headers)
            cookie_header = headers.get("cookie", "NO COOKIE HEADER")
            auth2_request_cookies.append({
                "url": req.url[:100],
                "cookie": cookie_header[:200],
                "has_laravel_session": "laravel_session" in cookie_header,
                "has_xsrf": "XSRF-TOKEN" in cookie_header,
            })
            logger.info("auth2.php REQUEST cookies: has_session=%s has_xsrf=%s url=%s",
                        "laravel_session" in cookie_header,
                        "XSRF-TOKEN" in cookie_header,
                        req.url[:80])

    async def on_response(resp):
        if "auth2.php" in resp.url:
            headers = dict(resp.headers) if hasattr(resp, 'headers') else {}
            all_headers = await resp.all_headers()
            auth2_response_headers.append({
                "url": resp.url[:100],
                "status": resp.status,
                "headers": all_headers,
            })
            set_cookie = all_headers.get("set-cookie", "")
            logger.info("auth2.php RESPONSE: status=%d set-cookie=%s",
                        resp.status, set_cookie[:200] if set_cookie else "NONE")

    page.on("request", on_request)
    page.on("response", on_response)
    # Also listen on context for popup requests
    ctx.on("request", on_request)
    ctx.on("response", on_response)

    await page.goto(TEST_URL, wait_until="domcontentloaded")
    await asyncio.sleep(3)
    await page.evaluate("document.cookie='teb3456767win=;expires=Thu,01 Jan 1970 00:00:00 UTC;path=/;'")

    gate_id = await page.evaluate("document.querySelector('#fan_gate_id')?.value||''")
    csrf = await page.evaluate("document.querySelector('meta[name=\"csrf-token\"]')?.getAttribute('content')||''")
    steps = await page.evaluate("document.querySelector('#steps_select')?.value||''")
    logger.info("Gate: id=%s steps=%s", gate_id, steps)

    # Get initial session cookie
    cookies_before = await ctx.cookies()
    session_before = [c for c in cookies_before if c["name"] == "laravel_session"]
    logger.info("Session BEFORE: %s", session_before[0]["value"][:40] if session_before else "NONE")

    # Activate
    await page.evaluate("document.querySelector('#gateDownloadButton')?.click()")
    await asyncio.sleep(3)
    csrf = await page.evaluate("document.querySelector('meta[name=\"csrf-token\"]')?.getAttribute('content')||''")

    # Check download BEFORE any steps
    dl0 = await page.evaluate(f"""async () => {{
        const fd = new URLSearchParams();
        document.querySelectorAll('input[type="hidden"]').forEach(i => {{
            if (i.name) fd.append(i.name, i.value);
        }});
        const r = await fetch('/gate/download/ul', {{ method:'POST', body:fd.toString(), credentials:'include',
            headers:{{'Content-Type':'application/x-www-form-urlencoded','X-Requested-With':'XMLHttpRequest','X-CSRF-TOKEN':'{csrf}'}}
        }});
        return await r.text();
    }}""")
    logger.info("Download BEFORE steps: %s", dl0[:200])

    # SC OAuth
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

    if oauth_url:
        logger.info("Opening SC OAuth popup...")
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
        except Exception as e:
            logger.error("OAuth error: %s", e)

    await asyncio.sleep(2)

    # Check session AFTER OAuth
    cookies_after = await ctx.cookies()
    session_after = [c for c in cookies_after if c["name"] == "laravel_session"]
    logger.info("Session AFTER OAuth: %s", session_after[0]["value"][:40] if session_after else "NONE")

    # Download AFTER SC OAuth only
    dl1 = await page.evaluate(f"""async () => {{
        const fd = new URLSearchParams();
        document.querySelectorAll('input[type="hidden"]').forEach(i => {{
            if (i.name) fd.append(i.name, i.value);
        }});
        const r = await fetch('/gate/download/ul', {{ method:'POST', body:fd.toString(), credentials:'include',
            headers:{{'Content-Type':'application/x-www-form-urlencoded','X-Requested-With':'XMLHttpRequest','X-CSRF-TOKEN':'{csrf}'}}
        }});
        return await r.text();
    }}""")
    logger.info("Download AFTER SC: %s", dl1[:200])

    # Log auth2 request/response details
    logger.info("=== auth2.php REQUEST cookies (%d) ===", len(auth2_request_cookies))
    for c in auth2_request_cookies:
        logger.info("  %s", json.dumps(c))

    logger.info("=== auth2.php RESPONSE headers (%d) ===", len(auth2_response_headers))
    for h in auth2_response_headers:
        logger.info("  status=%d url=%s", h["status"], h["url"])
        for k, v in h["headers"].items():
            if k.lower() in ("set-cookie", "location", "content-type"):
                logger.info("    %s: %s", k, v[:200])

    await asyncio.sleep(10)
    await ctx.close()
    await pw.stop()


if __name__ == "__main__":
    asyncio.run(main())
