# Astro-Ph Digest

Each weekday morning this repository's GitHub Actions job reads the day's new astro-ph submissions
(arxiv.org/list/astro-ph/new, new submissions only), ranks them against Charlie Conroy's reading
interests, and publishes the result with GitHub Pages: the papers above a fixed relevance bar
(about 10 on an average day) followed by the rest of the listing, in score order.

## How papers are ranked
- **Reference set** (`data/positives.json`, ~5,400 papers): the Zotero library and Charlie's own papers
  (weight 1) plus papers cited in his 2020+ papers as one of the first three authors (weight 0.25).
- **Topic score**: title + abstract embedded with NASA's INDUS model (`nasa-impact/nasa-smd-ibm-st-v2`);
  similarity to the reference set combined so the nearest few papers dominate (kernel width 0.02),
  then standardized against a random astro-ph sample.
- **Author score**: how often each author appears in the reference set, discounted by how often the
  name appears across astro-ph (`data/field_authors.json`).
- **Selection**: topic score + 0.7 x author score above the bar in `models/indus/calib.json`,
  set so an average recent day passes 10 (never fewer than 5 or more than 20).

The settings were chosen by replaying 2023-26: for each paper Charlie saved or cited, where would it
have ranked on the day it appeared? 89% of 2023-24 papers and 75% of held-out 2025-26 papers land in
their day's top 10.

## Pieces
- `code/daily.py` -- the weekday job (fetch, score, write `docs/`, archive the day in `data/daily/`).
- `code/retrain.py` -- the quarterly update, run on the Mac because it reads the local Zotero database:
  refreshes the library, publications and citations (ADS), the astro-ph record (arXiv OAI), re-embeds
  the reference set, recalibrates the bar, and pushes the model files.
- `code/replay.py`, `code/bakeoff_eval.py` -- the replay test used to choose the model and settings.
