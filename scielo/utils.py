import re
import asyncio
import time
import urllib.parse
from utils import log_event

LANG_MARKER = re.compile(r'Abstract in (\w+)', re.IGNORECASE)

def split_abstract_by_language(raw: str) -> dict[str, str]:
    """Split a concatenated multi-language abstract blob into {lang: text}."""
    parts = LANG_MARKER.split(raw)          # ['', 'portuguese', 'RESUMO...', 'english', 'ABSTRACT...']
    out = {}
    it = iter(parts[1:])                    # skip leading empty string
    for lang, body in zip(it, it):
        out[lang.lower()] = body.strip()
    return out if out else {"default": raw.strip()}

def extract_pid(url: str) -> str:
    pid = urllib.parse.parse_qs(urllib.parse.urlparse(url).query).get("pid", [None])[0]
    return pid or url

async def fetch_with_retry(session, url, params=None, retries=5, base_delay=1):
    for attempt in range(retries):
        start = time.time()
        try:
            async with session.get(url, params=params, timeout=10) as resp:
                text = await resp.text(encoding=resp.charset or "latin-1")

                await log_event({
                    "event": "http_request",
                    "status": "success",
                    "url": url,
                    "retry": attempt,
                    "latency": round(time.time() - start, 3)
                })

                return text

        except Exception as e:
            await log_event({
                "event": "http_request",
                "status": "fail",
                "url": url,
                "retry": attempt,
                "error": str(e)
            })

            await asyncio.sleep(base_delay * (2 ** attempt))

    return None