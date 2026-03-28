"""Scan many gates from test-fresh50.json to find simple step configurations."""
import asyncio
import json
import logging
from pathlib import Path

from playwright.async_api import async_playwright

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

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

    with open("test-fresh50.json", "r", encoding="utf-8") as f:
        tracks = json.load(f)

    results = []
    for i, t in enumerate(tracks):
        url = t.get("url", "")
        if not url or "hypeddit.com" not in url:
            continue

        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=10000)
            await asyncio.sleep(1.5)

            info = await page.evaluate("""() => {
                return {
                    gate_id: document.querySelector('#fan_gate_id')?.value || '',
                    steps: document.querySelector('#steps_select')?.value || '',
                    nwSteps: document.querySelector('#nwSteps')?.value || '',
                    is_skippable: document.querySelector('#is_skippable')?.value || '',
                    comment_sc: document.querySelector('#comment_sc')?.value || '',
                };
            }""")
            info['url'] = url
            info['title'] = t.get('title', '')[:50]
            results.append(info)

            nw = [s for s in (info['nwSteps'] or '').split(',') if s]
            logger.info("[%d] %s → nw=%s skip=%s", i, url.split("/")[-1][:30], info['nwSteps'], info['is_skippable'])

        except Exception as e:
            logger.error("[%d] %s: %s", i, url.split("/")[-1][:30], str(e)[:60])

    # Summary
    logger.info("\n=== SUMMARY ===")
    for r in results:
        nw = [s for s in (r['nwSteps'] or '').split(',') if s]
        tag = ""
        if len(nw) == 1 and nw[0] == 'sc':
            tag = " *** SC-ONLY ***"
        elif len(nw) == 1 and nw[0] == 'email':
            tag = " *** EMAIL-ONLY ***"
        elif r['is_skippable'] == '1':
            tag = " *** SKIPPABLE ***"
        elif len(nw) == 0:
            tag = " *** NO STEPS ***"
        elif len(nw) == 1:
            tag = f" *** {nw[0].upper()}-ONLY ***"

        if tag:
            logger.info("  %s%s (nw=%s skip=%s)", r['url'].split("/")[-1][:40], tag, r['nwSteps'], r['is_skippable'])

    await ctx.close()
    await pw.stop()


if __name__ == "__main__":
    asyncio.run(main())
