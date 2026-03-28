"""Deep diagnostic: What does auth2.php actually return?
What changes on the main page after OAuth popup closes?
"""
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


def generate_email_alias(base_email: str) -> str:
    local, domain = base_email.split("@", 1)
    local = local.split("+")[0].replace(".", "")
    positions = sorted(random.sample(range(1, len(local)), min(random.randint(1, 3), len(local) - 1)))
    parts, prev = [], 0
    for pos in positions:
        parts.append(local[prev:pos])
        prev = pos
    parts.append(local[prev:])
    return ".".join(parts) + f"@{domain}"


async def main():
    pw = await async_playwright().start()
    logger.info("=== auth2.php DEEP DIAGNOSTIC ===")

    import glob, os
    for pat in ["SingletonLock", "SingletonSocket", "SingletonCookie"]:
        for f in glob.glob(os.path.join(PROFILE_DIR, pat)):
            try: os.remove(f)
            except: pass

    ctx = await pw.chromium.launch_persistent_context(
        user_data_dir=PROFILE_DIR,
        headless=False,
        channel="chrome",
        viewport={"width": 1280, "height": 900},
        accept_downloads=True,
        args=["--disable-blink-features=AutomationControlled"],
        ignore_default_args=["--enable-automation"],
    )
    page = ctx.pages[0] if ctx.pages else await ctx.new_page()

    await page.goto(TEST_URL, wait_until="domcontentloaded")
    await asyncio.sleep(3)
    await page.evaluate("document.cookie = 'teb3456767win=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;';")

    meta = await page.evaluate("""() => {
        const r = {};
        document.querySelectorAll('input[type="hidden"]').forEach(i => { if (i.id) r[i.id] = i.value; });
        r.csrf = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';
        return r;
    }""")
    gate_id = meta.get("fan_gate_id", "")
    csrf = meta.get("csrf", "")
    logger.info("Gate: id=%s steps=%s", gate_id, meta.get("steps_select"))

    # Activate
    await page.evaluate("document.querySelector('#gateDownloadButton')?.click()")
    await asyncio.sleep(3)
    csrf = await page.evaluate("document.querySelector('meta[name=\"csrf-token\"]')?.getAttribute('content') || ''")

    # === EMAIL STEP ===
    email = generate_email_alias(EMAIL)
    await page.evaluate(f"""() => {{
        const n = document.querySelector('#email_name');
        if (n) {{ n.value = {repr(NAME)}; n.dispatchEvent(new Event('input', {{bubbles:true}})); }}
        const a = document.querySelector('#email_address');
        if (a) {{ a.value = {repr(email)}; a.dispatchEvent(new Event('input', {{bubbles:true}})); }}
    }}""")
    await asyncio.sleep(1)
    await page.evaluate("(jQuery || $)('#email_to_downloads_next').trigger('click');")
    await asyncio.sleep(5)

    # Advance to SC
    await page.evaluate("""() => {
        const cur = document.querySelector('.fangate-slider-content.email.current-slide');
        if (cur) { cur.classList.remove('current-slide'); cur.classList.add('move-left'); }
        const sc = document.querySelector('.fangate-slider-content.sc');
        if (sc) { sc.classList.remove('upcomming-slide'); sc.classList.add('current-slide', 'zindex'); }
    }""")
    await asyncio.sleep(1)

    # === CAPTURE STATE BEFORE OAUTH ===
    before_hidden = await page.evaluate("""() => {
        const r = {};
        document.querySelectorAll('input[type="hidden"]').forEach(i => {
            if (i.name || i.id) r[(i.id || i.name)] = i.value;
        });
        return r;
    }""")
    before_ls = await page.evaluate("""() => {
        const r = {};
        for (let i = 0; i < localStorage.length; i++) {
            const k = localStorage.key(i);
            r[k] = localStorage.getItem(k);
        }
        return r;
    }""")
    logger.info("BEFORE OAuth - hidden inputs: %d, localStorage: %d", len(before_hidden), len(before_ls))

    # === SC OAUTH ===
    await page.evaluate(f"""async () => {{
        const fd = new URLSearchParams();
        fd.append('fan_gate_id', '{gate_id}');
        fd.append('comment_sc', 'Great track!');
        await fetch('/setSC', {{ method: 'POST', body: fd.toString(), credentials: 'include',
            headers: {{ 'Content-Type': 'application/x-www-form-urlencoded', 'X-Requested-With': 'XMLHttpRequest', 'X-CSRF-TOKEN': '{csrf}' }}
        }});
    }}""")

    oauth_url = await page.evaluate("""() => {
        const btns = document.querySelectorAll('#login_to_sc');
        for (const btn of btns) {
            const attr = btn.getAttribute('data-onclick') || '';
            const match = attr.match(/PopupCenterDual\\('([^']+)'/);
            if (match) return match[1];
        }
        return null;
    }""")

    popup_responses = []
    popup_auth2_html = None

    if oauth_url:
        try:
            async with page.expect_popup(timeout=15000) as popup_info:
                await page.evaluate(f"window.open('{oauth_url}', 'sc_popup', 'width=800,height=500')")
            popup = await popup_info.value

            # Capture ALL popup responses
            async def capture_popup_resp(resp):
                url = resp.url
                try:
                    body = await resp.text()
                except:
                    body = "(unreadable)"
                entry = {"url": url, "status": resp.status, "body": body[:2000]}
                popup_responses.append(entry)
                if "auth2" in url or "hypeddit" in url:
                    logger.info("POPUP RESP: %d %s body=%s", resp.status, url[:100], body[:500])

            popup.on("response", capture_popup_resp)

            await popup.wait_for_load_state("domcontentloaded")
            await asyncio.sleep(3)

            # Click Allow
            auth_btn = await popup.query_selector('#submit_approval')
            if auth_btn:
                await auth_btn.click()
                logger.info("Clicked Allow button")
            else:
                popup_text = await popup.evaluate("() => document.body?.innerText || ''")
                logger.info("No Allow button. Popup text: %s", popup_text[:200])

            # Wait for popup to process auth2.php and close
            for i in range(30):
                await asyncio.sleep(1)
                if popup.is_closed():
                    logger.info("Popup closed after %ds", i+1)
                    break
                # Try to capture auth2.php response
                try:
                    if "auth2" in popup.url or "hypeddit" in popup.url:
                        html = await popup.evaluate("() => document.documentElement.outerHTML")
                        popup_auth2_html = html
                        logger.info("auth2 page HTML (first 1000): %s", html[:1000])
                except:
                    pass
            else:
                logger.warning("Popup did not close after 30s")
                try:
                    html = await popup.evaluate("() => document.documentElement.outerHTML")
                    popup_auth2_html = html
                    logger.info("Final popup HTML: %s", html[:1000])
                    await popup.close()
                except:
                    pass

        except Exception as e:
            logger.error("OAuth error: %s", e)

    logger.info("=== POPUP RESPONSES (%d) ===", len(popup_responses))
    for i, r in enumerate(popup_responses):
        if "auth2" in r["url"] or "hypeddit" in r["url"]:
            logger.info("  [%d] %d %s", i, r["status"], r["url"][:100])
            logger.info("  BODY: %s", r["body"][:500])

    # === CAPTURE STATE AFTER OAUTH ===
    await asyncio.sleep(2)
    after_hidden = await page.evaluate("""() => {
        const r = {};
        document.querySelectorAll('input[type="hidden"]').forEach(i => {
            if (i.name || i.id) r[(i.id || i.name)] = i.value;
        });
        return r;
    }""")
    after_ls = await page.evaluate("""() => {
        const r = {};
        for (let i = 0; i < localStorage.length; i++) {
            const k = localStorage.key(i);
            r[k] = localStorage.getItem(k);
        }
        return r;
    }""")

    # Compare hidden inputs
    new_inputs = {k: v for k, v in after_hidden.items() if k not in before_hidden}
    changed_inputs = {k: (before_hidden[k], v) for k, v in after_hidden.items() if k in before_hidden and before_hidden[k] != v}
    logger.info("NEW hidden inputs after OAuth: %s", json.dumps(new_inputs, indent=2))
    logger.info("CHANGED hidden inputs after OAuth: %s", json.dumps(changed_inputs, indent=2))

    # Compare localStorage
    new_ls = {k: v for k, v in after_ls.items() if k not in before_ls}
    changed_ls = {k: (before_ls[k], v) for k, v in after_ls.items() if k in before_ls and before_ls[k] != v}
    logger.info("NEW localStorage after OAuth: %s", json.dumps(new_ls, indent=2))
    logger.info("CHANGED localStorage after OAuth: %s", json.dumps(changed_ls, indent=2))

    # === Check cookies ===
    cookies = await ctx.cookies()
    hypeddit_cookies = [c for c in cookies if "hypeddit" in c.get("domain", "")]
    logger.info("Hypeddit cookies (%d):", len(hypeddit_cookies))
    for c in hypeddit_cookies:
        logger.info("  %s = %s... (path=%s secure=%s httpOnly=%s)", c["name"], str(c["value"])[:50], c.get("path"), c.get("secure"), c.get("httpOnly"))

    # === Call /windowopenerlog ===
    wol = await page.evaluate(f"""async () => {{
        const fd = new URLSearchParams();
        fd.append('elementID', 'login_to_sc');
        fd.append('fangate_id', '{gate_id}');
        const r = await fetch('/windowopenerlog', {{
            method: 'POST', body: fd.toString(), credentials: 'include',
            headers: {{ 'Content-Type': 'application/x-www-form-urlencoded', 'X-Requested-With': 'XMLHttpRequest', 'X-CSRF-TOKEN': '{csrf}' }},
        }});
        return {{ status: r.status, body: (await r.text()).substring(0, 300) }};
    }}""")
    logger.info("/windowopenerlog: %s", json.dumps(wol))

    # === getGatePathway ===
    pathway = await page.evaluate(f"""async () => {{
        const fd = new URLSearchParams();
        fd.append('fan_gate_id', '{gate_id}');
        const r = await fetch('/getGatePathway', {{
            method: 'POST', body: fd.toString(), credentials: 'include',
            headers: {{ 'Content-Type': 'application/x-www-form-urlencoded', 'X-Requested-With': 'XMLHttpRequest', 'X-CSRF-TOKEN': '{csrf}' }},
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
        for (const s of ['email', 'sc']) {{
            if (!fd.getAll('skip_gate_steps[]').includes(s)) fd.append('skip_gate_steps[]', s);
        }}
        const r = await fetch('/gate/download/ul', {{
            method: 'POST', body: fd.toString(), credentials: 'include',
            headers: {{ 'Content-Type': 'application/x-www-form-urlencoded', 'X-Requested-With': 'XMLHttpRequest', 'X-CSRF-TOKEN': '{csrf}' }},
        }});
        return {{ status: r.status, body: (await r.text()).substring(0, 500) }};
    }}""")
    logger.info("DOWNLOAD: %s", json.dumps(dl))

    # Also dump what the download form WOULD submit
    form_data = await page.evaluate("""() => {
        const fd = {};
        document.querySelectorAll('input[type="hidden"]').forEach(i => {
            const key = i.name || i.id;
            if (key) {
                if (fd[key]) {
                    if (!Array.isArray(fd[key])) fd[key] = [fd[key]];
                    fd[key].push(i.value);
                } else {
                    fd[key] = i.value;
                }
            }
        });
        return fd;
    }""")
    logger.info("Form data that would be submitted: %s", json.dumps(form_data, indent=2))

    await asyncio.sleep(15)
    await ctx.close()
    await pw.stop()


if __name__ == "__main__":
    asyncio.run(main())
