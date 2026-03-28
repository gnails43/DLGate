"""Test: Download WITHOUT skip_gate_steps[] for non-skippable gate.
Hypothesis: sending skip_gate_steps confuses server for is_skippable=0 gates.
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
    logger.info("=== TEST: Download WITHOUT skip_gate_steps ===")

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

    # Capture download API responses
    async def on_resp(resp):
        if "download/ul" in resp.url or "verifyEmail" in resp.url:
            try:
                body = await resp.text()
            except:
                body = "?"
            logger.info("<<< %d %s body=%s", resp.status, resp.url[:80], body[:300])
    page.on("response", on_resp)

    await page.goto(TEST_URL, wait_until="domcontentloaded")
    await asyncio.sleep(3)
    await page.evaluate("document.cookie='teb3456767win=;expires=Thu,01 Jan 1970 00:00:00 UTC;path=/;'")
    await page.evaluate("document.querySelector('#gateDownloadButton')?.click()")
    await asyncio.sleep(3)

    csrf = await page.evaluate("document.querySelector('meta[name=\"csrf-token\"]')?.getAttribute('content')||''")
    gate_id = await page.evaluate("document.querySelector('#fan_gate_id')?.value||''")
    is_skippable = await page.evaluate("document.querySelector('#is_skippable')?.value||''")
    logger.info("gate_id=%s is_skippable=%s", gate_id, is_skippable)

    # === EMAIL ===
    email = gen_alias(EMAIL)
    logger.info("Email: %s", email)
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

    # === SC OAuth ===
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
            for _ in range(20):
                await asyncio.sleep(1)
                if popup.is_closed():
                    logger.info("Popup closed")
                    break
        except Exception as e:
            logger.error("OAuth: %s", e)

    await asyncio.sleep(2)

    # === DOWNLOAD TESTS ===
    # Test 1: WITH skip_gate_steps (current behavior)
    logger.info("=== TEST 1: Download WITH skip_gate_steps ===")
    dl1 = await page.evaluate(f"""async () => {{
        const fd = new URLSearchParams();
        document.querySelectorAll('input[type="hidden"]').forEach(i => {{
            if (i.name) fd.append(i.name, i.value);
        }});
        fd.append('skip_gate_steps[]', 'email');
        fd.append('skip_gate_steps[]', 'sc');
        const r = await fetch('/gate/download/ul', {{ method:'POST', body:fd.toString(), credentials:'include',
            headers:{{'Content-Type':'application/x-www-form-urlencoded','X-Requested-With':'XMLHttpRequest','X-CSRF-TOKEN':'{csrf}'}}
        }});
        return {{ status:r.status, body:(await r.text()).substring(0,500) }};
    }}""")
    logger.info("WITH skip: %s", json.dumps(dl1))

    # Test 2: WITHOUT skip_gate_steps (just hidden inputs)
    logger.info("=== TEST 2: Download WITHOUT skip_gate_steps ===")
    dl2 = await page.evaluate(f"""async () => {{
        const fd = new URLSearchParams();
        document.querySelectorAll('input[type="hidden"]').forEach(i => {{
            if (i.name && i.name !== 'skip_gate_steps[]') fd.append(i.name, i.value);
        }});
        const r = await fetch('/gate/download/ul', {{ method:'POST', body:fd.toString(), credentials:'include',
            headers:{{'Content-Type':'application/x-www-form-urlencoded','X-Requested-With':'XMLHttpRequest','X-CSRF-TOKEN':'{csrf}'}}
        }});
        return {{ status:r.status, body:(await r.text()).substring(0,500) }};
    }}""")
    logger.info("WITHOUT skip: %s", json.dumps(dl2))

    # Test 3: Minimal form data (just essentials)
    logger.info("=== TEST 3: Minimal form data ===")
    file_id = await page.evaluate("document.querySelector('#current_download_file_listner')?.value||''")
    wrndk = await page.evaluate("document.querySelector('#wrndk')?.value||''")
    dl3 = await page.evaluate(f"""async () => {{
        const fd = new URLSearchParams();
        fd.append('file', '{file_id}');
        fd.append('download_visit', 'true');
        fd.append('wrndk', '{wrndk}');
        fd.append('download_action', 'DOWNLOAD');
        const r = await fetch('/gate/download/ul', {{ method:'POST', body:fd.toString(), credentials:'include',
            headers:{{'Content-Type':'application/x-www-form-urlencoded','X-Requested-With':'XMLHttpRequest','X-CSRF-TOKEN':'{csrf}'}}
        }});
        return {{ status:r.status, body:(await r.text()).substring(0,500) }};
    }}""")
    logger.info("MINIMAL: %s", json.dumps(dl3))

    # Test 4: Click the actual download button (native Hypeddit flow)
    logger.info("=== TEST 4: Native download button click ===")
    # Advance to DW slide
    await page.evaluate("""() => {
        document.querySelectorAll('.fangate-slider-content').forEach(s => {
            if (!s.className.includes('dw')) {
                s.classList.remove('current-slide','upcomming-slide','zindex');
                s.classList.add('move-left');
            }
        });
        const dw = document.querySelector('.fangate-slider-content.dw');
        if (dw) { dw.classList.remove('upcomming-slide','move-left'); dw.classList.add('current-slide','zindex'); }
    }""")
    await asyncio.sleep(1)

    # Find and click the actual download button on DW slide
    dl_btn_info = await page.evaluate("""() => {
        const dw = document.querySelector('.fangate-slider-content.dw.current-slide');
        if (!dw) return { error: 'no dw slide' };
        const btns = dw.querySelectorAll('a, button');
        const info = [];
        for (const b of btns) {
            info.push({
                tag: b.tagName,
                id: b.id,
                class: b.className,
                text: b.textContent.trim().substring(0, 50),
                href: b.href || '',
                onclick: b.getAttribute('onclick') || '',
                data_onclick: b.getAttribute('data-onclick') || '',
            });
        }
        return { buttons: info };
    }""")
    logger.info("DW slide buttons: %s", json.dumps(dl_btn_info, indent=2))

    # Try clicking the native download link
    native_click = await page.evaluate("""() => {
        const dw = document.querySelector('.fangate-slider-content.dw.current-slide');
        if (!dw) return 'no dw slide';
        // Look for the download function call
        const btn = dw.querySelector('a.hype-btn-green, a.hype-btn, button.hype-btn-green');
        if (btn) {
            const onclick = btn.getAttribute('onclick') || btn.getAttribute('data-onclick') || '';
            btn.click();
            return 'clicked: ' + btn.textContent.trim() + ' onclick=' + onclick.substring(0, 100);
        }
        return 'no download button found';
    }""")
    logger.info("Native click: %s", native_click)
    await asyncio.sleep(5)

    await asyncio.sleep(10)
    await ctx.close()
    await pw.stop()


if __name__ == "__main__":
    asyncio.run(main())
