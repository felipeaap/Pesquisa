
from pubmed.utils import LANG_CODE_MAP
from scielo.utils import KNOWN_LANGUAGES as SCIELO_LANGS

LANG_CODES = set(LANG_CODE_MAP.keys())
LANG_NAMES = SCIELO_LANGS
LANGS = LANG_NAMES | set(LANG_CODE_MAP.values())

def normalize_lang_key(lang: str) -> str:
    """Normalize any lang key to a full name. Handles ISO codes and full names."""
    lang = lang.lower().strip()
    if lang in LANG_CODES:                  # ISO code → full name
        return LANG_CODE_MAP[lang]
    if lang in LANG_NAMES:                  # already a full name
        return lang
    return "other"