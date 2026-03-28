"""Get full PopupCenterDual function and check hidden inputs after gate activation."""
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

    # 1. PopupCenterDual full source
    popup_fn = await page.evaluate("PopupCenterDual.toString()")
    logger.info("=== PopupCenterDual ===\n%s", popup_fn)

    # 2. ALL hidden inputs on the page
    hidden_inputs = await page.evaluate("""() => {
        const inputs = document.querySelectorAll('input[type="hidden"]');
        return Array.from(inputs).map(i => ({
            name: i.name, id: i.id, value: i.value.substring(0, 100)
        }));
    }""")
    logger.info("=== Hidden inputs (%d) ===", len(hidden_inputs))
    for inp in hidden_inputs:
        logger.info("  %s", json.dumps(inp))

    # 3. Activate gate
    await page.evaluate("document.querySelector('#gateDownloadButton')?.click()")
    await asyncio.sleep(3)

    # 4. Hidden inputs AFTER activation
    hidden_inputs2 = await page.evaluate("""() => {
        const inputs = document.querySelectorAll('input[type="hidden"]');
        return Array.from(inputs).map(i => ({
            name: i.name, id: i.id, value: i.value.substring(0, 100)
        }));
    }""")
    logger.info("=== Hidden inputs AFTER activate (%d) ===", len(hidden_inputs2))
    new_inputs = [i for i in hidden_inputs2 if i not in hidden_inputs]
    for inp in new_inputs:
        logger.info("  NEW: %s", json.dumps(inp))

    # 5. Check #nwSteps vs #steps_select
    nw_steps = await page.evaluate("$('#nwSteps').val() || 'NOT FOUND'")
    steps_select = await page.evaluate("$('#steps_select').val() || 'NOT FOUND'")
    logger.info("nwSteps=%s steps_select=%s", nw_steps, steps_select)

    # 6. Check jsonGateData
    gate_data = await page.evaluate("typeof jsonGateData !== 'undefined' ? JSON.stringify(jsonGateData).substring(0, 2000) : 'NOT FOUND'")
    logger.info("jsonGateData: %s", gate_data[:500])

    # 7. What does the NATIVE download button look like (the one on the DW slide)?
    dw_info = await page.evaluate("""() => {
        const dw = document.querySelector('.fangate-slider-content.dw');
        if (!dw) return 'no dw slide';
        return {
            html: dw.innerHTML.substring(0, 3000),
            buttons: Array.from(dw.querySelectorAll('a, button')).map(b => ({
                tag: b.tagName, id: b.id, class: b.className.substring(0, 100),
                text: b.textContent.trim().substring(0, 50),
                onclick: (b.getAttribute('onclick') || '').substring(0, 200),
                data_onclick: (b.getAttribute('data-onclick') || '').substring(0, 200),
                data_type: b.getAttribute('data-type') || '',
            }))
        };
    }""")
    logger.info("DW slide info: %s", json.dumps(dw_info, indent=2)[:2000])

    await ctx.close()
    await pw.stop()

if __name__ == "__main__":
    asyncio.run(main())
