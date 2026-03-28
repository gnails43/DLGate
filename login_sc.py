"""Open browser to SC login page. User needs to complete 2FA manually.
After login, the script saves the session and exits.
"""
import asyncio
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
        viewport={"width": 1280, "height": 900},
        args=["--disable-blink-features=AutomationControlled"],
        ignore_default_args=["--enable-automation"],
    )
    page = ctx.pages[0] if ctx.pages else await ctx.new_page()

    # Navigate to SC OAuth page (same as what Hypeddit would open)
    await page.goto("https://secure.soundcloud.com/authorize?client_id=f17476445ba4b72bc5760aa679820d27&scope=&display=popup&response_type=code&redirect_uri=http%3A%2F%2Fhypeddit.com%2Fauth2.php&state=test", wait_until="domcontentloaded")

    logger.info("=" * 60)
    logger.info("SC Login page opened.")
    logger.info("Please login via Facebook and complete 2FA.")
    logger.info("After you see 'Allow' button or get redirected,")
    logger.info("the script will detect it and save the session.")
    logger.info("=" * 60)

    # Wait for login completion - check every 2 seconds
    for i in range(120):  # 4 minutes max
        await asyncio.sleep(2)
        try:
            url = page.url
            # Check if we got past the login
            allow_btn = await page.query_selector('#submit_approval')
            if allow_btn:
                logger.info("SUCCESS! 'Allow' button found. SC is logged in.")
                break

            # Check if redirected to auth2.php (auto-approved)
            if "auth2.php" in url:
                logger.info("SUCCESS! Redirected to auth2.php. SC is logged in and auto-approved.")
                break

            # Check if on SC main page (logged in)
            if "soundcloud.com" in url and "authorize" not in url and "secure" not in url:
                logger.info("On SC main page. Checking login status...")
                break

            if i % 10 == 9:
                logger.info("Waiting... (%ds) URL: %s", (i+1)*2, url[:60])
        except:
            pass
    else:
        logger.warning("Timeout waiting for login. Saving session anyway.")

    # Verify by going to SC
    await page.goto("https://soundcloud.com/discover", wait_until="domcontentloaded")
    await asyncio.sleep(3)
    is_logged_in = await page.evaluate("""() => {
        const avatar = document.querySelector('.header__userNavButton, .header__userNavAvatar, [aria-label="Your profile"]');
        return !!avatar;
    }""")
    logger.info("SC logged in: %s", is_logged_in)

    logger.info("Session saved. Closing browser.")
    await ctx.close()
    await pw.stop()


if __name__ == "__main__":
    asyncio.run(main())
