import re
import urllib.parse

KNOWN_LANGUAGES = {
    # germanic
    "english", "german", "dutch", "swedish", "norwegian", "danish",
    "finnish", "afrikaans",
    # romance
    "portuguese", "spanish", "french", "italian", "romanian", "catalan",
    "galician",
    # slavic
    "russian", "polish", "czech", "slovak", "ukrainian", "bulgarian",
    "serbian", "croatian", "slovenian",
    # semitic
    "arabic", "hebrew",
    # east asian
    "chinese", "japanese", "korean",
    # south/southeast asian
    "hindi", "bengali", "tamil", "telugu", "malayalam", "thai",
    "vietnamese", "indonesian", "malay",
    # other
    "turkish", "persian", "greek", "hungarian", "georgian",
    "armenian", "swahili", "tagalog",
}

LANG_MARKER = re.compile(
    r'Abstract\s+in\s+(' + '|'.join(sorted(KNOWN_LANGUAGES, key=len, reverse=True)) + r')(?=[A-Z\s\W]|$)',
    re.IGNORECASE
)

HEADER_NOISE = re.compile(
    r'^[\s\W]*(abstract|resumen|resumo|résumé|zusammenfassung|summary)\b[\s:.\-]*',
    re.IGNORECASE
)

def split_abstract_by_language(raw: str) -> dict[str, str]:
    parts = LANG_MARKER.split(raw)
    out = {}
    it = iter(parts[1:])
    for lang, body in zip(it, it):
        body = HEADER_NOISE.sub('', body).strip()
        if body:
            out[lang.lower()] = body
    return out if out else {"default": raw.strip()}

def extract_pid(url: str) -> str:
    pid = urllib.parse.parse_qs(urllib.parse.urlparse(url).query).get("pid", [None])[0]
    return pid or url

def extract_doi(soup) -> str:
    tag = soup.find("meta", attrs={"name": "citation_doi"})
    return tag["content"].strip() if tag and tag.get("content") else ""

def extract_doi_from_text(text: str) -> str:
    """Extract DOI from raw text containing 'DOI: 10.xxxx/...'"""
    match = re.search(r'DOI:\s*(10\.\S+)', text, re.IGNORECASE)
    return match.group(1).rstrip(".,)") if match else ""

def extract_authors_from_card(art) -> list[str]:
    return [
        a.get_text(strip=True)
        for a in art.find_all("a", href=True)
        if 'q=au:"' in a.get("href", "")
        and a.get_text(strip=True)
    ]

def extract_date_from_card(art) -> str:
    source_div = art.select_one("div.line.source")
    if not source_div:
        return ""

    # preserve spaces between spans
    text = source_div.get_text(" ", strip=True)

    # matches:
    # "jun 2026"
    # "Mar 2023"
    # "2024"
    match = re.search(r'\b(?:[A-Za-z]{3,9}\s+)?\d{4}\b', text)

    return match.group(0) if match else ""