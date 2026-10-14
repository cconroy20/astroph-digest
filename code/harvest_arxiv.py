"""Harvest astro-ph metadata (arXivRaw) from arXiv OAI-PMH into data/oai/*.xml pages.

Resumable: the last resumptionToken is kept in data/oai/_token. Parse with parse_arxiv.py.
Incremental runs (a later FROM_DATE) append pages; parse_arxiv.py reads them in order, so newer records win.
Usage: harvest_arxiv.py FROM_DATE [UNTIL_DATE]
"""
import os, re, sys, time, requests

BASE = "https://oaipmh.arxiv.org/oai"
D = os.path.join(os.path.dirname(__file__), "..", "data", "oai")
os.makedirs(D, exist_ok=True)
tokfile = os.path.join(D, "_token")

if os.path.exists(tokfile) and open(tokfile).read().strip():
    params = {"verb": "ListRecords", "resumptionToken": open(tokfile).read().strip()}
    page = len([f for f in os.listdir(D) if f.endswith(".xml")])
else:
    params = {"verb": "ListRecords", "metadataPrefix": "arXivRaw", "set": "physics:astro-ph", "from": sys.argv[1]}
    if len(sys.argv) > 2:
        params["until"] = sys.argv[2]
    page = len([f for f in os.listdir(D) if f.endswith(".xml")])  # later pages override earlier ones when parsed

while True:
    for attempt in range(10):
        try:
            r = requests.get(BASE, params=params, timeout=180)
        except requests.RequestException as e:
            print("net error", e, flush=True); time.sleep(30); continue
        if r.status_code == 200:
            break
        wait = int(r.headers.get("Retry-After", 30))
        print("status", r.status_code, "wait", wait, flush=True)
        time.sleep(wait)
    else:
        sys.exit("gave up")
    txt = r.text
    open(os.path.join(D, f"p{page:05d}.xml"), "w").write(txt)
    m = re.search(r"<resumptionToken[^>]*>([^<]*)</resumptionToken>", txt)
    tok = m.group(1).strip() if m else ""
    open(tokfile, "w").write(tok)
    n = txt.count("<record>")
    cs = re.search(r'completeListSize="(\d+)"', txt)
    print(f"page {page}: {n} records; total {cs.group(1) if cs else '?'}", flush=True)
    page += 1
    if not tok:
        print("DONE", flush=True)
        break
    params = {"verb": "ListRecords", "resumptionToken": tok}
    time.sleep(4)
