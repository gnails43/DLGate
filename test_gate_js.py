"""Fetch gate-ul-preview.js and search for download/social_currency/pathway logic."""
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

    # Fetch gate-ul-preview.js (the main gate logic)
    gate_js = await page.evaluate("""async () => {
        const r = await fetch('/js/unlimited/gate-ul-preview.js?v=150.0.88');
        return await r.text();
    }""")

    # Save full file
    with open("gate-ul-preview.js", "w", encoding="utf-8") as f:
        f.write(gate_js)
    logger.info("Saved gate-ul-preview.js (%d bytes)", len(gate_js))

    # Search for key patterns
    lines = gate_js.split('\n')
    keywords = ['download', 'social_currency', 'getGatePathway', 'setGatePathway',
                'windowopener', 'auth2', 'login_to_sc', 'PopupCenter',
                'download_status', 'checkPopup', 'popupTimer', 'popupWindow']

    for kw in keywords:
        matches = [(i, l.strip()[:150]) for i, l in enumerate(lines) if kw.lower() in l.lower()]
        if matches:
            logger.info("=== %s (%d matches) ===", kw, len(matches))
            for line_no, text in matches[:10]:
                logger.info("  L%d: %s", line_no+1, text)

    # Also fetch verify-email-ul.js
    email_js = await page.evaluate("""async () => {
        const r = await fetch('/js/unlimited/verify-email-ul.js?v=150.0.88');
        return await r.text();
    }""")
    with open("verify-email-ul.js", "w", encoding="utf-8") as f:
        f.write(email_js)
    logger.info("Saved verify-email-ul.js (%d bytes)", len(email_js))

    # Also fetch scripts.js
    scripts_js = await page.evaluate("""async () => {
        const r = await fetch('/js/scripts.js?v=150.0.88');
        return await r.text();
    }""")
    with open("scripts.js", "w", encoding="utf-8") as f:
        f.write(scripts_js)
    logger.info("Saved scripts.js (%d bytes)", len(scripts_js))

    # Search scripts.js for same keywords
    lines2 = scripts_js.split('\n')
    for kw in keywords:
        matches = [(i, l.strip()[:150]) for i, l in enumerate(lines2) if kw.lower() in l.lower()]
        if matches:
            logger.info("=== scripts.js: %s (%d matches) ===", kw, len(matches))
            for line_no, text in matches[:10]:
                logger.info("  L%d: %s", line_no+1, text)

    await ctx.close()
    await pw.stop()


if __name__ == "__main__":
    asyncio.run(main())
