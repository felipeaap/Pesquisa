# openalex/openalex_fetcher.py
import time
import requests
from tqdm import tqdm
from openalex.utils import make_headers, infer_language, extract_authors, reconstruct_abstract

BASE_URL    = "https://api.openalex.org/works"
PER_PAGE    = 200
MAX_RESULTS = 600
DELAY       = 1.0

def fetch_page(query: str, cursor: str = "*") -> dict | None:
    params = {
        "search":   query,
        "per_page": PER_PAGE,
        "cursor":   cursor,
        "filter":   "has_abstract:true",
        "select": "id,doi,title,language,abstract_inverted_index,authorships,primary_location,publication_date",
    }
    try:
        resp = requests.get(BASE_URL, params=params, headers=make_headers(), timeout=15)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        return None

def fetch_openalex(query: str, checkpoint: dict) -> list[dict]:
    results = []
    cursor  = "*"
    total_fetched = 0
    unknown_lang  = 0

    with tqdm(desc=f"[OpenAlex] {query}", unit="art") as pbar:
        while total_fetched < MAX_RESULTS:
            data = fetch_page(query, cursor)

            if not data:
                break

            works = data.get("results", [])
            if not works:
                break

            for work in works:
                openalex_id = (work.get("id") or "").replace("https://openalex.org/", "")

                if not openalex_id or openalex_id in checkpoint["done_ids"]:
                    continue

                abstract = reconstruct_abstract(work.get("abstract_inverted_index"))
                if not abstract:
                    continue

                lang = infer_language(work,abstract)
                if lang == "unknown":
                    unknown_lang += 1

                results.append({
                    "source":    "openalex",
                    "query":     query,
                    "authors":   extract_authors(work),
                    "published": work.get("publication_date") or "",
                    "id":        openalex_id,
                    "doi":       work.get("doi") or "",
                    "title":     (work.get("title") or "").strip(),
                    "abstracts": {lang: abstract},
                })
                pbar.update(1)

            total_fetched += len(works)

            next_cursor = data.get("meta", {}).get("next_cursor")
            if not next_cursor:
                break

            cursor = next_cursor
            time.sleep(DELAY)
    return results