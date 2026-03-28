"""Test with a DIFFERENT gate + track session cookies across the flow."""
import asyncio
import json
import random
import logging
from pathlib import Path

from playwright.async_api import async_playwright

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# Try multiple gates from batch 1
GATES = [
    "https://hypeddit.com/sunnysea/sunnyseaeditsvoliv",
    "https://hypeddit.com/wublok/staticxpushitbootleg",
    "https://hypeddit.com/houzmusic/onemoretimevalmeredithzrx",
    "https://hypeddit.com/darrenafter/thebombdarrenafterrework",
]
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


async def test_gate(ctx, gate_url):
    logger.info("========================================")
    logger.info("Testing: %s", gate_url)
    logger.info("========================================")

    page = await ctx.new_page()
    api_responses = []

    async def on_resp(resp):
        kws = ["download/ul", "verifyEmail", "getGatePathway", "setSC", "windowopener", "setGatePathwayOr", "auth2"]
        if "hypeddit.com" in resp.url and any(k in resp.url for k in kws):
            try:
                body = await resp.text()
            except:
                body = "?"
            entry = {"url": resp.url, "status": resp.status, "body": body[:500]}
            api_responses.append(entry)
            logger.info("  <<< %d %s body=%s", resp.status, resp.url.split("hypeddit.com")[-1][:60], body[:200])

    page.on("response", on_resp)

    await page.goto(gate_url, wait_until="domcontentloaded")
    await asyncio.sleep(3)
    await page.evaluate("document.cookie='teb3456767win=;expires=Thu,01 Jan 1970 00:00:00 UTC;path=/;'")

    # Get metadata
    meta = await page.evaluate("""() => {
        const r = {};
        document.querySelectorAll('input[type="hidden"]').forEach(i => { if (i.id) r[i.id] = i.value; });
        r.csrf = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';
        return r;
    }""")
    gate_id = meta.get("fan_gate_id", "")
    steps = meta.get("steps_select", "")
    csrf = meta.get("csrf", "")
    is_skippable = meta.get("is_skippable", "?")
    logger.info("Gate: id=%s steps=%s skippable=%s", gate_id, steps, is_skippable)

    if not gate_id:
        logger.warning("No gate_id found, skipping")
        await page.close()
        return {"url": gate_url, "status": "NO_GATE_ID"}

    # Log session cookie
    cookies = await ctx.cookies()
    session = [c for c in cookies if c["name"] == "laravel_session" and "hypeddit" in c.get("domain", "")]
    if session:
        logger.info("Session cookie: %s... (sameSite=%s)", session[0]["value"][:30], session[0].get("sameSite"))

    # Activate
    await page.evaluate("document.querySelector('#gateDownloadButton')?.click()")
    await asyncio.sleep(3)
    csrf = await page.evaluate("document.querySelector('meta[name=\"csrf-token\"]')?.getAttribute('content')||''")

    # Process steps
    step_list = [s for s in steps.split(",") if s and s != "dw"]
    results = {"url": gate_url, "gate_id": gate_id, "steps": step_list, "skippable": is_skippable}

    for step in step_list:
        if step == "email":
            email = gen_alias(EMAIL)
            await page.evaluate(f"""() => {{
                const n = document.querySelector('#email_name');
                if (n) {{ n.value = {repr(NAME)}; n.dispatchEvent(new Event('input',{{bubbles:true}})); }}
                const a = document.querySelector('#email_address');
                if (a) {{ a.value = {repr(email)}; a.dispatchEvent(new Event('input',{{bubbles:true}})); }}
            }}""")
            await asyncio.sleep(0.5)
            await page.evaluate("(jQuery||$)('#email_to_downloads_next').trigger('click');")
            await asyncio.sleep(5)

            verify = [e for e in api_responses if "verifyEmail" in e["url"]]
            email_status = verify[-1]["body"] if verify else "NO_RESPONSE"
            results["email"] = email_status
            logger.info("Email result: %s", email_status)

            # Advance
            await page.evaluate("""() => {
                const e = document.querySelector('.fangate-slider-content.email.current-slide');
                if (e) { e.classList.remove('current-slide'); e.classList.add('move-left'); }
                const steps = (document.querySelector('#steps_select')?.value||'').split(',');
                const idx = steps.indexOf('email');
                for (let i = idx+1; i < steps.length; i++) {
                    const n = document.querySelector('.fangate-slider-content.' + steps[i]);
                    if (n) { n.classList.remove('upcomming-slide'); n.classList.add('current-slide','zindex'); break; }
                }
            }""")
            await asyncio.sleep(1)

        elif step == "sc":
            # Comment
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
                        logger.info("SC: Clicked Allow")
                        results["sc_allow"] = True
                    else:
                        popup_text = await popup.evaluate("() => document.body?.innerText||''")
                        logger.info("SC: No Allow button. Text: %s", popup_text[:100])
                        results["sc_allow"] = False
                    for _ in range(20):
                        await asyncio.sleep(1)
                        if popup.is_closed():
                            logger.info("SC: Popup closed")
                            results["sc_popup_closed"] = True
                            break
                    else:
                        results["sc_popup_closed"] = False
                except Exception as e:
                    results["sc_error"] = str(e)
                    logger.error("SC error: %s", e)

            # Advance
            await page.evaluate("""() => {
                const s = document.querySelector('.fangate-slider-content.sc.current-slide');
                if (s) { s.classList.remove('current-slide'); s.classList.add('move-left'); }
                const dw = document.querySelector('.fangate-slider-content.dw');
                if (dw) { dw.classList.remove('upcomming-slide'); dw.classList.add('current-slide','zindex'); }
            }""")
            await asyncio.sleep(1)

        else:
            # Social step - skip
            logger.info("Skipping social step: %s", step)

    # Download
    await asyncio.sleep(2)
    dl = await page.evaluate(f"""async () => {{
        const fd = new URLSearchParams();
        document.querySelectorAll('input[type="hidden"]').forEach(i => {{
            if (i.name) fd.append(i.name, i.value);
        }});
        const r = await fetch('/gate/download/ul', {{ method:'POST', body:fd.toString(), credentials:'include',
            headers:{{'Content-Type':'application/x-www-form-urlencoded','X-Requested-With':'XMLHttpRequest','X-CSRF-TOKEN':'{csrf}'}}
        }});
        return (await r.text()).substring(0,500);
    }}""")
    logger.info("DOWNLOAD: %s", dl)
    results["download"] = dl

    try:
        dl_json = json.loads(dl)
        results["download_status"] = dl_json.get("download_status")
        results["social_currency"] = dl_json.get("social_currency")
    except:
        pass

    await page.close()
    return results


async def main():
    pw = await async_playwright().start()
    logger.info("=== MULTI-GATE TEST ===")

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

    all_results = []
    for gate_url in GATES:
        result = await test_gate(ctx, gate_url)
        all_results.append(result)
        logger.info("Result: %s", json.dumps(result, indent=2))

    logger.info("\n=== SUMMARY ===")
    for r in all_results:
        logger.info("%s: download=%s sc=%s email=%s",
                     r.get("url", "?")[-40:],
                     r.get("download_status"),
                     r.get("sc_allow"),
                     r.get("email", "?")[:30])

    await asyncio.sleep(10)
    await ctx.close()
    await pw.stop()


if __name__ == "__main__":
    asyncio.run(main())
