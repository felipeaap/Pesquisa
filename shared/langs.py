from openalex.utils import ISO_6391_MAP
from pubmed.utils import ISO_6392_MAP
from scielo.utils import KNOWN_LANGUAGES as SCIELO_LANGS

LABEL_FIXES = {
    # english bleedthrough
    "englishabstract": "english", "englishthe": "english",
    "englishbackground": "english", "englishobjective": "english",
    "englishobjectives": "english", "englishintroduction": "english",
    "englishsummary": "english", "englishthis": "english",
    "englishcontext": "english", "englishpurpose": "english",
    "englishabastract": "english", "englishabstractbackground": "english",
    # portuguese bleedthrough
    "portugueseresumo": "portuguese", "portugueseo": "portuguese",
    "portuguesea": "portuguese", "portugueseas": "portuguese",
    "portugueseobjetivo": "portuguese", "portugueseobjetivos": "portuguese",
    "portugueseintrodução": "portuguese", "portuguesejustificativa": "portuguese",
    "portugueseeste": "portuguese", "portugueseobjetivou": "portuguese",
    "portugueseos": "portuguese", "portuguesefundamento": "portuguese",
    "portugueseembora": "portuguese", "portuguesecontexto": "portuguese",
    "portuguesecontextualização": "portuguese", "portugueseresumofundamento": "portuguese",
    # spanish bleedthrough
    "spanishresumen": "spanish", "spanishla": "spanish",
    "spanishel": "spanish", "spanishintroducción": "spanish",
    "spanishen": "spanish", "spanishobjetivo": "spanish",
    "spanishobjetivos": "spanish", "spanishse": "spanish",
    "spanishlas": "spanish", "spanishlos": "spanish",
    "spanishantecedentes": "spanish", "spanishjustificativa": "spanish",
    "spanisheste": "spanish", "spanishfundamento": "spanish",
    "spanishpara": "spanish", "spanishcon": "spanish",
    "spanishdurante": "spanish", "spanishintrodución": "spanish",
}

def normalize_lang_key(lang: str) -> str:
    lang = lang.lower().strip()
    if lang in LABEL_FIXES:
        return LABEL_FIXES[lang]
    if lang in ISO_6391_MAP.keys():
        return ISO_6391_MAP[lang]
    if lang in ISO_6392_MAP.keys():
        return ISO_6392_MAP[lang]
    if lang in SCIELO_LANGS:
        return lang
    return "other"