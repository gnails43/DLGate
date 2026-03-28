"""Check SC login status and re-login if needed.
Opens SC and waits for user to login if necessary.
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
    logger.info("=== SC Login Check ===")

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

    # Check SC login status
    logger.info("Navigating to SoundCloud...")
    await page.goto("https://soundcloud.com/discover", wait_until="domcontentloaded")
    await asyncio.sleep(5)

    # Check if logged in
    is_logged_in = await page.evaluate("""() => {
        // Check for user avatar or profile elements
        const avatar = document.querySelector('.header__userNavButton, .header__userNavAvatar, [aria-label="Your profile"]');
        const signIn = document.querySelector('button[aria-label="Sign in"], .header__login');
        return {
            has_avatar: !!avatar,
            has_sign_in: !!signIn,
            page_text: document.body?.innerText?.substring(0, 300) || '',
        };
    }""")
    logger.info("SC login status: %s", is_logged_in)

    if is_logged_in.get("has_sign_in") and not is_logged_in.get("has_avatar"):
        logger.warning("NOT logged into SoundCloud!")
        logger.info("Attempting Facebook login to SoundCloud...")

        # Navigate to SC OAuth authorize endpoint to trigger login
        await page.goto("https://secure.soundcloud.com/authorize?client_id=f17476445ba4b72bc5760aa679820d27&scope=&display=popup&response_type=code&redirect_uri=http%3A%2F%2Fhypeddit.com%2Fauth2.php&state=test", wait_until="domcontentloaded")
        await asyncio.sleep(3)

        # Look for Facebook login button
        fb_btn = await page.query_selector('button[aria-label="Continue with Facebook"]')
        if not fb_btn:
            # Try alternative selectors
            fb_btn = await page.evaluate("""() => {
                const btns = document.querySelectorAll('button');
                for (const b of btns) {
                    if (b.textContent.includes('Facebook')) return true;
                }
                return false;
            }""")

        page_text = await page.evaluate("document.body?.innerText || ''")
        logger.info("SC auth page: %s", page_text[:300])

        # Try clicking Facebook login
        try:
            await page.click('button:has-text("Facebook")', timeout=5000)
            logger.info("Clicked Facebook login button")
            await asyncio.sleep(5)

            # Check if Facebook login page appeared
            fb_text = await page.evaluate("document.body?.innerText || ''")
            logger.info("After FB click: %s", page.url[:80])
            logger.info("Page text: %s", fb_text[:200])

            # Fill in FB credentials
            email_field = await page.query_selector('#email, input[name="email"]')
            if email_field:
                await email_field.fill("gnahell@yahoo.co.jp")
                pass_field = await page.query_selector('#pass, input[name="pass"]')
                if pass_field:
                    await pass_field.fill("gna315086")
                    # Click login button
                    await page.click('button[name="login"], input[name="login"], #loginbutton', timeout=5000)
                    logger.info("Submitted FB login")
                    await asyncio.sleep(10)

                    # Check result
                    result_text = await page.evaluate("document.body?.innerText || ''")
                    logger.info("After FB login: %s", page.url[:80])
                    logger.info("Result: %s", result_text[:200])
        except Exception as e:
            logger.error("FB login error: %s", e)

        # Wait a bit and check SC login again
        await page.goto("https://soundcloud.com/discover", wait_until="domcontentloaded")
        await asyncio.sleep(5)
        is_logged_in2 = await page.evaluate("""() => {
            const avatar = document.querySelector('.header__userNavButton, .header__userNavAvatar');
            return { has_avatar: !!avatar };
        }""")
        logger.info("SC login after FB: %s", is_logged_in2)
    else:
        logger.info("Already logged into SoundCloud!")

    # Keep browser open for 30s to allow manual intervention if needed
    logger.info("Keeping browser open for 30s...")
    await asyncio.sleep(30)

    await ctx.close()
    await pw.stop()


if __name__ == "__main__":
    asyncio.run(main())
