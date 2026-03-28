"""Deep investigation: What JS functions exist for SC completion?
Look at PopupCenterDual, rX5mPQjW7s, localStorage listeners, etc.
"""
import asyncio
import json
import logging
from pathlib import Path

from playwright.async_api import async_playwright

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

TEST_URL = "https://hypeddit.com/houzmusic/onemoretimevalmeredithzrx"
PROFILE_DIR = str(Path("C:/GitHub/DLGate/.claude/worktrees/vigilant-ramanujan/.browser_profile").resolve())


async def main():
    pw = await async_playwright().start()
    logger.info("=== JS FLOW INVESTIGATION ===")

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

    # Capture ALL fetch/XHR
    all_requests = []
    async def on_request(req):
        if "hypeddit.com" in req.url and req.url != TEST_URL:
            method = req.method
            url = req.url.split("hypeddit.com")[-1]
            all_requests.append({"method": method, "url": url[:100]})

    all_responses = []
    async def on_response(resp):
        if "hypeddit.com" in resp.url:
            url = resp.url.split("hypeddit.com")[-1][:80]
            if any(k in url for k in ["download", "verify", "gateway", "Pathway", "setSC", "windowopener", "auth2", "setGate", "Pathway"]):
                try:
                    body = await resp.text()
                except:
                    body = "?"
                all_responses.append({"url": url, "status": resp.status, "body": body[:500]})
                logger.info("  <<< %d %s %s", resp.status, url, body[:200])

    page.on("request", on_request)
    page.on("response", on_response)

    await page.goto(TEST_URL, wait_until="domcontentloaded")
    await asyncio.sleep(3)
    await page.evaluate("document.cookie='teb3456767win=;expires=Thu,01 Jan 1970 00:00:00 UTC;path=/;'")

    gate_id = await page.evaluate("document.querySelector('#fan_gate_id')?.value||''")
    csrf = await page.evaluate("document.querySelector('meta[name=\"csrf-token\"]')?.getAttribute('content')||''")
    steps = await page.evaluate("document.querySelector('#steps_select')?.value||''")
    logger.info("Gate: id=%s steps=%s", gate_id, steps)

    # === INVESTIGATE JS FUNCTIONS ===

    # 1. What is PopupCenterDual?
    popup_fn = await page.evaluate("typeof PopupCenterDual === 'function' ? PopupCenterDual.toString().substring(0, 1000) : 'NOT FOUND'")
    logger.info("PopupCenterDual: %s", popup_fn[:500])

    # 2. What is rX5mPQjW7s (step completion)?
    step_fn = await page.evaluate("typeof rX5mPQjW7s === 'function' ? rX5mPQjW7s.toString().substring(0, 2000) : 'NOT FOUND'")
    logger.info("rX5mPQjW7s: %s", step_fn[:1000])

    # 3. What is jumpGate?
    jump_fn = await page.evaluate("typeof jumpGate === 'function' ? jumpGate.toString().substring(0, 1000) : 'NOT FOUND'")
    logger.info("jumpGate: %s", jump_fn[:500])

    # 4. localStorage listener?
    storage_listener = await page.evaluate("""() => {
        // Check if there's a storage event listener
        const events = window.getEventListeners ? window.getEventListeners(window) : {};
        return JSON.stringify(Object.keys(events || {}));
    }""")
    logger.info("Window event listeners: %s", storage_listener)

    # 5. Check what the SC login button's full data-onclick contains
    sc_onclick = await page.evaluate("""() => {
        const btns = document.querySelectorAll('#login_to_sc');
        const results = [];
        for (const btn of btns) {
            results.push({
                'data-onclick': btn.getAttribute('data-onclick') || '',
                'onclick': btn.getAttribute('onclick') || '',
                'class': btn.className,
                'parent_class': btn.parentElement?.className || '',
            });
        }
        return results;
    }""")
    logger.info("SC buttons: %s", json.dumps(sc_onclick, indent=2))

    # 6. What globals exist related to gate flow?
    gate_globals = await page.evaluate("""() => {
        const keys = ['PopupCenterDual', 'rX5mPQjW7s', 'jumpGate', 'hypeChildWindow',
                       'gatewayPopup', 'scPopup', 'popupWindow', 'popupTimer',
                       'checkPopup', 'setGatePathwayOr', 'windowopenerlog'];
        const result = {};
        for (const k of keys) {
            const v = window[k];
            if (v !== undefined) {
                result[k] = typeof v === 'function' ? 'function' : String(v).substring(0, 100);
            }
        }
        return result;
    }""")
    logger.info("Gate globals: %s", json.dumps(gate_globals, indent=2))

    # 7. Look for interval/timer that checks popup status
    # Search all script content for popup-related patterns
    scripts = await page.evaluate("""() => {
        const scripts = document.querySelectorAll('script:not([src])');
        let combined = '';
        for (const s of scripts) {
            const t = s.textContent;
            if (t.includes('popup') || t.includes('Popup') || t.includes('hypeChild') || t.includes('opener') || t.includes('windowopener')) {
                combined += '\\n===SCRIPT===\\n' + t.substring(0, 3000);
            }
        }
        return combined.substring(0, 10000);
    }""")
    logger.info("Popup-related scripts: %s", scripts[:3000])

    # 8. Check for setInterval/setTimeout that monitors popup
    timer_code = await page.evaluate("""() => {
        // Look for hypeChildWindow in localStorage handlers
        const scripts = document.querySelectorAll('script:not([src])');
        let found = '';
        for (const s of scripts) {
            const t = s.textContent;
            if (t.includes('setInterval') || t.includes('hypeChildWindow') || t.includes('storage')) {
                found += t.substring(0, 5000) + '\\n---\\n';
            }
        }
        return found.substring(0, 8000);
    }""")
    logger.info("Timer/storage scripts: %s", timer_code[:3000])

    # 9. External JS files that might contain the gate logic
    ext_scripts = await page.evaluate("""() => {
        const scripts = document.querySelectorAll('script[src]');
        return Array.from(scripts).map(s => s.src).filter(s => s.includes('hypeddit') || s.includes('gate') || s.includes('fan'));
    }""")
    logger.info("External scripts: %s", json.dumps(ext_scripts))

    # 10. Fetch and search external JS for popup/auth2 logic
    for src in ext_scripts[:3]:
        logger.info("Fetching: %s", src)
        content = await page.evaluate(f"""async () => {{
            try {{
                const r = await fetch('{src}');
                const t = await r.text();
                // Find popup/auth2 related code
                const lines = t.split('\\n');
                const matches = [];
                for (let i = 0; i < lines.length; i++) {{
                    const l = lines[i].toLowerCase();
                    if (l.includes('popup') || l.includes('auth2') || l.includes('hypechild') || l.includes('windowopener') || l.includes('gatepathway')) {{
                        matches.push({{ line: i, code: lines[i].substring(0, 200) }});
                    }}
                }}
                return {{ length: t.length, matches: matches.slice(0, 30) }};
            }} catch(e) {{
                return {{ error: e.message }};
            }}
        }}""")
        logger.info("  matches: %s", json.dumps(content, indent=2)[:2000])

    await asyncio.sleep(5)
    await ctx.close()
    await pw.stop()


if __name__ == "__main__":
    asyncio.run(main())
