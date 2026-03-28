"""TEST: Send download request using EXACTLY the same postData as native JS.
The native JS in gate-ul-preview.js constructs postData manually, NOT from hidden inputs.
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
    logger.info("=== TEST: Native download postData format ===")

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

    # Intercept the actual download POST to see what native JS sends
    download_requests = []
    async def on_request(req):
        if "download/ul" in req.url and req.method == "POST":
            post_data = req.post_data or ""
            download_requests.append(post_data)
            logger.info("=== CAPTURED download POST data ===")
            logger.info("  URL: %s", req.url)
            # Parse and log each field
            for pair in post_data.split("&"):
                if "=" in pair:
                    key, val = pair.split("=", 1)
                    from urllib.parse import unquote_plus
                    logger.info("  %s = %s", unquote_plus(key), unquote_plus(val)[:100])

    page.on("request", on_request)

    # Also capture the download response
    async def on_response(resp):
        if "download/ul" in resp.url:
            try:
                body = await resp.text()
                logger.info("=== DOWNLOAD RESPONSE: %s ===", body[:500])
            except:
                pass

    page.on("response", on_response)

    await page.goto(TEST_URL, wait_until="domcontentloaded")
    await asyncio.sleep(3)
    await page.evaluate("document.cookie='teb3456767win=;expires=Thu,01 Jan 1970 00:00:00 UTC;path=/;'")

    gate_id = await page.evaluate("document.querySelector('#fan_gate_id')?.value||''")
    csrf = await page.evaluate("document.querySelector('meta[name=\"csrf-token\"]')?.getAttribute('content')||''")
    steps = await page.evaluate("document.querySelector('#steps_select')?.value||''")
    nw_steps = await page.evaluate("document.querySelector('#nwSteps')?.value||''")
    logger.info("Gate: id=%s steps=%s nwSteps=%s", gate_id, steps, nw_steps)

    # Activate gate
    await page.evaluate("document.querySelector('#gateDownloadButton')?.click()")
    await asyncio.sleep(3)
    csrf = await page.evaluate("document.querySelector('meta[name=\"csrf-token\"]')?.getAttribute('content')||''")

    # SC Comment + OAuth
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

    # Do SC OAuth with relay approach
    if oauth_url:
        try:
            async with page.expect_popup(timeout=15000) as pi:
                await page.evaluate(f"window.open('{oauth_url}', 'sc', 'width=800,height=600')")
            popup = await pi.value

            async def intercept_and_relay(route):
                url = route.request.url
                if "hypeddit.com/auth2.php" in url:
                    https_url = url.replace("http://", "https://") if url.startswith("http://") else url
                    logger.info("INTERCEPTED auth2.php, fetching from main page...")

                    result = await page.evaluate(f"""async () => {{
                        try {{
                            const r = await fetch('{https_url}', {{
                                method: 'GET',
                                credentials: 'include',
                                redirect: 'follow',
                            }});
                            return {{ status: r.status, body: await r.text() }};
                        }} catch(e) {{
                            return {{ error: e.message }};
                        }}
                    }}""")

                    if result.get("error"):
                        await route.fulfill(status=500, body="Error")
                    else:
                        await route.fulfill(
                            status=result["status"],
                            content_type="text/html",
                            body=result["body"],
                        )
                else:
                    await route.continue_()

            await popup.route("**/*auth2*", intercept_and_relay)
            await popup.wait_for_load_state("domcontentloaded")
            await asyncio.sleep(3)

            auth_btn = await popup.query_selector('#submit_approval')
            if auth_btn:
                await auth_btn.click()
                logger.info("Clicked SC Allow")

            for i in range(30):
                await asyncio.sleep(1)
                if popup.is_closed():
                    logger.info("SC popup closed after %ds", i+1)
                    break
            else:
                try: await popup.close()
                except: pass

        except Exception as e:
            logger.error("SC OAuth error: %s", e)

    await asyncio.sleep(2)

    # Trigger completion
    await page.evaluate("""() => {
        if (typeof rX5mPQjW7s === 'function') rX5mPQjW7s('login_to_sc');
        if (typeof u98YzPqL1 === 'function') u98YzPqL1('login_to_sc');
    }""")
    await asyncio.sleep(2)

    # === NOW: Trigger the NATIVE download button click ===
    # This will use gate-ul-preview.js's own code to construct postData
    logger.info("=== Clicking native download button ===")
    # First advance to DW slide
    await page.evaluate("""() => {
        document.querySelectorAll('.fangate-slider-content').forEach(s => {
            if (!s.className.includes('dw')) {
                s.classList.remove('current-slide', 'upcomming-slide', 'zindex');
                s.classList.add('move-left');
            }
        });
        const dw = document.querySelector('.fangate-slider-content.dw');
        if (dw) { dw.classList.remove('upcomming-slide', 'move-left'); dw.classList.add('current-slide', 'zindex'); }
    }""")
    await asyncio.sleep(1)

    # Remove disabled class from download button
    await page.evaluate("""() => {
        const btn = document.querySelector('#gateDownloadButton');
        if (btn) {
            btn.classList.remove('disable', 'hy-btn-lightgray', 'disabled');
        }
    }""")
    await asyncio.sleep(0.5)

    # Click the actual download button using jQuery trigger
    await page.evaluate("jQuery('#gateDownloadButton').trigger('click');")
    await asyncio.sleep(8)

    # Show captured requests
    logger.info("=== Captured %d download requests ===", len(download_requests))

    # Also try constructing postData exactly like the native JS
    logger.info("=== Manual native-format download ===")
    dl = await page.evaluate(f"""async () => {{
        // Construct postData exactly like gate-ul-preview.js
        var downloadlink = jQuery("#current_download_file_listner").val();
        var duration = jQuery("#duration").val() || '313000';
        var commment_timestamp1 = Math.floor(Math.random() * parseInt(duration));
        var sc_comment_text = jQuery("#sc_comment_text")?.val() || 'Great track!';
        var wrndk = jQuery("#wrndk").val();
        var is_skippable = jQuery("#is_skippable").val();
        var steps = jQuery("#nwSteps").val();
        var email = jQuery("#email_address")?.val() || '';
        var is_mobile = jQuery("#is_mobile")?.val() || '';

        var additional_sc_array = [];
        jQuery('input[name="additional_sc_user_id[]"]').each(function() {{
            additional_sc_array.push(jQuery(this).val());
        }});
        var additional_sp_array = [];
        jQuery('input[name="additional_sp_user_id[]"]').each(function() {{
            additional_sp_array.push(jQuery(this).val());
        }});
        var skip_gate_steps = [];
        jQuery('input[name="skip_gate_steps[]"]').each(function() {{
            skip_gate_steps.push(jQuery(this).val());
        }});

        var postData = {{
            file: encodeURIComponent(downloadlink),
            download_visit: 'true',
            profile_downloads: 'true',
            time: commment_timestamp1,
            sc_comment_text: sc_comment_text,
            yt_comment_text: '',
            page: 'nonsingle',
            additional_sc_user_id: additional_sc_array,
            additional_yt_user_id: [],
            additional_sp_user_id: additional_sp_array,
            additional_dz_user_id: [],
            additional_dz_type_array: [],
            additional_mc_user_id: [],
            additional_tw_user_id: [],
            additional_ig_user_id: [],
            is_skippable: is_skippable,
            steps: steps,
            email: email,
            download_action: 'DOWNLOAD',
            skip_gate_steps: skip_gate_steps,
            wrndk: wrndk,
            is_mobile: is_mobile,
            additional_ap_user_id: [],
            additional_ap_type_array: [],
            additional_th_user_id: [],
            additional_th_type_array: [],
            external_id: '',
            hypesource: '',
            adcode: '',
            lifetime_fan_spotify: jQuery("#lifetime_fan_sp")?.val() || '',
            lifetime_fan_deezer: jQuery("#lifetime_fan_dz")?.val() || '',
            lifetime_fan_apple: jQuery("#lifetime_fan_ap")?.val() || '',
        }};

        // Log what we're sending
        var debug = {{
            file: postData.file,
            steps: postData.steps,
            is_skippable: postData.is_skippable,
            skip_gate_steps: postData.skip_gate_steps,
            wrndk: postData.wrndk,
            sc_user_ids: postData.additional_sc_user_id,
            sp_user_ids: postData.additional_sp_user_id,
        }};

        try {{
            const r = await new Promise((resolve, reject) => {{
                jQuery.ajax({{
                    type: "POST",
                    url: "/gate/download/ul",
                    dataType: "json",
                    data: postData,
                    success: function(res) {{ resolve(JSON.stringify(res)); }},
                    error: function(xhr, status, err) {{ resolve(JSON.stringify({{error: status, detail: err, response: xhr.responseText?.substring(0, 500)}})); }}
                }});
            }});
            return JSON.stringify({{ debug: debug, response: JSON.parse(r) }});
        }} catch(e) {{
            return JSON.stringify({{ debug: debug, error: e.message }});
        }}
    }}""")
    logger.info("=== NATIVE FORMAT DOWNLOAD: %s ===", dl[:1000])

    await asyncio.sleep(10)
    await ctx.close()
    await pw.stop()


if __name__ == "__main__":
    asyncio.run(main())
