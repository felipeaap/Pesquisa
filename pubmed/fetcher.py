import os
import time
from dotenv import load_dotenv
from tqdm import tqdm
from Bio import Entrez
from pubmed.utils import extract_pubmed_abstracts, extract_doi, extract_authors, extract_date

load_dotenv()

Entrez.email = os.getenv("ENTREZ_EMAIL")

api_key = os.getenv("ENTREZ_API_KEY")
if api_key:
    Entrez.api_key = api_key

MAX_PUBMED = 400
BATCH_SIZE = 200
REQUEST_DELAY = 0.11 if api_key else 0.34  # 10 req/s with key, 3 req/s without


def fetch_pubmed(query, checkpoint):
    handle = Entrez.esearch(db="pubmed", term=query, retmax=MAX_PUBMED)
    ids = Entrez.read(handle)["IdList"]
    ids = [pmid for pmid in ids if pmid not in checkpoint["done_ids"]]

    if not ids:
        return []

    results = []

    # batch into chunks of 200
    for i in tqdm(range(0, len(ids), BATCH_SIZE),desc=f"[PubMed] {query}", unit="art"):
        batch = ids[i:i + BATCH_SIZE]

        try:
            fetch = Entrez.efetch(db="pubmed", id=batch, rettype="abstract", retmode="xml")
            data = Entrez.read(fetch)

            for article in data["PubmedArticle"]:
                medline      = article["MedlineCitation"]
                article_data = medline["Article"]
                pmid         = str(medline["PMID"])
                title        = str(article_data.get("ArticleTitle", ""))
                abstracts    = extract_pubmed_abstracts(article_data)

                if abstracts:
                    results.append({
                        "source":    "pubmed",
                        "query":     query,
                        "authors":   extract_authors(article_data),
                        "published": extract_date(article_data),
                        "id":        pmid,
                        "doi":       extract_doi(article_data),   # add this
                        "title":     title,
                        "abstracts": abstracts,
                    })
                    checkpoint["done_ids"].append(pmid)

        except Exception as e:
            continue

        time.sleep(REQUEST_DELAY)  # respect rate limit between batches
    return results

