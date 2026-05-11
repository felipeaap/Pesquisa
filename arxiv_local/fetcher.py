# arxiv/arxiv_fetcher.py

import asyncio
import arxiv

from utils.progress import make_bar
from utils.files import log_event


MAX_ARXIV = 500
BATCH_SIZE = 100
DELAY = 5.0
MAX_RETRIES = 5
QUEUE_SIZE = 100


class ArxivFetcher:

    def __init__(self):
        self.client = arxiv.Client(
            page_size=BATCH_SIZE,
            delay_seconds=DELAY,
            num_retries=MAX_RETRIES,
        )
        self.semaphore = asyncio.Semaphore(1)

    async def iter_query(self, query: str, checkpoint: dict):

        async with self.semaphore:

            search = arxiv.Search(
                query=query,
                max_results=MAX_ARXIV,
                sort_by=arxiv.SortCriterion.Relevance,
            )

            queue = asyncio.Queue(maxsize=QUEUE_SIZE)
            SENTINEL = object()
            loop = asyncio.get_running_loop()

            def producer():
                try:
                    for result in self.client.results(search):
                        asyncio.run_coroutine_threadsafe(queue.put(result), loop).result()

                except Exception:
                    asyncio.run_coroutine_threadsafe(
                        log_event({"event": "arxiv_fetch_error", "query": query}),
                        loop,
                    ).result()

                finally:
                    asyncio.run_coroutine_threadsafe(queue.put(SENTINEL), loop).result()

            asyncio.create_task(asyncio.to_thread(producer))

            with make_bar("arxiv", f"[arXiv] {query}") as pbar:

                while True:

                    result = await queue.get()

                    if result is SENTINEL:
                        break

                    try:
                        arxiv_id = result.entry_id.split("/")[-1]
                        pbar.update(1)

                        if arxiv_id in checkpoint["done_ids"]:
                            continue

                        abstract = result.summary.strip()

                        if not abstract:
                            continue

                        checkpoint["done_ids"].append(arxiv_id)

                        yield {
                            "source": "arxiv",
                            "query": query,
                            "authors": [a.name for a in result.authors],
                            "published": (
                                result.published.strftime("%Y-%m-%d")
                                if result.published else ""
                            ),
                            "id": arxiv_id,
                            "doi": result.doi or "",
                            "title": result.title.strip(),
                            "abstracts": {"english": abstract},
                        }

                    except Exception:
                        await log_event({
                            "event": "arxiv_parse_error",
                            "query": query,
                        })


async def fetch_arxiv(query: str, checkpoint: dict):

    fetcher = ArxivFetcher()
    results = []

    async for item in fetcher.iter_query(query, checkpoint):
        results.append(item)

    return results