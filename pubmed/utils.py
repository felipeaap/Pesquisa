ISO_6392_MAP = {
    # germanic
    "eng": "english", "deu": "german", "ger": "german", "nld": "dutch",
    "dut": "dutch", "swe": "swedish", "nor": "norwegian", "dan": "danish",
    "fin": "finnish", "afr": "afrikaans",
    # romance
    "por": "portuguese", "spa": "spanish", "fra": "french", "fre": "french",
    "ita": "italian", "ron": "romanian", "rum": "romanian", "cat": "catalan",
    "glg": "galician",
    # slavic
    "rus": "russian", "pol": "polish", "ces": "czech", "cze": "czech",
    "slk": "slovak", "slo": "slovak", "ukr": "ukrainian", "bul": "bulgarian",
    "srp": "serbian", "hrv": "croatian", "slv": "slovenian",
    # semitic
    "ara": "arabic", "heb": "hebrew",
    # east asian
    "zho": "chinese", "chi": "chinese", "jpn": "japanese", "kor": "korean",
    # south/southeast asian
    "hin": "hindi", "ben": "bengali", "tam": "tamil", "tel": "telugu",
    "mal": "malayalam", "tha": "thai", "vie": "vietnamese", "ind": "indonesian",
    "msa": "malay", "may": "malay",
    # other
    "tur": "turkish", "fas": "persian", "per": "persian", "ell": "greek",
    "gre": "greek", "hun": "hungarian", "kat": "georgian", "hye": "armenian",
    "arm": "armenian", "swa": "swahili", "tgl": "tagalog",
}

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

def extract_doi(article_data: dict) -> str:
    """Extract DOI from PubMed ELocationID list."""
    for loc in article_data.get("ELocationID", []):
        if str(loc.attributes.get("EIdType", "")).lower() == "doi":
            return str(loc).strip()
    return ""

def extract_authors(article_data: dict) -> list[str]:
    authors = []
    for author in article_data.get("AuthorList", []):
        last  = author.get("LastName", "")
        fore  = author.get("ForeName", "")
        name  = f"{last}, {fore}".strip(", ")
        if name:
            authors.append(name)
    return authors

def extract_date(article_data: dict) -> str:
    pub_date = article_data.get("Journal", {}).get("JournalIssue", {}).get("PubDate", {})
    year  = pub_date.get("Year", "")
    month = pub_date.get("Month", "")
    day   = pub_date.get("Day", "")
    return "-".join(part for part in [year, month, day] if part)