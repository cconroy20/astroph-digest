"""Replay test: rank each held-out paper among the full listing of the day it was announced.

For a test paper on mailing day d, the model only sees positives known before d
(t_eff < d), never the paper itself. Reports recall@k = fraction of test papers that
land in the top k of their day; validation = 2023-24, held out = 2025-26.
"""
import json, os, sys
from collections import Counter, defaultdict
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
from authors import keys_ads, keys_arxiv

ROOT = os.path.join(os.path.dirname(__file__), "..")
D = os.path.join(ROOT, "data")


class Data:
    def __init__(self, model):
        self.P = json.load(open(os.path.join(D, "positives.json")))
        self.B = json.load(open(os.path.join(D, "bakeoff.json")))
        self.T = json.load(open(os.path.join(D, "tests.json")))
        if model == "tfidf":
            from sklearn.feature_extraction.text import TfidfVectorizer
            txt = lambda r: r["title"] + ". " + r.get("abstract", "")
            B0 = json.load(open(os.path.join(D, "bakeoff.json")))
            vec = TfidfVectorizer(sublinear_tf=True, min_df=2, max_df=0.3, stop_words="english", ngram_range=(1, 2))
            vec.fit([txt(r) for r in B0 if r["set"] == "bg"] + [txt(r) for r in self.P])
            self.Ep, self.Eb = vec.transform([txt(r) for r in self.P]), vec.transform([txt(r) for r in B0])
        else:
            self.Ep = np.load(os.path.join(ROOT, "models", model, "positives.npy")).astype(np.float32)
            self.Eb = np.load(os.path.join(ROOT, "models", model, "bakeoff.npy")).astype(np.float32)
        A = {a["id"]: a for a in json.load(open(os.path.join(D, "astroph.json")))}
        # effective date a positive became knowable: earlier of pubdate and arXiv announcement
        self.t_eff = []
        for p in self.P:
            t = p["t_known"]
            if p["arxiv"] in A and ("lib" in p["src"] or "own" in p["src"]):
                t = min(t, A[p["arxiv"]]["mailing"])
            self.t_eff.append(t)
        self.t_eff = np.array(self.t_eff)
        self.pos_by_arxiv = defaultdict(list)
        for i, p in enumerate(self.P):
            if p["arxiv"]:
                self.pos_by_arxiv[p["arxiv"]].append(i)
        self.days = defaultdict(list)
        for i, b in enumerate(self.B):
            if b["set"] == "day":
                self.days[b["mailing"]].append(i)
        self.bg = np.array([i for i, b in enumerate(self.B) if b["set"] == "bg"])
        self.bid = {b["id"]: i for i, b in enumerate(self.B) if b["set"] == "day"}
        # authors
        self.pkeys = []
        for p in self.P:
            if "own" in p["src"] and p.get("n_auth", 0) > 30 and p.get("own_pos", 99) > 3:
                self.pkeys.append([])  # big-collaboration papers: coauthor list is not a signal
            else:
                self.pkeys.append(keys_ads(p["authors"], 15))
        self.bkeys = [keys_arxiv(b["authors"], 15) for b in self.B]
        self.field = Counter()
        for a in A.values():
            self.field.update(set(keys_arxiv(a["authors"], 15)))
        self.nfield_papers = len(A)


def weights(d, mask, w):
    """per-positive weights by source"""
    out = np.zeros(len(d.P), dtype=np.float32)
    for i, p in enumerate(d.P):
        if not mask[i]:
            continue
        s = p["src"]
        v = 0.0
        if "lib" in s: v = max(v, w.get("lib", 1.0))
        if "own" in s: v = max(v, w.get("own", 1.0))
        if "cited" in s: v = max(v, w.get("cited", 0.5) * min(p.get("n_cited", 1), w.get("ncap", 1)))
        if "__Reviews" in p["collections"]: v *= w.get("review", 1.0)
        out[i] = v
    return out


def text_scores(S, wt, method, tau=0.05, k=5, Sbg=None):
    """S: candidates x positives similarity (masked entries = -9). wt: weights of the same positives."""
    if method == "max":
        return S.max(1)
    if method == "topk":
        part = np.sort(S, 1)[:, -k:]
        return part.mean(1)
    if method in ("kde", "kderatio"):
        x = np.log((wt[None, :] * np.exp((S - 1) / tau)).sum(1) / wt.sum() + 1e-30)
        if method == "kderatio":
            x -= np.log(np.exp((Sbg - 1) / tau).mean(1) + 1e-30)
        return x
    raise ValueError(method)


def author_scores(d, cand, mask, wt, beta_field=1.0):
    pos = Counter()
    for i in np.nonzero(mask)[0]:
        for j, kk in enumerate(d.pkeys[i]):
            pos[kk] += wt[i] * (1.0 if j < 3 else 0.5)
    out = np.zeros(len(cand))
    for n, c in enumerate(cand):
        s = 0.0
        for j, kk in enumerate(d.bkeys[c]):
            if kk in pos:
                lift = pos[kk] / (1.0 + beta_field * d.field[kk] / 50.0)
                s += lift * (1.0 if j < 3 else 0.5)
        out[n] = np.log1p(s)
    return out


_clf_cache = {}


def logreg_scores(d, cand, day, w, C=1.0):
    """Logistic regression positives-vs-field, retrained per quarter on positives known before the quarter."""
    from sklearn.linear_model import LogisticRegression
    q = day[:4] + "Q" + str((int(day[5:7]) - 1) // 3)
    key = (id(d), q, C, json.dumps(w, sort_keys=True))
    if key not in _clf_cache:
        qstart = f"{day[:4]}-{3 * ((int(day[5:7]) - 1) // 3) + 1:02d}-01"
        mask = d.t_eff < qstart
        wt = weights(d, mask, w)
        idx = np.nonzero(wt > 0)[0]
        X = np.vstack([d.Ep[idx], d.Eb[d.bg]])
        y = np.r_[np.ones(len(idx)), np.zeros(len(d.bg))]
        sw = np.r_[wt[idx] / wt[idx].mean(), np.full(len(d.bg), len(idx) / len(d.bg))]
        _clf_cache[key] = LogisticRegression(C=C, max_iter=2000).fit(X, y, sample_weight=sw)
    return _clf_cache[key].decision_function(d.Eb[cand])


def run(d, method="topk", k=5, tau=0.05, w=None, alpha_auth=0.0, tests=None, beta_field=1.0, return_scores=False,
        C=1.0, mix=None):
    w = w or {}
    tests = tests if tests is not None else d.T
    by_day = defaultdict(list)
    for t in tests:
        if t["arxiv"] in d.bid:
            by_day[t["mailing"]].append(t)
    ranks = []
    for day, ts in sorted(by_day.items()):
        cand = d.days[day]
        mask = d.t_eff < day
        for c in cand:  # never let a candidate match its own positive record
            for i in d.pos_by_arxiv.get(d.B[c]["id"], []):
                mask[i] = False
        wt = weights(d, mask, w)
        idx = np.nonzero(wt > 0)[0]
        if method == "logreg":
            sc = logreg_scores(d, cand, day, w, C)
            if alpha_auth:
                z = (sc - sc.mean()) / (sc.std() + 1e-9)
                sc = z + alpha_auth * author_scores(d, cand, mask, wt, beta_field)
            order = np.argsort(-sc)
            rank = np.empty(len(cand), int)
            rank[order] = np.arange(1, len(cand) + 1)
            pos_in_day = {d.B[c]["id"]: r for c, r in zip(cand, rank)}
            for t in ts:
                ranks.append({**t, "rank": int(pos_in_day[t["arxiv"]]), "n": len(cand)})
            continue
        S = d.Eb[cand] @ d.Ep[idx].T
        Sbg = d.Eb[cand] @ d.Eb[d.bg].T if method == "kderatio" else None
        if hasattr(S, "toarray"):
            S = S.toarray()
            Sbg = Sbg.toarray() if Sbg is not None else None
        sc = text_scores(S, wt[idx], method, tau, k, Sbg)
        if mix:  # blend kNN with the classifier (z-scored within the day)
            zz = lambda v: (v - v.mean()) / (v.std() + 1e-9)
            sc = zz(sc) + mix * zz(logreg_scores(d, cand, day, w, C))
        if alpha_auth:
            z = (sc - sc.mean()) / (sc.std() + 1e-9)
            sc = z + alpha_auth * author_scores(d, cand, mask, wt, beta_field)
        order = np.argsort(-sc)
        rank = np.empty(len(cand), int)
        rank[order] = np.arange(1, len(cand) + 1)
        pos_in_day = {d.B[c]["id"]: r for c, r in zip(cand, rank)}
        for t in ts:
            ranks.append({**t, "rank": int(pos_in_day[t["arxiv"]]), "n": len(cand)})
    return ranks


def summarize(ranks, label=""):
    out = {}
    for name, sel in [("val", lambda r: r["mailing"] < "2025"), ("hold", lambda r: r["mailing"] >= "2025")]:
        rr = [r for r in ranks if sel(r) and not r["own"]]
        if not rr:
            continue
        rk = np.array([r["rank"] for r in rr])
        n = np.array([r["n"] for r in rr])
        out[name] = {"N": len(rr), "r@5": np.mean(rk <= 5), "r@10": np.mean(rk <= 10), "r@20": np.mean(rk <= 20),
                     "medrank": float(np.median(rk)), "medpct": float(np.median(rk / n))}
    s = "  ".join(f"{k}: N={v['N']} r@5={v['r@5']:.2f} r@10={v['r@10']:.2f} r@20={v['r@20']:.2f} med={v['medrank']:.0f}"
                  for k, v in out.items())
    print(f"{label:40s} {s}", flush=True)
    return out
