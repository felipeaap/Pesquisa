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

# match "Abstract in <lang>" with optional punctuation/whitespace after
LANG_MARKER = re.compile(
    r'Abstract\s+in\s+(' + '|'.join(KNOWN_LANGUAGES) + r')',
    re.IGNORECASE
)

def split_abstract_by_language(raw: str) -> dict[str, str]:
    parts = LANG_MARKER.split(raw)
    out = {}
    it = iter(parts[1:])
    for lang, body in zip(it, it):
        # strip leading punctuation, whitespace, and the word "Abstract" if repeated
        body = re.sub(r'^[\s\W]+', '', body)          # strip leading non-word chars
        body = re.sub(r'^Abstract\b\s*', '', body, flags=re.IGNORECASE)  # strip repeated "Abstract"
        out[lang.lower()] = body.strip()
    return out if out else {"default": raw.strip()}

def extract_pid(url: str) -> str:
    pid = urllib.parse.parse_qs(urllib.parse.urlparse(url).query).get("pid", [None])[0]
    return pid or url