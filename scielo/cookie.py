import asyncio
import os
from playwright.async_api import async_playwright
from dotenv import set_key
from tqdm import tqdm

DOTENV_PATH = ".env"

async def refresh_scielo_cookie(verify_query: str = "renal") -> str:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36",
            locale="en-US",
            timezone_id="America/Sao_Paulo",
        )
        page = await context.new_page()

        # step 1: land on homepage, let Bunny CDN issue the shield cookie
        await page.goto("https://search.scielo.org/", wait_until="networkidle")

        # step 2: wait until the shield cookie actually appears
        for _ in range(20):
            cookies = await context.cookies()
            if any("bunny_shield" in c["name"] for c in cookies):
                break
            await asyncio.sleep(0.5)
        else:
            tqdm.write("[Cookie] Warning: bunny_shield cookie never appeared")

        # step 3: do one real search request inside Playwright so the cookie
        # gets validated against a real browser fingerprint before we extract it
        await page.goto(
            f"https://search.scielo.org/?q={verify_query}&lang=en&count=20&from=0&format=abstract",
            wait_until="networkidle"
        )

        # step 4: collect all cookies after the validated request
        cookies = await context.cookies()
        cookie_str = "; ".join(
            f"{c['name']}={c['value']}"
            for c in cookies
            if c["domain"] in ("search.scielo.org", ".scielo.org")
        )

        await browser.close()

        set_key(DOTENV_PATH, "SCIELO_COOKIE", cookie_str)
        os.environ["SCIELO_COOKIE"] = cookie_str  # update live env immediately
        tqdm.write(f"[Cookie] Refreshed: {cookie_str[:80]}...")
        return cookie_str