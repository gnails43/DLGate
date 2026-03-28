"""Test: 1) NO-STEPS gate download, 2) SC-ONLY gate with OAuth."""
import asyncio
import json
import random
import logging
from pathlib import Path

from playwright.async_api import async_playwright

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

NO_STEPS_URL = "https://hypeddit.com/deeyazlockitdownwha111-1"
SC_ONLY_URL = "https://hypeddit.com/espresso/espresso"  # just "sc"
PROFILE_DIR = str(Path("C:/GitHub/DLGate/.claude/worktrees/vigilant-ramanujan/.browser_profile").resolve())

EMAIL = "gna.k.fujisaki43@gmail.com"
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


async def test_download(page, ctx, url, label, do_sc=False):
    """Test download for a gate."""
    logger.info("\n========== %s: %s ==========", label, url)

    await page.goto(url, wait_until="domcontentloaded")
    await asyncio.sleep(3)
    await page.evaluate("document.cookie='teb3456767win=;expires=Thu,01 Jan 1970 00:00:00 UTC;path=/;'")

    gate_id = await page.evaluate("document.querySelector('#fan_gate_id')?.value||''")
    csrf = await page.evaluate("document.querySelector('meta[name=\"csrf-token\"]')?.getAttribute('content')||''")
    steps = await page.evaluate("document.querySelector('#steps_select')?.value||''")
    nw_steps = await page.evaluate("document.querySelector('#nwSteps')?.value||''")
    is_skip = await page.evaluate("document.querySelector('#is_skippable')?.value||''")
    comment_sc = await page.evaluate("document.querySelector('#comment_sc')?.value||''")
    logger.info("gate_id=%s steps=%s nwSteps=%s skippable=%s comment_sc=%s", gate_id, steps, nw_steps, is_skip, comment_sc)

    if not gate_id:
        logger.warning("No gate_id found!")
        return

    # Activate
    await page.evaluate("document.querySelector('#gateDownloadButton')?.click()")
    await asyncio.sleep(3)
    csrf = await page.evaluate("document.querySelector('meta[name=\"csrf-token\"]')?.getAttribute('content')||''")

    if do_sc and 'sc' in (nw_steps or '').split(','):
        # Set comment
        if comment_sc == '1':
            await page.evaluate(f"""async () => {{
                const fd = new URLSearchParams();
                fd.append('fan_gate_id', '{gate_id}');
                fd.append('comment_sc', 'Great track!');
                await fetch('/setSC', {{ method:'POST', body:fd.toString(), credentials:'include',
                    headers:{{'Content-Type':'application/x-www-form-urlencoded','X-Requested-With':'XMLHttpRequest','X-CSRF-TOKEN':'{csrf}'}}
                }});
            }}""")
            await page.evaluate("$('#sc_comment_text').val('Great track!')")

        # Get OAuth URL
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
                        logger.info("CAPTURED auth2: %s", url[:100])
                        # Fulfill with the auth2 response fetched from main page
                        https_url = url.replace("http://", "https://") if url.startswith("http://") else url
                        result = await page.evaluate(f"""async () => {{
                            const r = await fetch('{https_url}', {{ credentials: 'include' }});
                            return {{ status: r.status, body: await r.text() }};
                        }}""")
                        await route.fulfill(
                            status=result.get("status", 200),
                            content_type="text/html",
                            body=result.get("body", "<script>self.close();</script>"),
                        )
                    else:
                        await route.continue_()

                await popup.route("**/*auth2*", intercept)
                await popup.wait_for_load_state("domcontentloaded")
                await asyncio.sleep(3)

                auth_btn = await popup.query_selector('#submit_approval')
                if auth_btn:
                    await auth_btn.click()
                    logger.info("Clicked Allow")

                for _ in range(20):
                    await asyncio.sleep(1)
                    if popup.is_closed() or auth2_url:
                        break
                if not popup.is_closed():
                    try: await popup.close()
                    except: pass
            except Exception as e:
                logger.error("OAuth: %s", e)

        if auth2_url:
            logger.info("SC OAuth completed successfully")
            # Trigger completion handlers
            await page.evaluate("""() => {
                if (typeof rX5mPQjW7s === 'function') rX5mPQjW7s('login_to_sc');
                if (typeof u98YzPqL1 === 'function') u98YzPqL1('login_to_sc');
            }""")
            await asyncio.sleep(2)
        else:
            logger.warning("Failed to capture auth2 URL!")

    # Download using native jQuery mechanism
    csrf = await page.evaluate("document.querySelector('meta[name=\"csrf-token\"]')?.getAttribute('content')||''")

    # Advance to DW slide
    await page.evaluate("""() => {
        document.querySelectorAll('.fangate-slider-content').forEach(s => {
            if (!s.className.includes('dw')) {
                s.classList.remove('current-slide', 'upcomming-slide', 'zindex');
                s.classList.add('move-left');
            }
        });
        const dw = document.querySelector('.fangate-slider-content.dw');
        if (dw) { dw.classList.remove('upcomming-slide', 'move-left'); dw.classList.add('current-slide', 'zindex'); }
        // Enable download button
        $('#gateDownloadButton').removeClass('disable hy-btn-lightgray disabled');
    }""")
    await asyncio.sleep(1)

    # Use native jQuery download
    dl = await page.evaluate("""() => {
        return new Promise((resolve) => {
            const origAjax = $.ajax;
            $.ajax = function(opts) {
                if (opts.url && opts.url.includes('download')) {
                    const origSuccess = opts.success;
                    opts.success = function(res) {
                        resolve(JSON.stringify(res));
                        if (origSuccess) origSuccess.call(this, res);
                    };
                    const origError = opts.error;
                    opts.error = function(xhr, status, err) {
                        resolve(JSON.stringify({error: status, response: xhr.responseText?.substring(0, 500)}));
                        if (origError) origError.call(this, xhr, status, err);
                    };
                }
                return origAjax.call(this, opts);
            };
            $('#gateDownloadButton').trigger('click');
            setTimeout(() => resolve('TIMEOUT'), 15000);
        });
    }""")
    logger.info("DOWNLOAD (native click): %s", dl[:500])

    try:
        dj = json.loads(dl)
        if dj.get("download_status"):
            logger.info("🎉 SUCCESS! URL: %s", dj.get("URL", "")[:200])
        else:
            logger.warning("❌ FAILED: social_currency=%s", dj.get("social_currency"))
    except:
        pass

    return dl


async def main():
    pw = await async_playwright().start()
    logger.info("=== Simple gate tests ===")

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

    # Test 1: SC-ONLY gate with OAuth
    await test_download(page, ctx, "https://hypeddit.com/espresso/espresso", "SC-ONLY", do_sc=True)

    # Test 2: Another SC-ONLY gate
    await test_download(page, ctx, "https://hypeddit.com/lukewaveblackzushi/nacho", "SC-ONLY-2", do_sc=True)

    await asyncio.sleep(5)
    await ctx.close()
    await pw.stop()


if __name__ == "__main__":
    asyncio.run(main())
