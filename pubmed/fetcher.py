# pubmed/pubmed_fetcher.py

import os
import asyncio

from dotenv import load_dotenv
from Bio import Entrez

from pubmed.utils import (
    extract_pubmed_abstracts,
    extract_doi,
    extract_authors,
    extract_date,
)

from utils.progress import make_bar
from utils.files import log_event


load_dotenv()

Entrez.email = os.getenv("ENTREZ_EMAIL")

api_key = os.getenv("ENTREZ_API_KEY")

if api_key:
    Entrez.api_key = api_key


MAX_PUBMED = 400
BATCH_SIZE = 200
REQUEST_DELAY = 0.11 if api_key else 0.34
MAX_RETRIES = 5


class PubMedFetcher:

    def __init__(self):
        self.semaphore = asyncio.Semaphore(10 if api_key else 3)

    async def esearch(self, query: str) -> list[str]:

        async with self.semaphore:

            for attempt in range(MAX_RETRIES):

                try:

                    def _search():
                        handle = Entrez.esearch(
                            db="pubmed",
                            term=query,
                            retmax=MAX_PUBMED,
                        )

                        data = Entrez.read(handle)
                        handle.close()

                        return data["IdList"]

                    return await asyncio.to_thread(_search)

                except Exception:
                    await asyncio.sleep((2 ** attempt) + 0.1)

        await log_event({
            "event": "pubmed_esearch_error",
            "query": query,
        })

        return []

    async def efetch_batch(self, batch: list[str]):

        async with self.semaphore:

            for attempt in range(MAX_RETRIES):

                try:

                    def _fetch():
                        fetch = Entrez.efetch(
                            db="pubmed",
                            id=batch,
                            rettype="abstract",
                            retmode="xml",
                        )

                        data = Entrez.read(fetch)
                        fetch.close()

                        return data

                    return await asyncio.to_thread(_fetch)

                except Exception:
                    await asyncio.sleep((2 ** attempt) + 0.1)

        await log_event({
            "event": "pubmed_efetch_error",
            "batch_size": len(batch),
        })

        return None

    async def iter_query(self, query: str, checkpoint: dict):

        ids = await self.esearch(query)

        ids = [
            pmid
            for pmid in ids
            if pmid not in checkpoint["done_ids"]
        ]

        if not ids:
            return

        with make_bar(
            "pubmed",
            f"[PubMed] {query}"
        ) as pbar:

            for i in range(0, len(ids), BATCH_SIZE):

                batch = ids[i:i + BATCH_SIZE]
                data = await self.efetch_batch(batch)

                if not data:
                    continue

                try:

                    for article in data["PubmedArticle"]:

                        medline = article["MedlineCitation"]
                        article_data = medline["Article"]

                        pmid = str(medline["PMID"])
                        title = str(article_data.get("ArticleTitle", ""))
                        abstracts = extract_pubmed_abstracts(article_data)

                        pbar.update(1)

                        if not abstracts:
                            continue

                        checkpoint["done_ids"].append(pmid)

                        yield {
                            "source": "pubmed",
                            "query": query,
                            "authors": extract_authors(article_data),
                            "published": extract_date(article_data),
                            "id": pmid,
                            "doi": extract_doi(article_data),
                            "title": title,
                            "abstracts": abstracts,
                        }

                except Exception:

                    await log_event({
                        "event": "pubmed_parse_error",
                        "query": query,
                    })

                await asyncio.sleep(REQUEST_DELAY)


async def fetch_pubmed(query: str, checkpoint: dict):

    fetcher = PubMedFetcher()
    results = []

    async for item in fetcher.iter_query(query, checkpoint):
        results.append(item)

    return results