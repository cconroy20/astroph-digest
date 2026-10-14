"""Author-name keys shared by the ADS ('Last, First') and arXiv ('First Last, ... and ...') forms.

Key = 'last|f' (surname + first initial), ascii-folded and lowercased. Coarse on purpose:
the two sources spell given names differently. Collisions on common surnames are
handled downstream by dividing by how often the key appears in the whole field.
"""
import re, unicodedata
from tex import detex_plain

# letters NFKD does not decompose to ASCII
FOLD = str.maketrans({"ø": "o", "ł": "l", "ß": "ss", "đ": "d", "æ": "ae", "œ": "oe", "ð": "d", "þ": "th", "ı": "i", "ŋ": "n"})

PARTICLES = {"van", "von", "de", "der", "den", "del", "della", "la", "le", "di", "da", "dos", "du", "ter", "ten", "st", "st."}
SUFFIX = {"jr", "jr.", "sr", "sr.", "ii", "iii", "iv"}


def fold(s):
    s = unicodedata.normalize("NFKD", s.translate(FOLD))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z\- ]", "", s.lower().replace("\\", "")).strip()


def key_ads(name):
    """'Belokurov, Vasily' -> 'belokurov|v'"""
    if "," not in name:
        return key_free(name)
    last, first = name.split(",", 1)
    last, first = fold(last), fold(first)
    if not last:
        return None
    return f"{last.replace(' ', '')}|{first[:1]}"


def key_free(name):
    """'Vasily Belokurov' / 'S. E. de Mink' -> key"""
    toks = [t for t in fold(name.replace(".", ". ")).split() if t not in SUFFIX]
    if not toks:
        return None
    if len(toks) == 1:
        return f"{toks[0]}|"
    i = len(toks) - 1
    while i > 1 and toks[i - 1] in PARTICLES:
        i -= 1
    last = "".join(toks[i:])
    return f"{last}|{toks[0][:1]}"


def surname(name):
    """Display surname with original spelling: 'Mithi A. C. de los Reyes' -> 'de los Reyes'."""
    toks = [t for t in name.split() if t.lower().strip(".,") not in SUFFIX]
    if len(toks) <= 1:
        return " ".join(toks)
    i = len(toks) - 1
    while i > 1 and toks[i - 1].lower() in PARTICLES | {"los", "las", "y"}:
        i -= 1
    return " ".join(toks[i:])


def split_arxiv(authors):
    """Split an arXiv authors string into names (drops affiliations in parentheses)."""
    s = re.sub(r"\([^()]*\)", "", detex_plain(authors))
    s = re.sub(r"\([^()]*\)", "", s)
    parts = re.split(r",\s*|\s+and\s+", s)
    return [p.strip() for p in parts if p.strip() and len(p.strip()) > 1 and "collaboration" not in p.lower()]


def keys_arxiv(authors, kmax=None):
    ks = [key_free(n) for n in split_arxiv(authors)]
    ks = [k for k in ks if k]
    return ks[:kmax] if kmax else ks


def keys_ads(names, kmax=None):
    ks = [key_ads(n) for n in names]
    ks = [k for k in ks if k]
    return ks[:kmax] if kmax else ks


def field_counts(papers, kmax=15):
    """How many astro-ph papers each author key appears on (first kmax authors)."""
    from collections import Counter
    c = Counter()
    for a in papers:
        c.update(set(keys_arxiv(a["authors"], kmax)))
    return c
