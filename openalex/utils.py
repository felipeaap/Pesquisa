
import os
import langdetect
from dotenv import load_dotenv
from langdetect.lang_detect_exception import LangDetectException

load_dotenv()

ISO_6391_MAP = {
    # germanic
    "en": "english", "de": "german", "nl": "dutch", "sv": "swedish",
    "no": "norwegian", "da": "danish", "fi": "finnish", "af": "afrikaans",
    # romance
    "pt": "portuguese", "es": "spanish", "fr": "french", "it": "italian",
    "ro": "romanian", "ca": "catalan", "gl": "galician",
    # slavic
    "ru": "russian", "pl": "polish", "cs": "czech", "sk": "slovak",
    "uk": "ukrainian", "bg": "bulgarian", "sr": "serbian",
    "hr": "croatian", "sl": "slovenian",
    # semitic
    "ar": "arabic", "he": "hebrew",
    # east asian
    "zh": "chinese", "ja": "japanese", "ko": "korean",
    # south/southeast asian
    "hi": "hindi", "bn": "bengali", "ta": "tamil", "te": "telugu",
    "ml": "malayalam", "th": "thai", "vi": "vietnamese",
    "id": "indonesian", "ms": "malay",
    # other
    "tr": "turkish", "fa": "persian", "el": "greek", "hu": "hungarian",
    "ka": "georgian", "hy": "armenian", "sw": "swahili", "tl": "tagalog",
}

def make_headers() -> dict:
    email = os.getenv("ENTREZ_EMAIL", "")
    return {"User-Agent": f"pesquisa/1.0 (mailto:{email})"}

def reconstruct_abstract(inverted_index: dict | None) -> str:
    if not inverted_index:
        return ""
    positions = []
    for word, pos_list in inverted_index.items():
        for pos in pos_list:
            positions.append((pos, word))
    return " ".join(word for _, word in sorted(positions))


def extract_authors(work: dict) -> list[str]:
    return [
        a["author"]["display_name"]
        for a in work.get("authorships", [])
        if a.get("author") and a["author"].get("display_name")
    ]

def infer_language(work: dict, abstract: str = "") -> str:
    lang = work.get("language")
    if lang:
        return lang

    primary = work.get("primary_location") or {}
    source  = primary.get("source") or {}

    source_lang = source.get("language")
    if source_lang:
        return source_lang
    
    source_name = (source.get("display_name") or "").lower()
    if any(w in source_name for w in ("revista", "Brazilian", "brasileiro", "brasileira")):
        return "pt"
    if any(w in source_name for w in ("journal", "american", "british", "european")):
        return "en"
    if any(w in source_name for w in ("revue", "annales")):
        return "fr"
    if any(w in source_name for w in ("zeitschrift", "archiv")):
        return "de"

    if abstract and len(abstract) > 50:
        try:
            return langdetect.detect(abstract)
        except LangDetectException:
            pass

    return "unknown"