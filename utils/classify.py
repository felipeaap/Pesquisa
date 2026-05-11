
from shared.langs import normalize_lang_key
from dateutil import parser as dateparser

def normalize_date(raw: str) -> str:
    if not raw:
        return ""
    try:
        return dateparser.parse(raw).strftime("%Y-%m-%d")
    except Exception:
        return raw  # keep original if parsing fails


def dedup(entries: list[dict]) -> tuple[list[dict], list[dict]]:
    seen = {}
    dupes = []
    for entry in entries:
        key = entry.get("doi") or entry.get("id")
        if not key:
            continue
        if key in seen:
            dupes.append(entry)
        else:
            seen[key] = entry
    return list(seen.values()), dupes


def classify_languages(entry: dict) -> dict:
    abstracts = entry.get("abstracts", {})

    normalized = {}
    for lang, text in abstracts.items():
        if text and text.strip():
            normalized[normalize_lang_key(lang)] = text.strip()

    entry["abstracts"]    = normalized
    entry["languages"]    = sorted(normalized.keys())
    entry["multilingual"] = len(normalized) > 1

    return entry