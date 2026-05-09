import os
from dotenv import load_dotenv
from tqdm import tqdm
from Bio import Entrez

load_dotenv()
Entrez.email = os.getenv("ENTREZ_EMAIL")

MAX_PUBMED = 200

def extract_pubmed_abstracts(article_data: dict) -> dict[str, str]:
    abstracts = {}

    # primary abstract — may be english or the article's original language
    if "Abstract" in article_data:
        lang = article_data.get("Language", ["en"])[0].lower()  # Language lives one level up
        text = " ".join(str(x) for x in article_data["Abstract"]["AbstractText"])
        if text:
            abstracts[lang] = text

    # OtherAbstract holds translations (e.g. portuguese, spanish)
    for other in article_data.get("OtherAbstract", []):
        lang = str(other.get("@Language", "unknown")).lower()
        text = " ".join(str(x) for x in other.get("AbstractText", []))
        if text:
            abstracts[lang] = text

    return abstracts  # e.g. {"en": "...", "pt": "...", "es": "..."}

def fetch_pubmed(query, checkpoint):
    print(f"[PubMed] {query}")

    handle = Entrez.esearch(db="pubmed", term=query, retmax=MAX_PUBMED)
    ids = Entrez.read(handle)["IdList"]
    ids = [pmid for pmid in ids if pmid not in checkpoint["done_ids"]]

    if not ids:
        return []

    fetch = Entrez.efetch(db="pubmed", id=ids, rettype="abstract", retmode="xml")
    data  = Entrez.read(fetch)
    results = []

    for article in tqdm(data["PubmedArticle"]):
        medline      = article["MedlineCitation"]
        article_data = medline["Article"]
        pmid         = str(medline["PMID"])
        title        = str(article_data.get("ArticleTitle", ""))
        abstracts    = extract_pubmed_abstracts(article_data)

        if abstracts:
            results.append({
                "source":    "pubmed",
                "query":     query,
                "id":        pmid,
                "title":     title,
                "abstracts": abstracts,
            })
            checkpoint["done_ids"].append(pmid)

    return results