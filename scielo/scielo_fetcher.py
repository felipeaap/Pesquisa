import random
import asyncio
import aiohttp
from bs4 import BeautifulSoup
from collections import defaultdict
from utils import log_event
from scielo.utils import fetch_with_retry, split_abstract_by_language, extract_pid

SCIELO_PAGES = 20
SCIELO_CONCURRENCY = 5

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
    semaphore = asyncio.Semaphore(SCIELO_CONCURRENCY)

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

        for page in range(1, SCIELO_PAGES + 1):
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
                with open("scielo/debug/scielo_debug.html", "w", encoding="utf-8") as f:
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
                    results.append({
                        "source": "scielo",
                        "query": query,
                        "id": extract_pid(link),
                        "url": link,  
                        "title": title,
                        "abstracts": split_abstract_by_language(inline_abstract),
                    })
                else:
                    task = asyncio.create_task(
                        fetch_scielo_article(session, link, semaphore, stats)
                    )
                    all_tasks.append((task, title, link))

            await asyncio.sleep(random.uniform(1.0, 2.5))

        gathered = await asyncio.gather(*[t for t, _, _ in all_tasks], return_exceptions=True)
        for (_, title, link), abstract in zip(all_tasks, gathered):
            if isinstance(abstract, Exception) or not abstract:
                stats["no_abstract"] += 1
            else:
                results.append({
                    "source": "scielo",
                    "query": query,
                    "id": extract_pid(link),
                    "url": link,
                    "title": title,
                    "abstracts": split_abstract_by_language(abstract),
                })

    await log_event({"event": "scielo_summary", "query": query, "stats": dict(stats)})
    print(f"[STATS] {query}: {dict(stats)}")
    return results