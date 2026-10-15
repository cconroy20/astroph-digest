"""Pick the top three figures of each paper from arXiv's HTML version.

Score of a figure = (1 + number of times the paper's own text links to it) x section weight, where the weight is
2 for a figure inside any section or subsection titled "Results"/"Findings", 0.2 inside an appendix, 1 otherwise.
Ties go to the earlier figure. Figures without an image (e.g. inline TikZ) are skipped.

Each figure is stored as {"n": "Figure 3", "imgs": [absolute image URLs], "cap": caption with math as $...$}.
"""
import html, re, sys, time
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup

BASE = "https://arxiv.org/html/"
UA = {"User-Agent": "arxivsort (personal digest)"}
RESULTS = re.compile(r"\b(results?|findings?)\b", re.I)


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


def top_figures(page, k=3):
    soup = BeautifulSoup(page, "html.parser")
    figs = [f for f in soup.find_all("figure", class_="ltx_figure")
            if f.get("id") and not f.find_parent("figure", class_="ltx_figure")]
    if not figs:
        return []
    ids = {f["id"] for f in figs}
    refs = dict.fromkeys(ids, 0)
    for a in soup.find_all("a", href=True):
        h = a["href"]
        if not h.startswith("#"):
            continue
        target = re.sub(r"\.sf\d+$", "", h[1:])
        if target in refs:
            own = a.find_parent("figure", class_="ltx_figure")
            if own is None or own.get("id") != target and not (own.get("id") or "").startswith(target + "."):
                refs[target] += 1
    scored = []
    for order, f in enumerate(figs):
        imgs = [urljoin(BASE, i.get("src") or i.get("data")) for i in f.find_all(["img", "object"])
                if i.get("src") or (i.name == "object" and i.get("data"))]  # vector figures come as <object data=*.svg>
        if not imgs:
            continue
        cap = f.find_all("figcaption")
        label, text = caption_text(cap[-1]) if cap else ("", "")
        score = (1 + refs[f["id"]]) * section_weight(f, soup)
        scored.append((-score, order, {"n": label or f"Figure {order + 1}", "imgs": imgs[:6], "cap": text}))
    scored.sort(key=lambda x: (x[0], x[1]))
    return [s[2] for s in scored[:k]]


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
    n_ok = 0
    for i, r in enumerate(rows):
        page = fetch_page(r["id"], s)
        try:
            r["figs"] = top_figures(page) if page else []
        except Exception as e:  # a malformed page must not stop the digest
            log(f"figures {r['id']}: {e}")
            r["figs"] = []
        n_ok += bool(r["figs"])
        time.sleep(pause)
    log(f"figures: {n_ok}/{len(rows)} papers have figures")
    return rows


if __name__ == "__main__":
    s = requests.Session()
    for aid in sys.argv[1:]:
        for f in top_figures(fetch_page(aid, s) or ""):
            print(aid, f["n"], len(f["imgs"]), "img |", f["cap"][:100])
