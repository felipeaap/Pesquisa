# scielo_fetcher.py
import os
import random
import asyncio
import aiohttp
import urllib.parse
from utils.progress import make_bar
from bs4 import BeautifulSoup
from collections import defaultdict
from playwright.async_api import async_playwright, BrowserContext
from utils.files import log_event
from scielo.utils import (split_abstract_by_language, extract_pid, 
                          extract_doi, extract_doi_from_text, 
                          extract_authors_from_card, extract_date_from_card)
from scielo.cookie import refresh_scielo_cookie
from scielo.block_guard import fetch_with_retry, is_blocked, BLOCKED

SCIELO_CONCURRENCY = 5
BASE_URL = "https://search.scielo.org/"


async def make_aiohttp_session() -> aiohttp.ClientSession:
    connector = aiohttp.TCPConnector(ssl=True)
    timeout = aiohttp.ClientTimeout(total=30)
    return aiohttp.ClientSession(connector=connector, timeout=timeout)


async def make_playwright_context(playwright) -> tuple:
    browser = await playwright.chromium.launch(headless=True)
    context = await browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36",
        locale="en-US",
        timezone_id="America/Sao_Paulo",
    )

    # inject current cookie into the Playwright context
    for chunk in os.getenv("SCIELO_COOKIE", "").split(";"):
        chunk = chunk.strip()
        if "=" not in chunk:
            continue
        name, value = chunk.split("=", 1)
        await context.add_cookies([{
            "name": name.strip(),
            "value": value.strip(),
            "domain": "search.scielo.org",
            "path": "/",
        }])

    return browser, context


async def fetch_search_page(context: BrowserContext, params: dict) -> str | None:
    """Fetch a search results page using Playwright."""
    url = BASE_URL + "?" + urllib.parse.urlencode(params)
    page = await context.new_page()
    try:
        await page.goto(url, wait_until="networkidle", timeout=30000)
        content = await page.content()
        return content
    except Exception as e:
        await log_event({"event": "playwright_fetch", "status": "fail", "url": url, "error": str(e)})
        return None
    finally:
        await page.close()


async def fetch_scielo_article(session, url, semaphore, stats):
    async with semaphore:
        html = await fetch_with_retry(session, url)
        if not html or html is BLOCKED:
            stats["fail"] += 1
            return None

        soup = BeautifulSoup(html, "lxml")
        abstract_tag = soup.select_one("div.abstract")

        if not abstract_tag:
            stats["no_abstract"] += 1
            await log_event({"event": "scielo_article", "status": "no_abstract", "url": url})
            return None

        stats["success"] += 1
        return {
            "abstract": abstract_tag.text.strip(),
            "doi":      extract_doi(soup),   # extract alongside abstract
        }


async def fetch_scielo(query: str) -> list:

    # ensure we have a valid cookie before starting
    if not os.getenv("SCIELO_COOKIE"):
        await refresh_scielo_cookie()

    results = []
    stats = defaultdict(int)
    semaphore = asyncio.Semaphore(SCIELO_CONCURRENCY)
    all_tasks = []
    page = 1
    consecutive_empties = 0
    block_retries = 0
    MAX_BLOCK_RETRIES = 3

    aio_session = await make_aiohttp_session()

    async with async_playwright() as playwright:
        browser, context = await make_playwright_context(playwright)

        try:
            with make_bar("scielo", f"[SciELO] {query}") as pbar:
                while True:
                    params = {
                        "q": query,
                        "lang": "en",
                        "count": 20,
                        "from": (page - 1) * 20,
                        "format": "abstract",
                    }

                    html = await fetch_search_page(context, params)

                    if not html:
                        await log_event({"event": "scielo_search", "status": "no_html"})
                        break

                    if is_blocked(html):
                        block_retries += 1
                        await log_event({"event": "scielo_block", "page": page, "query": query, "attempt": block_retries})

                        if block_retries >= MAX_BLOCK_RETRIES:
                            await log_event({"event": "scielo_max_retries", "page": page, "query": query})
                            break

                        # close current browser context and get a fresh cookie
                        await browser.close()
                        await refresh_scielo_cookie()
                        await asyncio.sleep(random.uniform(10, 20))
                        browser, context = await make_playwright_context(playwright)
                        continue  # retry same page

                    block_retries = 0  # reset on success

                    soup = BeautifulSoup(html, "lxml")
                    articles = soup.select("div.results div.item")

                    if not articles:
                        with open("scielo/debug/scielo_debug.html", "w", encoding="utf-8") as f:
                            f.write(html)
                        await log_event({"event": "scielo_no_articles", "page": page, "query": query})    
                        break

                    if len(articles) < 5:
                        consecutive_empties += 1
                        delay = random.uniform(3.0, 6.0) * consecutive_empties
                    else:
                        consecutive_empties = 0
                        delay = random.uniform(1.0, 2.5)

                    for art in articles:
                        a = art.find("a", title=True)
                        if not a:
                            continue

                        href = a.get("href", "")
                        if not href:
                            continue

                        link = href if href.startswith("http") else f"https://search.scielo.org{href}"
                        title_tag = a.find("strong", class_="title")
                        title = title_tag.get_text(strip=True) if title_tag else a.get("title", "").strip()

                        # DOI is in the article card text on the search page
                        doi = extract_doi_from_text(art.get_text())
                        authors = extract_authors_from_card(art)
                        published = extract_date_from_card(art)

                        source_div = art.select_one("div.source")
                        abstract_div = source_div.find_next_sibling("div", class_=False) if source_div else None
                        inline_abstract = abstract_div.get_text(strip=True) if abstract_div else None

                        stats["total"] += 1

                        if inline_abstract:
                            stats["inline_abstract"] += 1
                            results.append({
                                "source":    "scielo",
                                "query":     query,
                                "authors":   authors,
                                "published": published,
                                "id":        extract_pid(link),
                                "url":       link,
                                "doi":       doi,
                                "title":     title,
                                "abstracts": split_abstract_by_language(inline_abstract),
                            })
                        else:
                            task = asyncio.create_task(
                                fetch_scielo_article(aio_session, link, semaphore, stats)
                            )
                            all_tasks.append((task, title, link, doi, authors, published))
                        
                        pbar.update(1)

                    page += 1
                    await asyncio.sleep(delay)

        finally:
            await browser.close()
            await aio_session.close()

    gathered = await asyncio.gather(*[t for t, _, _, _, _, _ in all_tasks], return_exceptions=True)
    for (_, title, link, doi, authors, published), abstract in zip(all_tasks, gathered):
        if isinstance(abstract, Exception) or not abstract:
            stats["no_abstract"] += 1
        else:
            results.append({
                "source":    "scielo",
                "query":     query,
                "authors":   authors,
                "published": published,
                "id":        extract_pid(link),
                "url":       link,
                "doi":       doi,
                "title":     title,             
                "abstracts": split_abstract_by_language(abstract),
            })

    await log_event({"event": "scielo_summary", "query": query, "stats": dict(stats)})
    return results