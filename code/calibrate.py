"""Field calibration: put scores on an absolute scale and set the selection bar.

Saves models/<model>/calib.json:
  mu, sd   -- mean/std of the text score over a field sample
  thresh   -- cut on  z_text + alpha_auth * author  that passes `per_day` papers on an average recent day
The field sample is the archived daily listings (data/daily/, written by daily.py) from the last 180 days, plus the
original random astro-ph sample (data/bakeoff.json) when present. The bar comes from the archived days once at
least 30 exist; until then from the original sample's 2025-26 papers.
"""
import glob, json, os, sys
from datetime import date, timedelta
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
from scorer import Scorer

ROOT = os.path.join(os.path.dirname(__file__), "..")
cfg = json.load(open(os.path.join(ROOT, "models", "config.json")))
sc = Scorer(cfg)
per_day = cfg.get("per_day", 10)
alpha = cfg.get("alpha_auth", 0.0)


def scores(rows, E):
    res, _ = sc.score(rows, E=E.astype(np.float32))
    return np.array([r["text"] for r in res]), np.array([r["auth"] for r in res])


# archived daily listings, last 180 days
cut = (date.today() - timedelta(days=180)).isoformat()
day_rows, day_E, day_id = [], [], []
for f in sorted(glob.glob(os.path.join(ROOT, "data", "daily", "*.json"))):
    d = os.path.basename(f)[:-5]
    if d >= cut:
        r = json.load(open(f))
        day_rows += r
        day_E.append(np.load(f[:-5] + ".npy"))
        day_id += [d] * len(r)
n_days = len(set(day_id))

texts, auths, recent = [], [], []
if day_rows:
    t, a = scores(day_rows, np.vstack(day_E))
    texts.append(t); auths.append(a); recent.append(np.ones(len(t), bool))
bpath = os.path.join(ROOT, "data", "bakeoff.json")
if os.path.exists(bpath):
    B = json.load(open(bpath))
    E = np.load(os.path.join(ROOT, "models", cfg["model"], "bakeoff.npy"))
    bg = [i for i, b in enumerate(B) if b["set"] == "bg"]
    t, a = scores([B[i] for i in bg], E[bg])
    texts.append(t); auths.append(a)
    recent.append(np.array([B[i]["mailing"] >= "2025-07-01" for i in bg]) if n_days < 30 else np.zeros(len(bg), bool))
text, auth, recent = np.concatenate(texts), np.concatenate(auths), np.concatenate(recent)

mu, sd = float(text.mean()), float(text.std())
comb = (text - mu) / sd + alpha * auth
if n_days >= 30:
    day_size = len(day_rows) / n_days
    source = f"{n_days} archived days"
else:  # average recent day size from the full astro-ph record
    A = json.load(open(os.path.join(ROOT, "data", "astroph.json")))
    days = {}
    for x in A:
        if x["mailing"] >= cut:
            days[x["mailing"]] = days.get(x["mailing"], 0) + 1
    day_size = float(np.mean(list(days.values())))
    source = "original field sample"
thresh = float(np.quantile(comb[recent], 1 - per_day / day_size))
json.dump({"mu": mu, "sd": sd, "thresh": thresh, "per_day": per_day, "day_size": day_size, "source": source,
           "date": date.today().isoformat()},
          open(os.path.join(ROOT, "models", cfg["model"], "calib.json"), "w"), indent=1)
np.save(os.path.join(ROOT, "models", cfg["model"], "ref_scores.npy"), text)
print(f"field sample {len(text)} papers; mu={mu:.2f} sd={sd:.2f}; bar {thresh:.2f} for {per_day}/day "
      f"(day size {day_size:.0f}; from {source})")
if n_days:
    ids = np.array(day_id)
    cnt = np.array([(comb[:len(day_rows)][ids == d] >= thresh).sum() for d in sorted(set(day_id))])
    print(f"archived days: count above bar mean {cnt.mean():.1f}, 10-90% {np.percentile(cnt, 10):.0f}-{np.percentile(cnt, 90):.0f}")
