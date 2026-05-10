# scielo_fetcher.py
import os
import random
import asyncio
import aiohttp
import urllib.parse
import re
import sys
from tqdm import tqdm
from bs4 import BeautifulSoup
from collections import defaultdict
from playwright.async_api import async_playwright, BrowserContext

# Tenta importar as utilidades tratando o caminho das pastas
root_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if root_path not in sys.path:
    sys.path.insert(0, root_path)

try:
    from utils import log_event
    from scielo.utils import split_abstract_by_language, extract_pid
    from scielo.cookie import refresh_scielo_cookie
    from scielo.block_guard import fetch_with_retry, is_blocked, BLOCKED
except ImportError as e:
    print(f"⚠️ Erro de importação: {e}")
    # Fallback básico para não quebrar o script se rodar isolado
    async def log_event(data): print(f"LOG: {data}")
    BLOCKED = "blocked"
    def is_blocked(html): return False

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

    # Injeta cookies se existirem
    for chunk in os.getenv("SCIELO_COOKIE", "").split(";"):
        chunk = chunk.strip()
        if "=" not in chunk: continue
        name, value = chunk.split("=", 1)
        await context.add_cookies([{
            "name": name.strip(),
            "value": value.strip(),
            "domain": "search.scielo.org",
            "path": "/",
        }])
    return browser, context

async def fetch_search_page(context: BrowserContext, params: dict) -> str | None:
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
        abstract_tag = soup.select_one("div.abstract") or soup.select_one(".abstract")
        
        if not abstract_tag:
            stats["no_abstract"] += 1
            return None

        stats["success"] += 1
        return abstract_tag.text.strip()

async def fetch_scielo(query: str) -> list:
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
            with tqdm(desc=f"[SciELO] {query}", unit="art") as pbar:
                while True:
                    params = {
                        "q": query,
                        "lang": "pt",
                        "count": 20,
                        "from": (page - 1) * 20,
                        "format": "abstract",
                    }

                    html = await fetch_search_page(context, params)
                    if not html or is_blocked(html):
                        block_retries += 1
                        if block_retries >= MAX_BLOCK_RETRIES: break
                        await browser.close()
                        await refresh_scielo_cookie()
                        await asyncio.sleep(random.uniform(10, 20))
                        browser, context = await make_playwright_context(playwright)
                        continue

                    block_retries = 0
                    soup = BeautifulSoup(html, "lxml")
                    articles = soup.select("div.results div.item")

                    if not articles: break

                    for art in articles:
                        a = art.find("a", title=True)
                        if not a: continue

                        href = a.get("href", "")
                        link = href if href.startswith("http") else f"https://search.scielo.org{href}"
                        
                        # Título
                        title_tag = a.find("strong", class_="title")
                        title = title_tag.get_text(strip=True) if title_tag else a.get("title", "").strip()

                        # Autores
                        authors_div = art.select_one("div.authors")
                        authors = authors_div.get_text(strip=True) if authors_div else None

                        # Ano (via Regex na div source)
                        source_div = art.select_one("div.source")
                        source_text = source_div.get_text() if source_div else ""
                        year_match = re.search(r'\b(19|20)\d{2}\b', source_text)
                        year = year_match.group(0) if year_match else None

                        # Abstract Inline
                        abstract_div = art.select_one("div.abstract") or art.find("div", class_="item")
                        inline_abstract = abstract_div.get_text(strip=True) if abstract_div and "Abstract" in abstract_div.text else None

                        item_base = {
                            "source": "scielo",
                            "query": query,
                            "id": extract_pid(link),
                            "url": link,
                            "title": title,
                            "authors": authors,
                            "year": year
                        }

                        stats["total"] += 1

                        if inline_abstract:
                            stats["inline_abstract"] += 1
                            item_base["abstracts"] = split_abstract_by_language(inline_abstract)
                            results.append(item_base)
                        else:
                            task = asyncio.create_task(fetch_scielo_article(aio_session, link, semaphore, stats))
                            all_tasks.append((task, item_base))
                        
                        pbar.update(1)

                    page += 1
                    await asyncio.sleep(random.uniform(1, 3))

        finally:
            await browser.close()
            await aio_session.close()

    if all_tasks:
        gathered = await asyncio.gather(*[t for t, _ in all_tasks], return_exceptions=True)
        for (task, item), abstract in zip(all_tasks, gathered):
            if not isinstance(abstract, Exception) and abstract:
                item["abstracts"] = split_abstract_by_language(abstract)
                results.append(item)
            else:
                stats["no_abstract"] += 1

    await log_event({"event": "scielo_summary", "query": query, "stats": dict(stats)})
    print(f"\n[STATS] {query}: {dict(stats)}")
    return results

# --- GATILHO DE EXECUÇÃO ---
if __name__ == "__main__":
    import json
    
    async def main():
        # TROQUE O TERMO AQUI
        query = "educação" 
        print(f"🚀 Iniciando tranco na SciELO: {query}")
        
        try:
            artigos = await fetch_scielo(query)
            
            # Garante que a pasta data existe
            os.makedirs("../data", exist_ok=True)
            output_file = "../data/scielo_data.jsonl"
            
            with open(output_file, "a", encoding="utf-8") as f:
                for art in artigos:
                    f.write(json.dumps(art, ensure_ascii=False) + "\n")
            
            print(f"✅ Finalizado! {len(artigos)} artigos salvos em {output_file}")
            
        except Exception as e:
            print(f"❌ Erro crítico: {e}")

    asyncio.run(main())