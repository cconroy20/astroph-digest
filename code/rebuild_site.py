"""Re-render every archived day in docs/ with the current page design (after a layout change).

Uses the saved listing and text vectors in data/daily/, so nothing is re-fetched or re-embedded.
  rebuild_site.py [--site docs] [--refetch-figures]
"""
import glob, json, os, sys
from datetime import datetime
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
from daily import ROOT, ARCH, publish
from digest import build
from scorer import Scorer

site = os.path.join(ROOT, sys.argv[sys.argv.index("--site") + 1]) if "--site" in sys.argv else os.path.join(ROOT, "docs")
sc = Scorer(json.load(open(os.path.join(ROOT, "models", "config.json"))))
days = sorted(os.path.basename(f)[:-5] for f in glob.glob(os.path.join(ARCH, "*.json")))
for day in days:
    rows = json.load(open(os.path.join(ARCH, day + ".json")))
    if "--refetch-figures" in sys.argv or any("figs" not in r for r in rows):  # new day, or figure picking changed
        from figures import add_figures
        add_figures(rows)
        json.dump(rows, open(os.path.join(ARCH, day + ".json"), "w"))
    E = np.load(os.path.join(ARCH, day + ".npy")).astype(np.float32)
    label = datetime.strptime(day, "%Y-%m-%d").strftime("%A, %-d %B %Y")
    page, order, res, E, items = build(label, rows, sc, E=E)
    publish(site, day, label, page, items)
    print("rebuilt", day)
