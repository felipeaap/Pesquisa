import asyncio
import argparse
from utils import save_checkpoint, save_jsonl_async, load_checkpoint, hash_text
from pubmed.pubmed_fetcher import fetch_pubmed
from scielo.scielo_fetcher import fetch_scielo

import os
from dotenv import load_dotenv

load_dotenv()
QUERIES = [q.strip() for q in os.getenv("QUERIES", "").split(",") if q.strip()]

# registry — add new fetchers here
FETCHERS = {
    "pubmed": lambda q, checkpoint: asyncio.get_event_loop().run_in_executor(
        None, fetch_pubmed, q, checkpoint
    ),
    "scielo": lambda q, checkpoint: fetch_scielo(q),
}


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

        print(f"[DONE] {q} → {len(combined)} artigos")


if __name__ == "__main__":
    asyncio.run(main())