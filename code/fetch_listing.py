"""Fetch the current astro-ph 'New submissions' listing (no cross-lists, no replacements).

Returns (listing_date_str, rows) where rows look like data/astroph.json rows.
"""
import html, re, requests

URL = "https://arxiv.org/list/astro-ph/new?skip=0&show=2000"


def strip(s):
    s = re.sub(r"<span class='descriptor'>[^<]*</span>", "", s)
    s = re.sub(r"<[^>]+>", "", s)
    return html.unescape(re.sub(r"\s+", " ", s)).strip()


def parse(page):
    m = re.search(r"Showing new listings for ([^<]+)</h3>", page)
    date = m.group(1).strip() if m else "?"
    i = page.index("New submissions")
    j = page.find("Cross submissions", i)
    if j < 0:
        j = page.find("Replacement submissions", i)
    sec = page[i:j if j > 0 else None]
    rows = []
    for dt, dd in re.findall(r"<dt>(.*?)</dt>\s*<dd>(.*?)</dd>", sec, re.S):
        aid = re.search(r'id="(\d{4}\.\d{4,5})"', dt).group(1)
        title = strip(re.search(r"<div class='list-title[^']*'>(.*?)</div>", dd, re.S).group(1))
        authors = ", ".join(strip(a) for a in re.findall(r"<a [^>]*>(.*?)</a>", re.search(
            r"<div class='list-authors'>(.*?)</div>", dd, re.S).group(1)))
        cm = re.search(r"<div class='list-comments[^']*'>(.*?)</div>", dd, re.S)
        subj = strip(re.search(r"<div class='list-subjects'>(.*?)</div>", dd, re.S).group(1))
        cats = re.findall(r"\(([a-z\-]+(?:\.[A-Z]{2})?)\)", subj)
        ab = re.search(r"<p class='mathjax'>(.*?)</p>", dd, re.S)
        rows.append({"id": aid, "title": title, "authors": authors, "abstract": strip(ab.group(1)) if ab else "",
                     "comments": strip(cm.group(1)) if cm else "", "cats": cats,
                     "primary": cats[0] if cats else ""})
    return date, rows


def fetch():
    r = requests.get(URL, timeout=120, headers={"User-Agent": "arxivsort (personal digest)"})
    r.raise_for_status()
    return parse(r.text)


if __name__ == "__main__":
    date, rows = fetch()
    print(date, len(rows), "new submissions")
    for r in rows[:3]:
        print(r["id"], r["primary"], "|", r["title"][:70], "|", r["authors"][:60])
