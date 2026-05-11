import tqdm
tqdm.tqdm.monitor_interval = 0

import os
from dotenv import load_dotenv

load_dotenv()
QUERIES = [q.strip() for q in os.getenv("QUERIES", "").split(",") if q.strip()]

from pubmed.fetcher import fetch_pubmed
from scielo.fetcher import fetch_scielo
from arxiv_local.fetcher import fetch_arxiv
from openalex.fetcher import fetch_openalex

FETCHERS = {
    "pubmed":    lambda q, cp: asyncio.get_event_loop().run_in_executor(None, fetch_pubmed, q, cp),
    "scielo":    lambda q, cp: fetch_scielo(q),
    "arxiv":     lambda q, cp: asyncio.get_event_loop().run_in_executor(None, fetch_arxiv, q, cp),
    "openalex":  lambda q, cp: fetch_openalex(q, cp),
}


import argparse

def parse_args():
    parser = argparse.ArgumentParser(description="Abstract scraper")
    parser.add_argument(
        "--sources",
        nargs="+",
        choices=FETCHERS.keys(),
        default=list(FETCHERS.keys()),
        metavar="SOURCE",
        help=f"Sources to fetch from. Available: {', '.join(FETCHERS.keys())}. Default: all",
    )
    return parser.parse_args()

import asyncio
from utils.files import save_checkpoint, save_jsonl_async, load_checkpoint, hash_text

async def main():
    args = parse_args()
    selected = args.sources
    print(f"[Runner] Sources: {', '.join(selected)}")

    checkpoint = load_checkpoint()

    for q in QUERIES:
        futures = [FETCHERS[source](q, checkpoint) for source in selected]
        results = await asyncio.gather(*futures)

        combined = [item for source_results in results for item in source_results]

        for item in combined:
            item_hash = hash_text(item["id"])

            if item_hash in checkpoint["done_ids"]:
                continue

            await save_jsonl_async(item)
            checkpoint["done_ids"].append(item_hash)

        save_checkpoint(checkpoint)
        print(f"[DONE] {q} → {len(combined)} artigos", flush=True)


if __name__ == "__main__":
    asyncio.run(main())