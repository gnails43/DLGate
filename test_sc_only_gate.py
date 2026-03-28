"""Find and test a gate that has ONLY SC step (no SP, no email).
If SC-only gate download works, we know SC auth is working and the issue is just needing all steps.
"""
import asyncio
import json
import logging
from pathlib import Path

from playwright.async_api import async_playwright

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# Try multiple gates and check their step requirements
GATES_TO_CHECK = [
    "https://hypeddit.com/sunnysea/sunnyseaeditsvoliv",
    "https://hypeddit.com/wublok/staticxpushitbootleg",
    "https://hypeddit.com/darrenafter/thebombdarrenafterrework",
    "https://hypeddit.com/cliqueaudio/bassrocketdontcallmelatinfreeedit",
    "https://hypeddit.com/djhitzo/marshmellohappier",
]

PROFILE_DIR = str(Path("C:/GitHub/DLGate/.claude/worktrees/vigilant-ramanujan/.browser_profile").resolve())


async def main():
    pw = await async_playwright().start()
    logger.info("=== SCAN: Find SC-only gates ===")

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

    # First, scan all gates for their step requirements
    gate_info = []
    page = ctx.pages[0] if ctx.pages else await ctx.new_page()

    for url in GATES_TO_CHECK:
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=15000)
            await asyncio.sleep(2)

            info = await page.evaluate("""() => {
                return {
                    gate_id: document.querySelector('#fan_gate_id')?.value || '',
                    steps: document.querySelector('#steps_select')?.value || '',
                    nwSteps: document.querySelector('#nwSteps')?.value || '',
                    is_skippable: document.querySelector('#is_skippable')?.value || '',
                    is_unlimited: document.querySelector('#is_unlimited')?.value || '',
                    comment_sc: document.querySelector('#comment_sc')?.value || '',
                };
            }""")
            info['url'] = url
            gate_info.append(info)
            logger.info("Gate: %s → steps=%s nwSteps=%s skippable=%s sc_comment=%s",
                        url.split("/")[-1], info['steps'], info['nwSteps'],
                        info['is_skippable'], info['comment_sc'])
        except Exception as e:
            logger.error("Error loading %s: %s", url, e)

    # Also check our test-fresh50.json for gate URLs
    try:
        with open("test-fresh50.json", "r") as f:
            tracks = json.load(f)
        # Try some that we haven't processed
        for t in tracks[24:35]:
            gate_url = t.get("gate_url") or t.get("url", "")
            if gate_url and "hypeddit.com" in gate_url and gate_url not in [g['url'] for g in gate_info]:
                try:
                    await page.goto(gate_url, wait_until="domcontentloaded", timeout=15000)
                    await asyncio.sleep(2)
                    info = await page.evaluate("""() => {
                        return {
                            gate_id: document.querySelector('#fan_gate_id')?.value || '',
                            steps: document.querySelector('#steps_select')?.value || '',
                            nwSteps: document.querySelector('#nwSteps')?.value || '',
                            is_skippable: document.querySelector('#is_skippable')?.value || '',
                            comment_sc: document.querySelector('#comment_sc')?.value || '',
                        };
                    }""")
                    info['url'] = gate_url
                    gate_info.append(info)
                    logger.info("Gate: %s → steps=%s nwSteps=%s skippable=%s",
                                gate_url.split("/")[-1], info['steps'], info['nwSteps'], info['is_skippable'])
                except Exception as e:
                    logger.error("Error: %s %s", gate_url.split("/")[-1], e)
    except:
        pass

    # Find gates with only SC or only email
    logger.info("\n=== GATE SUMMARY ===")
    sc_only = []
    email_only = []
    skippable = []
    for g in gate_info:
        nw = [s for s in (g['nwSteps'] or '').split(',') if s and s != 'dw']
        steps = g['steps']
        logger.info("  %s: nwSteps=%s skippable=%s", g['url'].split("/")[-1], g['nwSteps'], g['is_skippable'])
        if nw == ['sc']:
            sc_only.append(g)
        if nw == ['email'] or (not nw and 'email' in steps):
            email_only.append(g)
        if g['is_skippable'] == '1':
            skippable.append(g)

    logger.info("\nSC-only gates: %d", len(sc_only))
    for g in sc_only:
        logger.info("  %s", g['url'])
    logger.info("Email-only gates: %d", len(email_only))
    for g in email_only:
        logger.info("  %s", g['url'])
    logger.info("Skippable gates: %d", len(skippable))
    for g in skippable:
        logger.info("  %s (steps=%s)", g['url'], g['nwSteps'])

    # === TEST: Try email-only gate or skippable gate ===
    test_gate = None
    if email_only:
        test_gate = email_only[0]
        logger.info("\n=== TESTING EMAIL-ONLY GATE: %s ===", test_gate['url'])
    elif skippable:
        test_gate = skippable[0]
        logger.info("\n=== TESTING SKIPPABLE GATE: %s ===", test_gate['url'])
    elif sc_only:
        test_gate = sc_only[0]
        logger.info("\n=== TESTING SC-ONLY GATE: %s ===", test_gate['url'])

    if test_gate:
        await page.goto(test_gate['url'], wait_until="domcontentloaded")
        await asyncio.sleep(3)
        await page.evaluate("document.cookie='teb3456767win=;expires=Thu,01 Jan 1970 00:00:00 UTC;path=/;'")

        gate_id = await page.evaluate("document.querySelector('#fan_gate_id')?.value||''")
        csrf = await page.evaluate("document.querySelector('meta[name=\"csrf-token\"]')?.getAttribute('content')||''")

        # Activate
        await page.evaluate("document.querySelector('#gateDownloadButton')?.click()")
        await asyncio.sleep(3)
        csrf = await page.evaluate("document.querySelector('meta[name=\"csrf-token\"]')?.getAttribute('content')||''")

        # Try direct download (for skippable gates)
        if test_gate.get('is_skippable') == '1':
            logger.info("Gate is skippable, trying download with skip...")
            dl = await page.evaluate(f"""async () => {{
                var downloadlink = jQuery("#current_download_file_listner").val();
                var wrndk = jQuery("#wrndk").val();
                var steps = jQuery("#nwSteps").val();
                var skip = steps ? steps.split(',') : [];
                return await new Promise((resolve) => {{
                    jQuery.ajax({{
                        type: "POST", url: "/gate/download/ul",
                        dataType: "json",
                        data: {{
                            file: encodeURIComponent(downloadlink),
                            download_visit: 'true', profile_downloads: 'true',
                            time: Math.floor(Math.random() * 300000),
                            page: 'nonsingle', is_skippable: '1',
                            steps: steps, download_action: 'DOWNLOAD',
                            skip_gate_steps: skip, wrndk: wrndk, is_mobile: '',
                        }},
                        success: function(res) {{ resolve(JSON.stringify(res)); }},
                        error: function(xhr) {{ resolve(xhr.responseText?.substring(0, 500) || 'ERROR'); }}
                    }});
                }});
            }}""")
            logger.info("SKIPPABLE DOWNLOAD: %s", dl[:500])

    await asyncio.sleep(5)
    await ctx.close()
    await pw.stop()


if __name__ == "__main__":
    asyncio.run(main())
