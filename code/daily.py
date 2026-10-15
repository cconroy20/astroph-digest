"""Weekday job: fetch today's astro-ph listing, build the digest, archive the day for calibration.

Writes <site>/<date>.html, refreshes <site>/index.html (latest) and <site>/archive.html, and saves the day's
rows + text vectors to data/daily/ (the quarterly retrain calibrates against them).
Skips quietly when today's listing is already done (weekends, holidays, a second run).

  daily.py                  local run: site = digests/, opens the page in the browser
  daily.py --site docs      GitHub Actions run: no browser
  daily.py --force          rebuild even if today's digest exists
"""
import html, json, os, re, shutil, subprocess, sys, time, traceback
from datetime import datetime
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ARCH = os.path.join(ROOT, "data", "daily")
LOCAL = not os.environ.get("CI")


def log(msg):
    print(f"{datetime.now():%Y-%m-%d %H:%M:%S} {msg}", flush=True)


def notify(msg):
    if LOCAL:
        subprocess.run(["osascript", "-e", f'display notification "{msg}" with title "arXiv Digest"'], check=False)


def write_archive(site):
    from digest import CSS, FONTS, ICONS
    days = sorted((f[:-5] for f in os.listdir(site) if re.fullmatch(r"\d{4}-\d{2}-\d{2}\.html", f)), reverse=True)
    items = "".join(f'<li><a href="{d}.html">{datetime.strptime(d, "%Y-%m-%d"):%a %-d %b %Y}</a></li>' for d in days)
    page = (f"<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
            f"<title>arXiv Digest archive</title>{ICONS}{FONTS}<style>{CSS}</style></head><body><div class='wrap'>"
            f"<header class='mast'><div class='name'>arXiv Digest</div><div class='info'><span class='when'>Archive</span>"
            f"<a class='arch' href='index.html'>Latest digest</a></div></header>"
            f"<main><ul class='rest'>{items}</ul></main></div></body></html>")
    open(os.path.join(site, "archive.html"), "w").write(page)


def publish(site, day, label, page, items):
    """Write one day's page and its catch-up data file (days/<date>.json), then refresh index/archive."""
    os.makedirs(os.path.join(site, "days"), exist_ok=True)
    open(os.path.join(site, day + ".html"), "w").write(page)
    json.dump({"date": day, "label": label, "papers": items}, open(os.path.join(site, "days", day + ".json"), "w"))
    refresh_index(site)


def refresh_index(site):
    days = sorted(f[:-5] for f in os.listdir(os.path.join(site, "days")) if re.fullmatch(r"\d{4}-\d{2}-\d{2}\.json", f))
    json.dump(days, open(os.path.join(site, "days", "index.json"), "w"))
    latest = open(os.path.join(site, days[-1] + ".html")).read()
    # index.html is the latest day, marked so its script offers the catch-up view
    open(os.path.join(site, "index.html"), "w").write(latest.replace("<body data-date=", "<body data-index='1' data-date=", 1))
    write_archive(site)


def main():
    site = os.path.join(ROOT, sys.argv[sys.argv.index("--site") + 1]) if "--site" in sys.argv else os.path.join(ROOT, "digests")
    from fetch_listing import fetch
    for attempt in range(4):  # arXiv can be briefly unreachable (e.g. right after a wake from sleep)
        try:
            label, rows = fetch()
            break
        except Exception as e:
            log(f"fetch failed ({e}); retry {attempt + 1}/3")
            time.sleep(120)
    else:
        notify("Could not reach arXiv; run code/daily.py --force to retry.")
        sys.exit(1)
    day = datetime.strptime(label, "%A, %d %B %Y").strftime("%Y-%m-%d")
    path = os.path.join(site, day + ".html")
    if os.path.exists(path) and "--force" not in sys.argv:
        log(f"{day}: already done, nothing new")
        return
    from digest import build
    from scorer import Scorer
    cfg = json.load(open(os.path.join(ROOT, "models", "config.json")))
    sc = Scorer(cfg)
    page, order, res, E, items = build(label, rows, sc)
    publish(site, day, label, page, items)
    os.makedirs(ARCH, exist_ok=True)
    json.dump(rows, open(os.path.join(ARCH, day + ".json"), "w"))
    np.save(os.path.join(ARCH, day + ".npy"), E.astype(np.float16))
    log(f"{day}: {len(rows)} papers -> {path}")
    if LOCAL and "--site" not in sys.argv:
        subprocess.run(["open", path], check=False)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        log(traceback.format_exc())
        notify("The digest failed to build; see the log.")
        sys.exit(1)
