"""Score a list of arXiv rows against Charlie's positives; explain each score.

Config (models/config.json) holds the choices made in the replay test.
"""
import json, os, sys
from collections import Counter, defaultdict
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
from authors import keys_ads, keys_arxiv
import replay

ROOT = os.path.join(os.path.dirname(__file__), "..")
D = os.path.join(ROOT, "data")
NONTOPIC = {"__Reviews", "__My Papers"}


def leaf(c):
    parts = c.split("/")
    return parts[-1] if len(parts) == 1 else f"{parts[-1]} ({parts[0]})"


class Scorer:
    def __init__(self, cfg, encoder=None):
        self.cfg = cfg
        self.P = json.load(open(os.path.join(D, "positives.json")))
        self.Ep = np.load(os.path.join(ROOT, "models", cfg["model"], "positives.npy")).astype(np.float32)
        self.wt = replay.weights(self, np.ones(len(self.P), bool), cfg.get("w", {}))
        self.encoder = encoder
        # author affinity counts over all positives
        self.pos_auth = Counter()
        for i, p in enumerate(self.P):
            if "own" in p["src"] and p.get("n_auth", 0) > 30 and p.get("own_pos", 99) > 3:
                continue
            for j, kk in enumerate(keys_ads(p["authors"], 15)):
                self.pos_auth[kk] += self.wt[i] * (1.0 if j < 3 else 0.5)
        self.field = Counter(json.load(open(os.path.join(D, "field_authors.json")))["counts"])
        self.lib_arxiv = {p["arxiv"] for p in self.P if p["arxiv"] and "lib" in p["src"]}
        self.topical = [[c for c in p["collections"] if c.split("/")[0] not in NONTOPIC] for p in self.P]
        self.ref = None
        rp = os.path.join(ROOT, "models", cfg["model"], "ref_scores.npy")
        if os.path.exists(rp):
            self.ref = np.sort(np.load(rp))

    def embed(self, rows):
        if self.encoder is None:
            import embed
            self.encoder = embed.load(self.cfg["model"])
        E = self.encoder([r["title"] for r in rows], [r.get("abstract", "") for r in rows])
        return (E / np.linalg.norm(E, axis=1, keepdims=True)).astype(np.float32)

    def author_terms(self, authors):
        hits, s = [], 0.0
        for j, kk in enumerate(keys_arxiv(authors, 15)):
            if kk in self.pos_auth:
                lift = self.pos_auth[kk] / (1.0 + self.cfg.get("beta_field", 1.0) * self.field[kk] / 50.0)
                s += lift * (1.0 if j < 3 else 0.5)
                if lift > 1.0:
                    hits.append((j, kk, lift))
        return np.log1p(s), hits

    def score(self, rows, E=None, exclude_ids=()):
        cfg = self.cfg
        E = self.embed(rows) if E is None else E
        S = E @ self.Ep.T
        idx = np.nonzero(self.wt > 0)[0]
        own = {p["arxiv"]: i for i, p in enumerate(self.P) if p["arxiv"]}
        for n, r in enumerate(rows):  # a paper never matches its own record
            if r["id"] in own:
                S[n, own[r["id"]]] = -9
        text = replay.text_scores(S[:, idx], self.wt[idx], cfg["method"], cfg.get("tau", 0.05), cfg.get("k", 5))
        out = []
        for n, r in enumerate(rows):
            a, hits = self.author_terms(r["authors"])
            out.append({"text": float(text[n]), "auth": float(a), "hits": hits})
        return out, S

    def explain(self, S_row, n_nb=3, k=10, p=8):
        """nearest library/own papers + collection vote among the k nearest library papers
        (leave-one-out on the library: 76% leaf-level accuracy for k=10, p=8)"""
        order = np.argsort(-S_row)
        nbs = []
        for i in order[:60]:
            if "lib" in self.P[i]["src"] or "own" in self.P[i]["src"]:
                nbs.append((i, float(S_row[i])))
                if len(nbs) == n_nb:
                    break
        vote, n = defaultdict(float), 0
        for i in order:
            if self.topical[i]:
                for c in self.topical[i]:
                    vote[c] += max(S_row[i], 0) ** p / len(self.topical[i])
                n += 1
                if n == k:
                    break
        best_lib = max((S_row[i] for i in order[:200] if self.topical[i]), default=0)
        if not vote or best_lib < self.cfg.get("other_sim", 0):
            return nbs, "Other"
        return nbs, max(vote, key=vote.get)
