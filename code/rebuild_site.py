"""Re-render every archived day in docs/ with the current page design (after a layout change).

Uses the saved listing and text vectors in data/daily/, so nothing is re-fetched or re-embedded.
  rebuild_site.py [--site docs]
"""
import glob, json, os, shutil, sys
from datetime import datetime
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
from daily import ROOT, ARCH, write_archive
from digest import build
from scorer import Scorer

site = os.path.join(ROOT, sys.argv[sys.argv.index("--site") + 1]) if "--site" in sys.argv else os.path.join(ROOT, "docs")
sc = Scorer(json.load(open(os.path.join(ROOT, "models", "config.json"))))
days = sorted(os.path.basename(f)[:-5] for f in glob.glob(os.path.join(ARCH, "*.json")))
for day in days:
    rows = json.load(open(os.path.join(ARCH, day + ".json")))
    E = np.load(os.path.join(ARCH, day + ".npy")).astype(np.float32)
    label = datetime.strptime(day, "%Y-%m-%d").strftime("%A, %-d %B %Y")
    page = build(label, rows, sc, E=E)[0]
    open(os.path.join(site, day + ".html"), "w").write(page)
    print("rebuilt", day)
shutil.copyfile(os.path.join(site, days[-1] + ".html"), os.path.join(site, "index.html"))
write_archive(site)
