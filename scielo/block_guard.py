import random
import asyncio
import time
import os
from utils.files import log_event

def random_headers() -> dict:
    return {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Accept-Language": "en-US,en;q=0.8",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "Priority": "u=0, i",
        "Sec-Ch-Ua": '"Chromium";v="148", "Brave";v="148", "Not/A)Brand";v="99"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Windows"',
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Sec-Gpc": "1",
        "Upgrade-Insecure-Requests": "1",
        "Cookie": os.environ.get("SCIELO_COOKIE", "")
    }

BLOCK_SIGNALS = [
    "403 Forbidden",
    "<title>403",
    "Access Denied",
    "captcha",
    "unusual traffic",
    "automated",
]

BLOCKED = object()

def is_blocked(html: str) -> bool:
    lower = html[:2000].lower()  # only check the head, not the whole page
    return any(signal.lower() in lower for signal in BLOCK_SIGNALS)

async def fetch_with_retry(session, url, params=None, retries=5, base_delay=1.0):
    for attempt in range(retries):
        start = time.time()
        try:
            async with session.get(url, params=params, headers=random_headers(), timeout=15) as resp:

                if resp.status == 429 or resp.status == 503:
                    wait = base_delay * (3 ** attempt) + random.uniform(0, 2)
                    await log_event({"event": "http_request", "status": "rate_limited",
                                     "url": url, "retry": attempt, "wait": wait})
                    await asyncio.sleep(wait)
                    continue

                if resp.status == 403:
                    await log_event({"event": "http_request", "status": "blocked", "url": url, "retry": attempt})
                    return BLOCKED

                text = await resp.text(encoding=resp.charset or "latin-1")
                await log_event({"event": "http_request", "status": "success",
                                 "url": url, "retry": attempt,
                                 "latency": round(time.time() - start, 3)})
                return text

        except asyncio.TimeoutError:
            wait = base_delay * (2 ** attempt) + random.uniform(0, 1)
            await log_event({"event": "http_request", "status": "timeout",
                             "url": url, "retry": attempt, "wait": wait})
            await asyncio.sleep(wait)

        except Exception as e:
            wait = base_delay * (2 ** attempt) + random.uniform(0, 1)
            await log_event({"event": "http_request", "status": "fail",
                             "url": url, "retry": attempt, "error": str(e), "wait": wait})
            await asyncio.sleep(wait)

    return None