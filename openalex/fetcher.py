# openalex/openalex_fetcher.py

import asyncio
import aiohttp
from aiohttp import ClientSession
from typing import AsyncGenerator

from openalex.utils import (
    make_headers,
    infer_language,
    extract_authors,
    reconstruct_abstract,
)

from utils.progress import make_bar
from utils.files import log_event


BASE_URL = "https://api.openalex.org/works"

PER_PAGE = 200
MAX_RESULTS = 10000

REQUEST_TIMEOUT = 20
MAX_CONNECTIONS = 20

RATE_LIMIT_DELAY = 0.5
MAX_RETRIES = 5
MAX_CONCURRENCY = 5


class OpenAlexFetcher:
    def __init__(self):
        connector = aiohttp.TCPConnector(
            limit=MAX_CONNECTIONS,
            ttl_dns_cache=300,
        )

        timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)

        self.session = ClientSession(
            connector=connector,
            timeout=timeout,
            headers=make_headers(),
        )

        self.semaphore = asyncio.Semaphore(MAX_CONCURRENCY)

    async def close(self):
        await self.session.close()

    async def fetch_page(
        self,
        query: str,
        cursor: str = "*",
    ) -> dict | None:

        params = {
            "search": query,
            "per_page": PER_PAGE,
            "cursor": cursor,
            "filter": "has_abstract:true",
            "select": ",".join([
                "id",
                "doi",
                "title",
                "language",
                "abstract_inverted_index",
                "authorships",
                "primary_location",
                "publication_date",
            ]),
        }

        async with self.semaphore:

            for attempt in range(MAX_RETRIES):

                try:
                    async with self.session.get(
                        BASE_URL,
                        params=params,
                    ) as resp:

                        if resp.status == 429:
                            retry_after = int(
                                resp.headers.get("Retry-After", "2")
                            )

                            await asyncio.sleep(retry_after)
                            continue

                        resp.raise_for_status()

                        return await resp.json()

                except asyncio.TimeoutError:
                    pass

                except aiohttp.ClientError:
                    pass

                except Exception:
                    pass

                backoff = (2 ** attempt) + 0.1
                await asyncio.sleep(backoff)

        await log_event({
            "event": "openalex_fetch_error",
            "query": query,
            "cursor": cursor,
        })

        return None

    async def iter_query(
        self,
        query: str,
        checkpoint: dict,
    ) -> AsyncGenerator[dict, None]:

        cursor = "*"
        fetched = 0
        unknown_lang = 0

        first_page = await self.fetch_page(query, cursor)

        if not first_page:
            return

        total_available = min(
            first_page.get("meta", {}).get("count", 0),
            MAX_RESULTS,
        )

        with make_bar(
            "openalex",
            f"[OpenAlex] {query}",
            total=total_available,
        ) as pbar:

            data = first_page

            while True:

                works = data.get("results", [])

                if not works:
                    break

                for work in works:

                    pbar.update(1)

                    openalex_id = (
                        work.get("id", "")
                        .replace("https://openalex.org/", "")
                    )

                    if (
                        not openalex_id
                        or openalex_id in checkpoint["done_ids"]
                    ):
                        continue

                    abstract = reconstruct_abstract(
                        work.get("abstract_inverted_index")
                    )

                    if not abstract:
                        continue

                    lang = infer_language(work, abstract)

                    if lang == "unknown":
                        unknown_lang += 1

                    yield {
                        "source": "openalex",
                        "query": query,
                        "authors": extract_authors(work),
                        "published": (
                            work.get("publication_date") or ""
                        ),
                        "id": openalex_id,
                        "doi": work.get("doi") or "",
                        "title": (
                            work.get("title") or ""
                        ).strip(),
                        "abstracts": {
                            lang: abstract
                        },
                    }

                    fetched += 1

                    if fetched >= MAX_RESULTS:
                        break

                if fetched >= MAX_RESULTS:
                    break

                next_cursor = data.get("meta", {}).get("next_cursor")

                if not next_cursor:
                    break

                await asyncio.sleep(RATE_LIMIT_DELAY)

                data = await self.fetch_page(
                    query,
                    next_cursor,
                )

                if not data:
                    break

        if unknown_lang:
            await log_event({
                "event": "openalex_unknown_languages",
                "query": query,
                "art_num": unknown_lang,
            })


async def fetch_openalex(
    query: str,
    checkpoint: dict,
) -> list[dict]:

    fetcher = OpenAlexFetcher()

    results = []

    try:
        async for item in fetcher.iter_query(
            query,
            checkpoint,
        ):
            results.append(item)

    finally:
        await fetcher.close()

    return results