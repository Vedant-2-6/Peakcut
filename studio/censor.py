"""Content safety & profanity censor to prevent YouTube age restrictions (18+) and community guideline flags.

YouTube automatically age-restricts Shorts containing:
1. Profanity or vulgarity in Titles, Descriptions, or Tags.
2. Uncensored swear words in on-screen captions/subtitles (detected by YouTube OCR).
3. Explicit or vulgar terms in big hook overlays.

This module cleans metadata completely (removing swear words) and masks captions with asterisks (e.g. 'f***ing').
"""
import re

# Comprehensive dictionary of English and Hinglish profanity / slurs commonly used in gaming
PROFANITY_MASKS = {
    # English
    "motherfucking": "m****rf***ing",
    "motherfucker": "m****rf***er",
    "fucking": "f***ing",
    "fucked": "f***ed",
    "fucker": "f***er",
    "fuck": "f**k",
    "fucks": "f**ks",
    "bullshit": "bullsh*t",
    "shit": "sh*t",
    "shits": "sh*ts",
    "shitting": "sh*tting",
    "bitch": "b***h",
    "bitches": "b***hes",
    "bitching": "b***hing",
    "asshole": "a**hole",
    "assholes": "a**holes",
    "bastard": "b***ard",
    "bastards": "b***ards",
    "cunt": "c**t",
    "cunts": "c**ts",
    "dick": "d**k",
    "dicks": "d**ks",
    "pussy": "p***y",
    "pussies": "p***ies",
    "whore": "wh**e",
    "whores": "wh**es",
    "slut": "sl*t",
    "sluts": "sl*ts",
    "nigger": "n***er",
    "niggers": "n***ers",
    "nigga": "n***a",
    "niggas": "n***as",
    "retard": "r***rd",
    "retarded": "r***rded",
    # Hindi / Hinglish Gaming Slang
    "madarchod": "m****chod",
    "madarchodd": "m****chod",
    "mc": "m*",
    "bhenchod": "bh**chod",
    "behenchod": "beh**chod",
    "bc": "b*",
    "bhosdike": "bh***dike",
    "bhosadike": "bh***dike",
    "bhosadi": "bh***di",
    "chutiya": "ch***ya",
    "chutiye": "ch***ye",
    "chutiyapa": "ch***yapa",
    "gaand": "g**nd",
    "gand": "g*nd",
    "gandu": "g**du",
    "gaandu": "g**du",
    "lodu": "l*du",
    "lauda": "l**da",
    "lawda": "l**da",
    "loda": "l*da",
    "randi": "r**di",
    "saala": "s**la",
    "sala": "s**la",
    "harami": "h***mi",
    "kamine": "k***ne",
    "chut": "ch*t",
}

# Words to cleanly remove or tone down from titles & descriptions
# Instead of asterisks (which can still trip title clickbait bots), titles should be clean & natural
TITLE_REPLACEMENTS = {
    r"\bmotherfucking\b": "absolute",
    r"\bmotherfucker\b": "guy",
    r"\bfucking\b": "",
    r"\bfucked\b": "messed",
    r"\bfuck\b": "",
    r"\bfucker\b": "guy",
    r"\bbullshit\b": "nonsense",
    r"\bshit\b": "moment",
    r"\bbitch\b": "",
    r"\basshole\b": "",
    r"\bbastard\b": "",
    r"\bcunt\b": "",
    r"\bdick\b": "",
    r"\bpussy\b": "",
    r"\bnigga\b": "",
    r"\bnigger\b": "",
    r"\bmadarchod\b": "",
    r"\bbhenchod\b": "",
    r"\bbehenchod\b": "",
    r"\bbhosdike\b": "",
    r"\bchutiya\b": "",
    r"\bchutiye\b": "",
    r"\bgaand\b": "",
    r"\bgand\b": "",
    r"\blodu\b": "",
    r"\blauda\b": "",
    r"\brandi\b": "",
}

# Precompile patterns
_CAPTION_PATTERNS = [
    (re.compile(rf"\b{re.escape(k)}\b", re.IGNORECASE), v)
    for k, v in sorted(PROFANITY_MASKS.items(), key=lambda x: -len(x[0]))
]

_TITLE_PATTERNS = [
    (re.compile(k, re.IGNORECASE), v)
    for k, v in sorted(TITLE_REPLACEMENTS.items(), key=lambda x: -len(x[0]))
]


def clean_title_metadata(text: str) -> str:
    """Clean profanity completely from titles and descriptions so YouTube algorithms never flag them."""
    if not text:
        return ""
    result = str(text)
    for pat, rep in _TITLE_PATTERNS:
        result = pat.sub(rep, result)
    # Clean up double spaces or awkward leftover punctuation (e.g. "NOT A  SINGLE" -> "NOT A SINGLE")
    result = re.sub(r"\s+", " ", result).strip()
    result = re.sub(r"\s+([!?,.])", r"\1", result)
    # Ensure hashtags have a preceding space
    result = re.sub(r"(?<=\S)#", " #", result)
    return result


def mask_caption_word(word: str) -> str:
    """Mask profanity in on-screen captions / subtitles using asterisks (e.g. 'fucking' -> 'f***ing').

    Preserves case and punctuation.
    """
    if not word or len(word) < 2:
        return word
    result = str(word)
    for pat, mask in _CAPTION_PATTERNS:
        def _match_replace(m):
            matched = m.group(0)
            if matched.isupper():
                return mask.upper()
            if matched[0].isupper() and len(mask) > 1:
                return mask[0].upper() + mask[1:].lower()
            return mask.lower()
        result = pat.sub(_match_replace, result)
    return result


def sanitize_hook(hook: str) -> str:
    """Sanitize hooks for on-screen overlay banners and SEO."""
    if not hook:
        return ""
    cleaned = clean_title_metadata(hook)
    # If the hook was just a curse word (e.g. "FUCK"), give a generic high-energy hook
    if not cleaned or len(cleaned) < 3:
        return "CRAZY MOMENT"
    return cleaned
