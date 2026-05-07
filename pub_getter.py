import time
import json
import random
import asyncio
import aiohttp
import aiofiles
import hashlib
from tqdm import tqdm
from bs4 import BeautifulSoup
from Bio import Entrez
from collections import defaultdict

LOG_FILE = "pipeline_log.jsonl"

async def log_event(event: dict):
    async with aiofiles.open(LOG_FILE, "a") as f:
        await f.write(json.dumps(event) + "\n")

Entrez.email = "felipeplentz0@gmail.com"

OUTPUT_FILE = "dataset_raw.jsonl"
CHECKPOINT_FILE = "checkpoint.json"

QUERIES = [
    "renal physiology",
    "cardiovascular physiology",
    "respiratory physiology",
    "cellular physiology",
    "nervous physiology",
    "digestive physiology",
    "reproductive physiology",
    "endocrine physiology",
    "general physiology"
]

MAX_PUBMED = 200
SCIELO_PAGES = 5
SCIELO_CONCURRENCY = 5  # controle fino aqui


async def fetch_with_retry(session, url, params=None, retries=3, base_delay=0.5):
    for attempt in range(retries):
        start = time.time()
        try:
            async with session.get(url, params=params, timeout=10) as resp:
                text = await resp.text()

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

def load_checkpoint():
    try:
        with open(CHECKPOINT_FILE, "r") as f:
            return json.load(f)
    except:
        return {"done_ids": []}


def save_checkpoint(state):
    with open(CHECKPOINT_FILE, "w") as f:
        json.dump(state, f)


def hash_text(text):
    return hashlib.md5(text.encode()).hexdigest()

async def save_jsonl_async(data):
    async with aiofiles.open(OUTPUT_FILE, "a", encoding="utf-8") as f:
        await f.write(json.dumps(data, ensure_ascii=False) + "\n")


def fetch_pubmed(query, checkpoint):
    print(f"[PubMed] {query}")

    handle = Entrez.esearch(
        db="pubmed",
        term=query,
        retmax=MAX_PUBMED
    )
    record = Entrez.read(handle)
    ids = record["IdList"]

    results = []

    for pmid in tqdm(ids):
        if pmid in checkpoint["done_ids"]:
            continue

        try:
            fetch = Entrez.efetch(
                db="pubmed",
                id=pmid,
                rettype="abstract",
                retmode="xml"
            )
            data = Entrez.read(fetch)

            article = data["PubmedArticle"][0]
            article_data = article["MedlineCitation"]["Article"]

            title = article_data.get("ArticleTitle", "")
            abstract = ""

            if "Abstract" in article_data:
                abstract_list = article_data["Abstract"]["AbstractText"]
                abstract = " ".join(str(x) for x in abstract_list)

            if abstract:
                results.append({
                    "source": "pubmed",
                    "query": query,
                    "id": pmid,
                    "title": title,
                    "text": abstract
                })

                checkpoint["done_ids"].append(pmid)

            time.sleep(0.34)  # respeita rate limit (~3 req/s)

        except Exception:
            continue

    return results


async def fetch_scielo_article(session, url, semaphore, stats):
    async with semaphore:
        html = await fetch_with_retry(session, url)

        if not html:
            stats["fail"] += 1
            return None

        soup = BeautifulSoup(html, "lxml")
        abstract_tag = soup.select_one("div.abstract")

        if not abstract_tag:
            stats["no_abstract"] += 1

            await log_event({
                "event": "scielo_article",
                "status": "no_abstract",
                "url": url
            })

            return None

        stats["success"] += 1

        await log_event({
            "event": "scielo_article",
            "status": "success",
            "url": url
        })

        return abstract_tag.text.strip()


async def fetch_scielo(query):
    print(f"[SciELO] {query}")

    base_url = "https://search.scielo.org/"
    results = []
    stats = defaultdict(int)
    semaphore = asyncio.Semaphore(5)

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Referer": "https://search.scielo.org/",
        "Connection": "keep-alive",
        "DNT": "1",
    }

    # TCPConnector with SSL and a realistic timeout
    connector = aiohttp.TCPConnector(ssl=True)
    timeout = aiohttp.ClientTimeout(total=30)

    async with aiohttp.ClientSession(
        headers=headers,
        connector=connector,
        timeout=timeout,
    ) as session:

        # Warm up: visit the homepage first to get cookies, just like a browser would
        await session.get("https://search.scielo.org/")
        await asyncio.sleep(1.5)  # brief pause after landing

        all_tasks = []

        for page in range(1, 20):
            params = {
                "q": query,
                "lang": "en",
                "count": 20,
                "from": (page - 1) * 20,
                "format": "abstract",
            }

            html = await fetch_with_retry(session, base_url, params=params)
            if not html:
                print(f"[SciELO] No HTML on page {page}")
                continue

            # Detect block even if fetch_with_retry swallows the status code
            if "403 Forbidden" in html or "<title>403" in html:
                print(f"[SciELO] Still blocked on page {page}")
                break
            

            soup = BeautifulSoup(html, "lxml")
            articles = soup.select("div.results div.item")
            print(f"[SciELO] Page {page}: {len(articles)} articles")

            if not articles:
                with open("scielo_debug.html", "w", encoding="utf-8") as f:
                    f.write(html)
                print(f"[SciELO] HTML snippet: {html[:300]}")
                break

            for art in articles:
                a = art.find("a", title=True)  # the <a> has a title attribute
                if not a:
                    continue

                href = a.get("href", "")
                if not href:
                    continue

                link = href if href.startswith("http") else f"https://search.scielo.org{href}"
                title = a.find("strong", class_="title")
                title = title.get_text(strip=True) if title else a.get("title", "").strip()

                source_div = art.select_one("div.source")
                abstract_div = source_div.find_next_sibling("div", class_=False) if source_div else None
                inline_abstract = abstract_div.get_text(strip=True) if abstract_div else None

                stats["total"] += 1

                if inline_abstract:
                    stats["inline_abstract"] += 1
                    results.append({
                        "source": "scielo",
                        "query": query,
                        "id": link,
                        "title": title,
                        "text": inline_abstract,
                    })
                else:
                    task = asyncio.create_task(
                        fetch_scielo_article(session, link, semaphore, stats)
                    )
                    all_tasks.append((task, title, link))

            # Human-like delay between pages
            await asyncio.sleep(random.uniform(1.0, 2.5))

        for task, title, link in all_tasks:
            abstract = await task
            if abstract:
                results.append({
                    "source": "scielo",
                    "query": query,
                    "id": link,
                    "title": title,
                    "text": abstract,
                })
            else:
                stats["no_abstract"] += 1

    await log_event({"event": "scielo_summary", "query": query, "stats": dict(stats)})
    print(f"[STATS] {query}: {dict(stats)}")
    return results

async def main():
    checkpoint = load_checkpoint()

    for q in QUERIES:

        # roda em paralelo:
        loop = asyncio.get_event_loop()
        pubmed_future = loop.run_in_executor(None, fetch_pubmed, q, checkpoint)
        scielo_future = fetch_scielo(q)

        pubmed_data, scielo_data = await asyncio.gather(
            pubmed_future,
            scielo_future
        )

        combined = pubmed_data + scielo_data

        for item in combined:
            item_hash = hash_text(item["text"])

            if item_hash in checkpoint["done_ids"]:
                print(f"[SKIP] {item['source']} | {item['title'][:60]}")  # ← add this
                continue

            await save_jsonl_async(item)
            checkpoint["done_ids"].append(item_hash)

        save_checkpoint(checkpoint)

        print(f"[DONE] {q} → {len(combined)} artigos")


if __name__ == "__main__":
    asyncio.run(main())