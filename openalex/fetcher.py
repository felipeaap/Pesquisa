# openalex/openalex_fetcher.py
import asyncio
import aiohttp
from openalex.utils import make_headers, infer_language, extract_authors, reconstruct_abstract
from utils.progress import make_bar
from utils.files import log_event

BASE_URL    = "https://api.openalex.org/works"
PER_PAGE    = 200
MAX_RESULTS = 600
DELAY       = 1.0

async def fetch_page_async(session: aiohttp.ClientSession, query: str, cursor: str = "*") -> dict | None:
    params = {
        "search":   query,
        "per_page": PER_PAGE,
        "cursor":   cursor,
        "filter":   "has_abstract:true",
        "select":   "id,doi,title,language,abstract_inverted_index,authorships,primary_location,publication_date",
    }
    try:
        async with session.get(BASE_URL, params=params, headers=make_headers(), timeout=aiohttp.ClientTimeout(total=15)) as resp:
            resp.raise_for_status()
            return await resp.json()
    except Exception as e:
        await log_event({"event": "openalex_fetch_error", "query": query})
        return None

async def fetch_openalex(query: str, checkpoint: dict) -> list[dict]:
    results      = []
    cursor       = "*"
    unknown_lang = 0
    page         = 0

    async with aiohttp.ClientSession() as session:
        first_page = await fetch_page_async(session, query, cursor)
        if not first_page:
            return []

        total_available = min(first_page.get("meta", {}).get("count", 0), MAX_RESULTS)

        with make_bar("openalex", f"[OpenAlex] {query}", total=total_available, unit="art") as pbar:
            data = first_page

            while True:
                works = data.get("results", [])
                if not works:
                    break

                for work in works:
                    openalex_id = (work.get("id") or "").replace("https://openalex.org/", "")
                    pbar.update(1)

                    if not openalex_id or openalex_id in checkpoint["done_ids"]:
                        continue

                    abstract = reconstruct_abstract(work.get("abstract_inverted_index"))
                    if not abstract:
                        continue

                    lang = infer_language(work, abstract)
                    if lang == "unknown":
                        unknown_lang += 1

                    results.append({
                        "source":    "openalex",
                        "query":     query,
                        "id":        openalex_id,
                        "doi":       work.get("doi") or "",
                        "title":     (work.get("title") or "").strip(),
                        "authors":   extract_authors(work),
                        "published": work.get("publication_date") or "",
                        "abstracts": {lang: abstract},
                    })

                page += 1
                if page * PER_PAGE >= MAX_RESULTS:
                    break

                next_cursor = data.get("meta", {}).get("next_cursor")
                if not next_cursor:
                    break

                await asyncio.sleep(DELAY)   # non-blocking sleep
                data = await fetch_page_async(session, query, next_cursor)
                if not data:
                    break
    if unknown_lang:
        await log_event({"event": "openalex_unknown_languages", "query": query, "art_num": unknown_lang,})
    return results