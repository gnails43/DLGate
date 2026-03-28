"""Diagnostic: Why doesn't email button click trigger jQuery handler?
Then test calling runEmailVerification() and jumpGate() directly.
"""
import asyncio
import json
import random
import logging
from pathlib import Path

from playwright.async_api import async_playwright

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# Use desktop UA (not mobile) to match production setup
DESKTOP_UA = None  # Let Chrome use its default UA

TEST_URL = "https://hypeddit.com/spinrealrecords/bijwtfdubtopshelf01"
EMAIL = "gna.k.fujisaki43@gmail.com"
NAME = "Kentaro"
PROFILE_DIR = str(Path("C:/GitHub/DLGate/.chrome-profile-test-diag").resolve())

api_log = []


def generate_email_alias(base_email: str) -> str:
    local, domain = base_email.split("@", 1)
    local = local.split("+")[0].replace(".", "")
    if len(local) < 2:
        return base_email
    positions = sorted(random.sample(range(1, len(local)), min(random.randint(1, 3), len(local) - 1)))
    parts = []
    prev = 0
    for pos in positions:
        parts.append(local[prev:pos])
        prev = pos
    parts.append(local[prev:])
    return ".".join(parts) + f"@{domain}"


async def main():
    pw = await async_playwright().start()
    logger.info("=== DIAGNOSTIC: Email handler analysis ===")

    Path(PROFILE_DIR).mkdir(parents=True, exist_ok=True)

    launch_kwargs = {
        "user_data_dir": PROFILE_DIR,
        "headless": False,
        "channel": "chrome",
        "viewport": {"width": 1280, "height": 900},
        "accept_downloads": True,
        "args": ["--disable-blink-features=AutomationControlled"],
        "ignore_default_args": ["--enable-automation"],
    }

    ctx = await pw.chromium.launch_persistent_context(**launch_kwargs)
    page = ctx.pages[0] if ctx.pages else await ctx.new_page()

    # Capture API calls
    async def on_response(resp):
        url = resp.url
        if "hypeddit.com" in url and any(kw in url for kw in ["setGate", "download", "verify", "getGate", "windowopener", "setSC", "Pathway", "jumpGate"]):
            try:
                body = await resp.text()
            except:
                body = "(unreadable)"
            api_log.append({"status": resp.status, "url": url, "body": body[:500]})
            logger.info("<<< API: %d %s body=%s", resp.status, url, body[:300])

    page.on("response", on_response)

    # Navigate
    logger.info("Navigating to %s", TEST_URL)
    await page.goto(TEST_URL, wait_until="domcontentloaded")
    await asyncio.sleep(3)

    # Clear rate limit cookie
    await page.evaluate("""() => {
        document.cookie = 'teb3456767win=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;';
    }""")

    # Extract metadata
    meta = await page.evaluate("""() => {
        const r = {};
        document.querySelectorAll('input[type="hidden"]').forEach(i => {
            if (i.id) r[i.id] = i.value;
        });
        r.csrf = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';
        return r;
    }""")
    gate_id = meta.get("fan_gate_id", "")
    steps = meta.get("steps_select", "")
    csrf = meta.get("csrf", "")
    logger.info("Gate: id=%s steps=%s skippable=%s", gate_id, steps, meta.get("is_skippable"))

    # Click Download to activate gate
    logger.info("Clicking Download button...")
    await page.evaluate("document.querySelector('#gateDownloadButton')?.click()")
    await asyncio.sleep(3)

    # Re-get CSRF (may change after activation)
    csrf = await page.evaluate("""() => {
        return document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';
    }""")

    # === DIAGNOSE EMAIL BUTTON ===
    logger.info("=== DIAGNOSING EMAIL BUTTON STATE ===")

    btn_diag = await page.evaluate("""() => {
        const btn = document.querySelector('#email_to_downloads_next');
        if (!btn) return {exists: false};

        const style = window.getComputedStyle(btn);
        return {
            exists: true,
            tagName: btn.tagName,
            id: btn.id,
            className: btn.className,
            text: btn.textContent.trim().substring(0, 100),
            display: style.display,
            visibility: style.visibility,
            opacity: style.opacity,
            disabled: btn.disabled,
            href: btn.href || '',
            onclick: btn.getAttribute('onclick') || '',
            data_onclick: btn.getAttribute('data-onclick') || '',
            // Check jQuery events bound
            has_jquery: typeof $ !== 'undefined',
            jquery_events: null,
        };
    }""")
    logger.info("Button state: %s", json.dumps(btn_diag, indent=2))

    # Check if jQuery events are bound
    jquery_diag = await page.evaluate("""() => {
        if (typeof $ === 'undefined' && typeof jQuery === 'undefined') return 'no jQuery';
        const jq = $ || jQuery;
        const btn = jq('#email_to_downloads_next');
        if (!btn.length) return 'element not found via jQuery';

        // Check jQuery event handlers
        const events = jq._data(btn[0], 'events') || {};
        const result = {};
        for (const [type, handlers] of Object.entries(events)) {
            result[type] = handlers.map(h => ({
                namespace: h.namespace,
                handler_preview: h.handler.toString().substring(0, 200),
            }));
        }
        return {
            element_found: true,
            events_bound: result,
            total_events: Object.keys(events).length,
        };
    }""")
    logger.info("jQuery events: %s", json.dumps(jquery_diag, indent=2))

    # Check runEmailVerification function
    fn_diag = await page.evaluate("""() => {
        return {
            runEmailVerification_exists: typeof runEmailVerification === 'function',
            runEmailVerification_source: typeof runEmailVerification === 'function'
                ? runEmailVerification.toString().substring(0, 500)
                : null,
            gateEmailVerificationNextSlide_exists: typeof gateEmailVerificationNextSlide === 'function',
            jumpGate_exists: typeof jumpGate === 'function',
        };
    }""")
    logger.info("Functions: %s", json.dumps(fn_diag, indent=2))

    # === TEST 1: Fill email and try jQuery trigger ===
    email = generate_email_alias(EMAIL)
    logger.info("=== TEST 1: jQuery trigger click ===")
    logger.info("Using email: %s", email)

    await page.evaluate(f"""() => {{
        const name = document.querySelector('#email_name');
        if (name) {{ name.value = {repr(NAME)}; name.dispatchEvent(new Event('input', {{bubbles:true}})); }}
        const addr = document.querySelector('#email_address');
        if (addr) {{ addr.value = {repr(email)}; addr.dispatchEvent(new Event('input', {{bubbles:true}})); }}
    }}""")
    await asyncio.sleep(1)

    # Try jQuery trigger
    trigger_result = await page.evaluate("""() => {
        if (typeof $ !== 'undefined' || typeof jQuery !== 'undefined') {
            const jq = $ || jQuery;
            jq('#email_to_downloads_next').trigger('click');
            return 'jQuery trigger click done';
        }
        return 'no jQuery available';
    }""")
    logger.info("jQuery trigger result: %s", trigger_result)
    await asyncio.sleep(5)

    # Check if API was called
    verify_calls = [e for e in api_log if "verify" in e.get("url", "").lower()]
    logger.info("verifyEmailAddress calls after jQuery trigger: %d", len(verify_calls))
    for c in verify_calls:
        logger.info("  %s", c)

    # === TEST 2: Call runEmailVerification() directly ===
    if not verify_calls:
        logger.info("=== TEST 2: Direct runEmailVerification() call ===")
        email2 = generate_email_alias(EMAIL)
        await page.evaluate(f"""() => {{
            const addr = document.querySelector('#email_address');
            if (addr) {{ addr.value = {repr(email2)}; addr.dispatchEvent(new Event('input', {{bubbles:true}})); }}
        }}""")

        direct_result = await page.evaluate("""() => {
            if (typeof runEmailVerification === 'function') {
                try {
                    runEmailVerification();
                    return 'called successfully';
                } catch(e) {
                    return 'error: ' + e.message;
                }
            }
            return 'function not found';
        }""")
        logger.info("Direct runEmailVerification result: %s", direct_result)
        await asyncio.sleep(5)

        verify_calls2 = [e for e in api_log if "verify" in e.get("url", "").lower()]
        logger.info("verifyEmailAddress calls after direct call: %d", len(verify_calls2))
        for c in verify_calls2:
            logger.info("  %s", c)

    # === TEST 3: Manual API call ===
    logger.info("=== TEST 3: Manual /verifyEmailAddress API call ===")
    email3 = generate_email_alias(EMAIL)
    manual_result = await page.evaluate(f"""async () => {{
        try {{
            const fd = new URLSearchParams();
            fd.append('email', {repr(email3)});
            fd.append('name', {repr(NAME)});
            fd.append('fan_gate_id', '{gate_id}');
            const r = await fetch('/verifyEmailAddress', {{
                method: 'POST',
                body: fd.toString(),
                credentials: 'include',
                headers: {{
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'X-Requested-With': 'XMLHttpRequest',
                    'X-CSRF-TOKEN': '{csrf}',
                }},
            }});
            return {{ status: r.status, body: (await r.text()).substring(0, 500) }};
        }} catch(e) {{
            return {{ error: e.message }};
        }}
    }}""")
    logger.info("Manual /verifyEmailAddress: %s", json.dumps(manual_result))

    # === TEST 4: jumpGate() call ===
    logger.info("=== TEST 4: Manual jumpGate() for email step ===")
    jump_result = await page.evaluate("""() => {
        if (typeof jumpGate !== 'function') return 'jumpGate not found';
        // Find the email slide
        const emailSlide = document.querySelector('.fangate-slider-content.email');
        if (!emailSlide) return 'email slide not found';

        // Check data-group attribute
        const group = emailSlide.getAttribute('data-group');
        const result = {
            slide_found: true,
            data_group: group,
            slide_classes: emailSlide.className,
        };

        try {
            jumpGate(emailSlide, 'submit');
            result.jumpGate_called = true;
        } catch(e) {
            result.jumpGate_error = e.message;
        }
        return result;
    }""")
    logger.info("jumpGate for email: %s", json.dumps(jump_result))
    await asyncio.sleep(3)

    # Check for /setGatePathwayOr calls
    sgpo = [e for e in api_log if "setGatePathwayOr" in e.get("url", "")]
    logger.info("setGatePathwayOr calls after jumpGate: %d", len(sgpo))
    for c in sgpo:
        logger.info("  %s", c)

    # === TEST 5: Check getGatePathway now ===
    pathway = await page.evaluate(f"""async () => {{
        const fd = new URLSearchParams();
        fd.append('fan_gate_id', '{gate_id}');
        const r = await fetch('/getGatePathway', {{
            method: 'POST', body: fd.toString(), credentials: 'include',
            headers: {{
                'Content-Type': 'application/x-www-form-urlencoded',
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRF-TOKEN': '{csrf}',
            }},
        }});
        return await r.json();
    }}""")
    logger.info("getGatePathway after all tests: %s", json.dumps(pathway))

    # === TEST 6: Try download now ===
    logger.info("=== TEST 6: Download attempt ===")
    dl = await page.evaluate(f"""async () => {{
        const fd = new URLSearchParams();
        // Add all hidden inputs
        document.querySelectorAll('input[type="hidden"]').forEach(i => {{
            if (i.name) fd.append(i.name, i.value);
        }});
        // Add skip steps
        for (const s of ['email', 'sc', 'ig', 'tk', 'sp', 'yt', 'fb', 'tw', 'am']) {{
            if (!fd.getAll('skip_gate_steps[]').includes(s)) {{
                fd.append('skip_gate_steps[]', s);
            }}
        }}
        const r = await fetch('/gate/download/ul', {{
            method: 'POST', body: fd.toString(), credentials: 'include',
            headers: {{
                'Content-Type': 'application/x-www-form-urlencoded',
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRF-TOKEN': '{csrf}',
            }},
        }});
        return {{ status: r.status, body: (await r.text()).substring(0, 500) }};
    }}""")
    logger.info("=== DOWNLOAD: %s ===", json.dumps(dl))

    # Full API log
    logger.info("=== FULL API LOG (%d) ===", len(api_log))
    for i, e in enumerate(api_log):
        logger.info("  [%d] %d %s body=%s", i, e["status"], e["url"], e.get("body", "")[:200])

    logger.info("Keeping browser open for 15s...")
    await asyncio.sleep(15)
    await ctx.close()
    await pw.stop()


if __name__ == "__main__":
    asyncio.run(main())
