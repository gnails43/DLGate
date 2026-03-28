"""Capture full auth2.php response body via route interception."""
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

    # Intercept auth2.php on ALL pages in the context
    auth2_bodies = []

    async def capture_all_responses(resp):
        if "auth2.php" in resp.url and resp.status == 200:
            try:
                body = await resp.text()
                auth2_bodies.append(body)
                with open("auth2_full_response.html", "w", encoding="utf-8") as f:
                    f.write(body)
                logger.info("CAPTURED auth2.php response: %d chars, saved to auth2_full_response.html", len(body))
            except Exception as e:
                logger.error("Failed to read auth2 body: %s", e)

    # Listen on context level for ALL pages
    ctx.on("response", capture_all_responses)

    await page.goto(TEST_URL, wait_until="domcontentloaded")
    await asyncio.sleep(3)
    await page.evaluate("document.cookie='teb3456767win=;expires=Thu,01 Jan 1970 00:00:00 UTC;path=/;'")
    await page.evaluate("document.querySelector('#gateDownloadButton')?.click()")
    await asyncio.sleep(3)

    csrf = await page.evaluate("document.querySelector('meta[name=\"csrf-token\"]')?.getAttribute('content')||''")
    gate_id = await page.evaluate("document.querySelector('#fan_gate_id')?.value||''")

    # Email
    email = gen_alias(EMAIL)
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

    # SC comment
    await page.evaluate(f"""async () => {{
        const fd = new URLSearchParams();
        fd.append('fan_gate_id', '{gate_id}');
        fd.append('comment_sc', 'Great track!');
        await fetch('/setSC', {{ method:'POST', body:fd.toString(), credentials:'include',
            headers:{{'Content-Type':'application/x-www-form-urlencoded','X-Requested-With':'XMLHttpRequest','X-CSRF-TOKEN':'{csrf}'}}
        }});
    }}""")

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
                await page.evaluate(f"window.open('{oauth_url}', 'sc_popup', 'width=800,height=600')")
            popup = await pi.value
            await popup.wait_for_load_state("domcontentloaded")
            await asyncio.sleep(3)

            auth_btn = await popup.query_selector('#submit_approval')
            if auth_btn:
                await auth_btn.click()
                logger.info("Clicked Allow")

            # Wait for popup to close
            for i in range(30):
                await asyncio.sleep(1)
                if popup.is_closed():
                    logger.info("Popup closed after %ds", i+1)
                    break
        except Exception as e:
            logger.error("OAuth error: %s", e)

    await asyncio.sleep(2)

    # Check auth2 capture
    if auth2_bodies:
        logger.info("auth2.php captured: %d chars", len(auth2_bodies[0]))
        # Extract scripts
        import re
        scripts = re.findall(r'<script(?:\s[^>]*)?>(.+?)</script>', auth2_bodies[0], re.DOTALL)
        logger.info("Found %d script blocks", len(scripts))
        for i, s in enumerate(scripts):
            s = s.strip()
            if s and not s.startswith('//') and len(s) > 10:
                logger.info("=== Script %d (%d chars) ===", i, len(s))
                logger.info("%s", s[:2000])
    else:
        logger.warning("auth2.php body NOT captured!")

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
