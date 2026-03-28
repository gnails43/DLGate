"""Check server session state: call /getSC, /getGatePathway, etc.
Also test: after auth2.php, reload gate, re-activate, check social_currency.
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
    logger.info("=== Check server session state ===")

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

    gate_id = await page.evaluate("document.querySelector('#fan_gate_id')?.value||''")
    csrf = await page.evaluate("document.querySelector('meta[name=\"csrf-token\"]')?.getAttribute('content')||''")
    logger.info("Gate: id=%s", gate_id)

    # === CHECK 1: Before anything ===
    logger.info("=== BEFORE ANYTHING ===")
    for endpoint in ['/getSC', '/getGatePathway', '/getEmail']:
        result = await page.evaluate(f"""async () => {{
            const fd = new URLSearchParams();
            fd.append('fan_gate_id', '{gate_id}');
            const r = await fetch('{endpoint}', {{ method:'POST', body:fd.toString(), credentials:'include',
                headers:{{'Content-Type':'application/x-www-form-urlencoded','X-Requested-With':'XMLHttpRequest','X-CSRF-TOKEN':'{csrf}'}}
            }});
            return {{ status: r.status, body: (await r.text()).substring(0, 300) }};
        }}""")
        logger.info("  %s: %s", endpoint, json.dumps(result))

    # === Activate gate ===
    await page.evaluate("document.querySelector('#gateDownloadButton')?.click()")
    await asyncio.sleep(3)
    csrf = await page.evaluate("document.querySelector('meta[name=\"csrf-token\"]')?.getAttribute('content')||''")

    # === CHECK 2: After activation ===
    logger.info("=== AFTER ACTIVATION ===")
    for endpoint in ['/getSC', '/getGatePathway']:
        result = await page.evaluate(f"""async () => {{
            const fd = new URLSearchParams();
            fd.append('fan_gate_id', '{gate_id}');
            const r = await fetch('{endpoint}', {{ method:'POST', body:fd.toString(), credentials:'include',
                headers:{{'Content-Type':'application/x-www-form-urlencoded','X-Requested-With':'XMLHttpRequest','X-CSRF-TOKEN':'{csrf}'}}
            }});
            return {{ status: r.status, body: (await r.text()).substring(0, 300) }};
        }}""")
        logger.info("  %s: %s", endpoint, json.dumps(result))

    # === SC Comment ===
    await page.evaluate(f"""async () => {{
        const fd = new URLSearchParams();
        fd.append('fan_gate_id', '{gate_id}');
        fd.append('comment_sc', 'Great track!');
        const r = await fetch('/setSC', {{ method:'POST', body:fd.toString(), credentials:'include',
            headers:{{'Content-Type':'application/x-www-form-urlencoded','X-Requested-With':'XMLHttpRequest','X-CSRF-TOKEN':'{csrf}'}}
        }});
        return (await r.text()).substring(0, 200);
    }}""")

    # === SC OAuth with relay ===
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

            async def intercept(route):
                url = route.request.url
                if "hypeddit.com/auth2.php" in url:
                    nonlocal auth2_url
                    auth2_url = url
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
                logger.info("Clicked SC Allow")

            for _ in range(15):
                await asyncio.sleep(1)
                if popup.is_closed() or auth2_url:
                    break
            if not popup.is_closed():
                try: await popup.close()
                except: pass
        except Exception as e:
            logger.error("OAuth: %s", e)

    if auth2_url:
        https_url = auth2_url.replace("http://", "https://") if auth2_url.startswith("http://") else auth2_url

        # === METHOD A: Fetch from main page ===
        logger.info("=== METHOD A: fetch auth2.php from main page ===")
        result_a = await page.evaluate(f"""async () => {{
            const r = await fetch('{https_url}', {{
                method: 'GET',
                credentials: 'include',
            }});
            return {{ status: r.status, body: (await r.text()).substring(0, 300) }};
        }}""")
        logger.info("auth2 result: %s", json.dumps(result_a))

        # === CHECK 3: After auth2 fetch ===
        logger.info("=== AFTER AUTH2 FETCH ===")
        csrf = await page.evaluate("document.querySelector('meta[name=\"csrf-token\"]')?.getAttribute('content')||''")
        for endpoint in ['/getSC', '/getGatePathway']:
            result = await page.evaluate(f"""async () => {{
                const fd = new URLSearchParams();
                fd.append('fan_gate_id', '{gate_id}');
                const r = await fetch('{endpoint}', {{ method:'POST', body:fd.toString(), credentials:'include',
                    headers:{{'Content-Type':'application/x-www-form-urlencoded','X-Requested-With':'XMLHttpRequest','X-CSRF-TOKEN':'{csrf}'}}
                }});
                return {{ status: r.status, body: (await r.text()).substring(0, 300) }};
            }}""")
            logger.info("  %s: %s", endpoint, json.dumps(result))

        # === Download attempt 1: same page ===
        dl1 = await page.evaluate(f"""async () => {{
            var downloadlink = jQuery("#current_download_file_listner").val();
            var wrndk = jQuery("#wrndk").val();
            var is_skippable = jQuery("#is_skippable").val();
            var steps = jQuery("#nwSteps").val();
            var postData = {{
                file: encodeURIComponent(downloadlink),
                download_visit: 'true',
                profile_downloads: 'true',
                time: Math.floor(Math.random() * 313000),
                sc_comment_text: 'Great track!',
                page: 'nonsingle',
                is_skippable: is_skippable,
                steps: steps,
                download_action: 'DOWNLOAD',
                skip_gate_steps: [],
                wrndk: wrndk,
                is_mobile: '',
            }};
            return await new Promise((resolve) => {{
                jQuery.ajax({{
                    type: "POST", url: "/gate/download/ul",
                    dataType: "json", data: postData,
                    success: function(res) {{ resolve(JSON.stringify(res)); }},
                    error: function(xhr) {{ resolve(xhr.responseText?.substring(0, 500) || 'ERROR'); }}
                }});
            }});
        }}""")
        logger.info("Download 1 (same page): %s", dl1[:300])

        # === METHOD B: Navigate new tab to auth2, then back ===
        # Actually, let's try reloading the gate and checking SC state
        logger.info("=== RELOAD GATE AND RE-CHECK ===")
        await page.goto(TEST_URL, wait_until="domcontentloaded")
        await asyncio.sleep(3)
        await page.evaluate("document.cookie='teb3456767win=;expires=Thu,01 Jan 1970 00:00:00 UTC;path=/;'")

        csrf = await page.evaluate("document.querySelector('meta[name=\"csrf-token\"]')?.getAttribute('content')||''")
        gate_id = await page.evaluate("document.querySelector('#fan_gate_id')?.value||''")

        for endpoint in ['/getSC', '/getGatePathway']:
            result = await page.evaluate(f"""async () => {{
                const fd = new URLSearchParams();
                fd.append('fan_gate_id', '{gate_id}');
                const r = await fetch('{endpoint}', {{ method:'POST', body:fd.toString(), credentials:'include',
                    headers:{{'Content-Type':'application/x-www-form-urlencoded','X-Requested-With':'XMLHttpRequest','X-CSRF-TOKEN':'{csrf}'}}
                }});
                return {{ status: r.status, body: (await r.text()).substring(0, 300) }};
            }}""")
            logger.info("  After reload %s: %s", endpoint, json.dumps(result))

        # Re-activate and try download
        await page.evaluate("document.querySelector('#gateDownloadButton')?.click()")
        await asyncio.sleep(3)
        csrf = await page.evaluate("document.querySelector('meta[name=\"csrf-token\"]')?.getAttribute('content')||''")

        dl2 = await page.evaluate(f"""async () => {{
            var downloadlink = jQuery("#current_download_file_listner").val();
            var wrndk = jQuery("#wrndk").val();
            return await new Promise((resolve) => {{
                jQuery.ajax({{
                    type: "POST", url: "/gate/download/ul",
                    dataType: "json",
                    data: {{
                        file: encodeURIComponent(downloadlink),
                        download_visit: 'true',
                        profile_downloads: 'true',
                        time: Math.floor(Math.random() * 313000),
                        sc_comment_text: 'Great track!',
                        page: 'nonsingle',
                        is_skippable: '0',
                        steps: 'sc,sp',
                        download_action: 'DOWNLOAD',
                        skip_gate_steps: [],
                        wrndk: wrndk,
                        is_mobile: '',
                    }},
                    success: function(res) {{ resolve(JSON.stringify(res)); }},
                    error: function(xhr) {{ resolve(xhr.responseText?.substring(0, 500) || 'ERROR'); }}
                }});
            }});
        }}""")
        logger.info("Download 2 (after reload): %s", dl2[:300])

    await asyncio.sleep(5)
    await ctx.close()
    await pw.stop()


if __name__ == "__main__":
    asyncio.run(main())
