import asyncio
from utils import save_checkpoint, save_jsonl_async, load_checkpoint, hash_text
from pubmed.pubmed_fetcher import fetch_pubmed
from scielo.scielo_fetcher import fetch_scielo

async def main():
    from queries import QUERIES

    checkpoint = load_checkpoint()

    for q in QUERIES:
        loop = asyncio.get_event_loop()
        pubmed_future = loop.run_in_executor(None, fetch_pubmed, q, checkpoint)
        scielo_future = fetch_scielo(q)

        pubmed_data, scielo_data = await asyncio.gather(
            pubmed_future,
            scielo_future
        )

        combined = pubmed_data + scielo_data

        for item in combined:
            item_hash = hash_text(item["id"])

            if item_hash in checkpoint["done_ids"]:
                print(f"[SKIP] {item['source']} | {item['title'][:60]}")
                continue

            await save_jsonl_async(item)
            checkpoint["done_ids"].append(item_hash)
            save_checkpoint(checkpoint)

        print(f"[DONE] {q} → {len(combined)} artigos")


if __name__ == "__main__":
    asyncio.run(main())