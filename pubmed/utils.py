LANG_CODE_MAP = {
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