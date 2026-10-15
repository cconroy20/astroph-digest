"""Pick the top figures of each paper from arXiv's HTML version.

1. Figures the authors name as key in the arXiv comments ("main results are shown in Figures 3, 4 and 5") come
   first.
2. Remaining slots (to six in all) go to the highest scores:
   (1 + number of times the paper's own text links to the figure) x section weight, where the weight is 2 for a
   figure inside any section or subsection titled "Results"/"Findings", 0.2 inside an appendix, 1 otherwise.
   Ties go to the earlier figure. Figures without an image (e.g. inline TikZ) are skipped.
The chosen figures are listed in the order they appear in the paper.

Each figure is stored as {"n": "Figure 3", "imgs": [absolute image URLs], "cap": caption with math as $...$,
"key": True if named by the authors}.
"""
import re, sys, time
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup

BASE = "https://arxiv.org/html/"
UA = {"User-Agent": "arxivsort (personal digest)"}
RESULTS = re.compile(r"\b(results?|findings?)\b", re.I)

# --- figures the authors name in the arXiv comments ---------------------------------------------------------------
DASH = "–"
# "Fig. 3"/"Figs. 3, 4" may carry a period; "Figure 3" may not ("9 figures. 3 tables" is a count, not a reference)
FIGREF = re.compile(r"\b(?:figs?\.?|figures?)\s*(\d+[a-z]?(?:\s*(?:,\s*and|,|and|&|-|" + DASH + r"|to)\s*\d+[a-z]?)*)", re.I)
COUNT = re.compile(r"\s*(pages?|tables?|figs?|figures?|appendi\w*)\b", re.I)
KEYWORD = re.compile(r"\b(key|main|summary|summari[sz]\w*|highlight\w*|headline|central|primary|most important|"
                     r"principal|major results?)\b", re.I)
REVISION = re.compile(r"\b(updat\w*|correct\w*|revis\w*|new|added|add|additional|replac\w*|chang\w*|fix\w*|typo\w*|"
                      r"movie|animation\w*|video|erratum|difference|previous version|v\d)\b", re.I)


def key_figures(comments):
    """Figure numbers the authors flag as key, e.g. "main results are shown in Figures 3, 4 and 5" -> ["3","4","5"].
    A reference counts only with a key/main/summary/highlight word in the same clause (within ~70 characters, no
    ';' between) and no revision word ("Fig. 14 updated", "animation of Fig. 2")."""
    out = []
    for m in FIGREF.finditer(comments or ""):
        if COUNT.match(comments, m.end()):  # "Figures 17 Pages"
            continue
        before = comments[max(0, m.start() - 70):m.start()].split(";")[-1]
        after = comments[m.end():m.end() + 50].split(";")[0]
        after = re.split(r"(?<!Fig)(?<!Figs)\.\s", after)[0]
        clause = before + " " + after
        if not KEYWORD.search(clause) or REVISION.search(clause):
            continue
        for part in re.split(r"\s*(?:,\s*and|,|and|&)\s*", m.group(1)):
            rng = re.split(r"\s*(?:-|" + DASH + r"|to)\s*", part)
            if len(rng) == 2 and rng[0].isdigit() and rng[1].isdigit() and int(rng[1]) - int(rng[0]) < 8:
                out += [str(i) for i in range(int(rng[0]), int(rng[1]) + 1)]
            elif part.strip():
                out.append(re.sub(r"[a-z]$", "", part.strip()))
    return list(dict.fromkeys(out))


# --- figures in the paper -------------------------------------------------------------------------------------
def caption_text(cap):
    """figcaption -> plain text with each MathML formula replaced by $alttext$."""
    cap = BeautifulSoup(str(cap), "html.parser")
    for m in cap.find_all("math"):
        m.replace_with(f"${m['alttext']}$" if m.get("alttext") else "")
    for t, mark in (("sub", "_"), ("sup", "^")):  # N<sub>2</sub>H<sup>+</sup> -> N$_{2}$H$^{+}$
        for x in cap.find_all(t):
            x.replace_with(f"${mark}{{{x.get_text('')}}}$")
    tag = cap.find(class_="ltx_tag_figure")
    label = tag.get_text("", strip=True).rstrip(":").strip() if tag else ""
    if tag:
        tag.decompose()
    text = re.sub(r"\s+", " ", cap.get_text("")).strip().replace("$$", "")  # adjacent formulas merge into one
    return label, text


def section_weight(fig, soup):
    """Location comes from the LaTeXML id ("S4.SS2.F3" = section 4, subsection 2; "A5.F20" = appendix 5):
    more robust than the DOM, which html.parser does not always nest correctly."""
    parts = fig["id"].split(".")
    if parts[0].startswith("A"):
        return 0.2
    weight = 1.0
    for k in range(1, len(parts)):
        sec = soup.find(id=".".join(parts[:k]))
        title = sec.find(class_="ltx_title") if sec else None
        if title and RESULTS.search(title.get_text(" ")):
            weight = 2.0
    return weight


def top_figures(page, k=6, prefer=()):
    soup = BeautifulSoup(page, "html.parser")
    figs = [f for f in soup.find_all("figure", class_="ltx_figure")
            if f.get("id") and not f.find_parent("figure", class_="ltx_figure")]
    if not figs:
        return []
    refs = dict.fromkeys((f["id"] for f in figs), 0)
    for a in soup.find_all("a", href=True):
        h = a["href"]
        if not h.startswith("#"):
            continue
        target = re.sub(r"\.sf\d+$", "", h[1:])
        if target in refs:
            own = a.find_parent("figure", class_="ltx_figure")
            if own is None or own.get("id") != target and not (own.get("id") or "").startswith(target + "."):
                refs[target] += 1
    cands = []
    for order, f in enumerate(figs):
        imgs = [urljoin(BASE, i.get("src") or i.get("data")) for i in f.find_all(["img", "object"])
                if i.get("src") or (i.name == "object" and i.get("data"))]  # vector figures come as <object data=*.svg>
        if not imgs:
            continue
        cap = f.find_all("figcaption")
        label, text = caption_text(cap[-1]) if cap else ("", "")
        num = re.search(r"(\d+)\s*$", label)
        cands.append({"order": order, "score": (1 + refs[f["id"]]) * section_weight(f, soup),
                      "num": num.group(1) if num else None,
                      "fig": {"n": label or f"Figure {order + 1}", "imgs": imgs[:6], "cap": text}})
    named = [c for p in prefer for c in cands if c["num"] == p][:6]
    for c in named:
        c["fig"]["key"] = True
    rest = sorted((c for c in cands if c not in named), key=lambda c: (-c["score"], c["order"]))
    chosen = named + rest[:max(0, k - len(named))]
    return [c["fig"] for c in sorted(chosen, key=lambda c: c["order"])]


def fetch_page(aid, session):
    for attempt in range(3):
        try:
            r = session.get(BASE + aid, timeout=60, headers=UA)
        except requests.RequestException:
            time.sleep(5)
            continue
        if r.status_code == 200 and "ltx_document" in r.text:
            return r.text
        if r.status_code in (429, 500, 502, 503):
            time.sleep(10 * (attempt + 1))
            continue
        return None  # no HTML version (conversion failed or not yet built)
    return None


def add_figures(rows, pause=1.0, log=print):
    """Attach r["figs"] to every row (empty list when arXiv has no HTML version or no usable figures)."""
    s = requests.Session()
    n_ok = n_named = 0
    for r in rows:
        page = fetch_page(r["id"], s)
        try:
            r["figs"] = top_figures(page, prefer=key_figures(r.get("comments"))) if page else []
        except Exception as e:  # a malformed page must not stop the digest
            log(f"figures {r['id']}: {e}")
            r["figs"] = []
        n_ok += bool(r["figs"])
        n_named += any(f.get("key") for f in r["figs"])
        time.sleep(pause)
    log(f"figures: {n_ok}/{len(rows)} papers have figures; {n_named} with author-named key figures")
    return rows


if __name__ == "__main__":
    s = requests.Session()
    for aid in sys.argv[1:]:
        for f in top_figures(fetch_page(aid, s) or ""):
            print(aid, f["n"], len(f["imgs"]), "img |", f["cap"][:100])
