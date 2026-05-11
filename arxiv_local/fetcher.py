# arxiv/arxiv_fetcher.py
import arxiv
from tqdm import tqdm

MAX_ARXIV  = 500   # reduce from 500 — arXiv rate limits aggressive pagination
BATCH_SIZE = 100   # max per request
DELAY      = 5.0   # seconds between pages — arXiv asks for 3s minimum


def fetch_arxiv(query: str, checkpoint: dict) -> list[dict]:
    client = arxiv.Client(
        page_size=BATCH_SIZE,
        delay_seconds=DELAY,      # wait between paginated requests
        num_retries=5,            # retry up to 5 times on 429
    )

    search = arxiv.Search(
        query=query,
        max_results=MAX_ARXIV,
        sort_by=arxiv.SortCriterion.Relevance,
    )

    results = []

    try:
        for result in tqdm(client.results(search), desc=f"[arXiv] {query}", unit="art"):
            arxiv_id = result.entry_id.split("/")[-1]

            if arxiv_id in checkpoint["done_ids"]:
                continue

            abstract = result.summary.strip()
            if not abstract:
                continue

            results.append({
                "source":    "arxiv",
                "query":     query,
                "authors":   [a.name for a in result.authors],
                "id":        arxiv_id,
                "doi":       result.doi or "",
                "title":     result.title.strip(),
                "abstracts": {"english": abstract},
            })

    except arxiv.HTTPError as e:
        pass
    return results