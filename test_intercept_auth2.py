"""FIX: Intercept auth2.php redirect, call it from MAIN page with correct session.

Root cause: popup's redirect to auth2.php doesn't include session cookies.
Fix: capture the OAuth code from the redirect URL, then fetch auth2.php
from the MAIN page which has the correct laravel_session cookie.
"""
import asyncio
import json
import random
import logging
from pathlib import Path
from urllib.parse import urlparse, parse_qs

from playwright.async_api import async_playwright

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

TEST_URL = "https://hypeddit.com/houzmusic/onemoretimevalmeredithzrx"  # sc,sp
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
    logger.info("=== FIX TEST: Intercept auth2.php, call from main page ===")

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

    # === KEY FIX: Intercept auth2.php redirect in popup ===
    auth2_url_captured = []

    if oauth_url:
        try:
            async with page.expect_popup(timeout=15000) as pi:
                await page.evaluate(f"window.open('{oauth_url}', 'sc', 'width=800,height=600')")
            popup = await pi.value

            # Route handler: intercept auth2.php requests and ABORT them
            # We'll capture the URL and call it from the main page instead
            async def intercept_auth2(route):
                url = route.request.url
                if "hypeddit.com/auth2.php" in url:
                    logger.info("INTERCEPTED auth2.php: %s", url[:150])
                    auth2_url_captured.append(url)
                    # Abort the request - we'll handle it from the main page
                    await route.fulfill(
                        status=200,
                        content_type="text/html",
                        body="<html><body><script>self.close();</script>Redirecting...</body></html>"
                    )
                else:
                    await route.continue_()

            await popup.route("**/*auth2*", intercept_auth2)

            await popup.wait_for_load_state("domcontentloaded")
            await asyncio.sleep(3)

            # Click Allow
            auth_btn = await popup.query_selector('#submit_approval')
            if auth_btn:
                await auth_btn.click()
                logger.info("Clicked Allow")

            # Wait for popup to close (our interceptor closes it)
            for i in range(20):
                await asyncio.sleep(1)
                if popup.is_closed():
                    logger.info("Popup closed after %ds", i+1)
                    break
            else:
                try: await popup.close()
                except: pass

        except Exception as e:
            logger.error("OAuth error: %s", e)

    # === Now call auth2.php from the MAIN PAGE with correct session ===
    if auth2_url_captured:
        auth2_url = auth2_url_captured[0]
        # Make sure it's HTTPS
        if auth2_url.startswith("http://"):
            auth2_url = "https://" + auth2_url[7:]
        logger.info("Calling auth2.php from MAIN page: %s", auth2_url[:150])

        auth2_result = await page.evaluate(f"""async () => {{
            try {{
                const r = await fetch('{auth2_url}', {{
                    method: 'GET',
                    credentials: 'include',
                }});
                return {{ status: r.status, body: (await r.text()).substring(0, 2000) }};
            }} catch(e) {{
                return {{ error: e.message }};
            }}
        }}""")
        logger.info("auth2.php result: status=%s", auth2_result.get("status"))
        logger.info("auth2.php body (first 500): %s", auth2_result.get("body", "")[:500])
    else:
        logger.warning("auth2.php URL not captured!")

    # Also call /windowopenerlog
    if gate_id:
        wol = await page.evaluate(f"""async () => {{
            const fd = new URLSearchParams();
            fd.append('elementID', 'login_to_sc');
            fd.append('fangate_id', '{gate_id}');
            const r = await fetch('/windowopenerlog', {{ method:'POST', body:fd.toString(), credentials:'include',
                headers:{{'Content-Type':'application/x-www-form-urlencoded','X-Requested-With':'XMLHttpRequest','X-CSRF-TOKEN':'{csrf}'}}
            }});
            return {{ status: r.status, body: (await r.text()).substring(0, 300) }};
        }}""")
        logger.info("/windowopenerlog: %s", json.dumps(wol))

    await asyncio.sleep(2)

    # === CHECK: getGatePathway ===
    pathway = await page.evaluate(f"""async () => {{
        const fd = new URLSearchParams();
        fd.append('fan_gate_id', '{gate_id}');
        const r = await fetch('/getGatePathway', {{ method:'POST', body:fd.toString(), credentials:'include',
            headers:{{'Content-Type':'application/x-www-form-urlencoded','X-Requested-With':'XMLHttpRequest','X-CSRF-TOKEN':'{csrf}'}}
        }});
        return await r.json();
    }}""")
    logger.info("getGatePathway: %s", json.dumps(pathway))

    # === DOWNLOAD ===
    dl = await page.evaluate(f"""async () => {{
        const fd = new URLSearchParams();
        document.querySelectorAll('input[type="hidden"]').forEach(i => {{
            if (i.name) fd.append(i.name, i.value);
        }});
        const r = await fetch('/gate/download/ul', {{ method:'POST', body:fd.toString(), credentials:'include',
            headers:{{'Content-Type':'application/x-www-form-urlencoded','X-Requested-With':'XMLHttpRequest','X-CSRF-TOKEN':'{csrf}'}}
        }});
        return await r.text();
    }}""")
    logger.info("=== DOWNLOAD: %s ===", dl[:300])

    try:
        dj = json.loads(dl)
        if dj.get("download_status"):
            logger.info("🎉🎉🎉 DOWNLOAD SUCCESS! URL: %s", dj.get("URL", "")[:200])
        else:
            logger.warning("❌ STILL FAILED: %s", dl[:200])
    except:
        pass

    await asyncio.sleep(10)
    await ctx.close()
    await pw.stop()


if __name__ == "__main__":
    asyncio.run(main())
