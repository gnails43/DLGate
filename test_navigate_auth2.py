"""FIX v2: Navigate MAIN PAGE to auth2.php URL, then back to gate.
This ensures auth2.php processes with the correct session cookies
and any session regeneration is properly handled.
"""
import asyncio
import json
import random
import logging
from pathlib import Path

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
    logger.info("=== FIX v2: Navigate main page to auth2.php ===")

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

    # === STEP 3: SC OAuth - open popup, get code, intercept redirect ===
    oauth_url = await page.evaluate("""() => {
        const b = document.querySelectorAll('#login_to_sc');
        for (const btn of b) {
            const a = btn.getAttribute('data-onclick')||'';
            const m = a.match(/PopupCenterDual\\('([^']+)'/);
            if (m) return m[1];
        }
        return null;
    }""")

    auth2_url = None

    if oauth_url:
        try:
            async with page.expect_popup(timeout=15000) as pi:
                await page.evaluate(f"window.open('{oauth_url}', 'sc', 'width=800,height=600')")
            popup = await pi.value

            # Intercept auth2.php - capture URL but don't let it hit server
            async def intercept(route):
                url = route.request.url
                if "hypeddit.com/auth2.php" in url:
                    nonlocal auth2_url
                    auth2_url = url
                    logger.info("CAPTURED auth2 URL: %s", url[:150])
                    await route.fulfill(status=200, content_type="text/html",
                                       body="<html><script>self.close();</script></html>")
                else:
                    await route.continue_()

            await popup.route("**/*auth2*", intercept)
            await popup.wait_for_load_state("domcontentloaded")
            await asyncio.sleep(3)

            auth_btn = await popup.query_selector('#submit_approval')
            if auth_btn:
                await auth_btn.click()
                logger.info("Clicked Allow")

            for _ in range(15):
                await asyncio.sleep(1)
                if popup.is_closed() or auth2_url:
                    break
            if not popup.is_closed():
                try: await popup.close()
                except: pass

        except Exception as e:
            logger.error("OAuth error: %s", e)

    if not auth2_url:
        logger.error("Failed to capture auth2 URL!")
        await ctx.close()
        await pw.stop()
        return

    # === STEP 4: Navigate MAIN PAGE to auth2.php URL ===
    # Force HTTPS
    if auth2_url.startswith("http://"):
        auth2_url = "https://" + auth2_url[7:]

    logger.info("Navigating main page to auth2.php...")
    await page.goto(auth2_url, wait_until="domcontentloaded")
    await asyncio.sleep(3)

    # Check what auth2.php returned
    auth2_text = await page.evaluate("() => document.body?.innerText || ''")
    logger.info("auth2 page text: %s", auth2_text[:200])

    # === STEP 5: Navigate back to gate ===
    logger.info("Navigating back to gate...")
    await page.goto(TEST_URL, wait_until="domcontentloaded")
    await asyncio.sleep(3)
    await page.evaluate("document.cookie='teb3456767win=;expires=Thu,01 Jan 1970 00:00:00 UTC;path=/;'")

    # Re-extract CSRF (might have changed)
    csrf = await page.evaluate("document.querySelector('meta[name=\"csrf-token\"]')?.getAttribute('content')||''")
    gate_id = await page.evaluate("document.querySelector('#fan_gate_id')?.value||''")
    logger.info("After return: gate_id=%s", gate_id)

    # Activate gate again
    await page.evaluate("document.querySelector('#gateDownloadButton')?.click()")
    await asyncio.sleep(3)
    csrf = await page.evaluate("document.querySelector('meta[name=\"csrf-token\"]')?.getAttribute('content')||''")

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
            logger.info("🎉🎉🎉 SUCCESS! URL: %s", dj.get("URL", "")[:200])
        else:
            sc = dj.get("social_currency")
            logger.warning("❌ FAILED: download_status=%s social_currency=%s", dj.get("download_status"), sc)
    except:
        pass

    await asyncio.sleep(10)
    await ctx.close()
    await pw.stop()


if __name__ == "__main__":
    asyncio.run(main())
