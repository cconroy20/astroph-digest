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
        self._load_votes()

    def _load_votes(self):
        """Votes cast on the site (data/votes.json, written by the page). Upvoted papers join the reference set like
        library papers (text and authors); downvoted papers form a 'less like this' set used in score()."""
        self.En, self.neg_ids, self.n_up = np.zeros((0, self.Ep.shape[1]), np.float32), [], 0
        path = os.path.join(D, "votes.json")
        if not os.path.exists(path):
            return
        by_day = defaultdict(dict)
        for aid, v in json.load(open(path)).get("votes", {}).items():
            if v.get("v") and v.get("day"):
                by_day[v["day"]][aid] = v["v"]
        up_E, up_rows, dn_E = [], [], []
        for day, vs in by_day.items():
            f = os.path.join(D, "daily", day + ".json")
            if not os.path.exists(f):
                continue
            rows, E = json.load(open(f)), np.load(f[:-5] + ".npy").astype(np.float32)
            for k, r in enumerate(rows):
                if vs.get(r["id"], 0) > 0:
                    up_E.append(E[k]); up_rows.append(r)
                elif vs.get(r["id"], 0) < 0:
                    dn_E.append(E[k]); self.neg_ids.append(r["id"])
        w = self.cfg.get("vote_up_weight", 1.0)
        if up_E:
            self.Ep = np.vstack([self.Ep, np.array(up_E)])
            self.wt = np.concatenate([self.wt, np.full(len(up_E), w, np.float32)])
            for r in up_rows:
                self.P.append({"key": "vote:" + r["id"], "arxiv": r["id"], "src": ["vote"], "authors": [],
                               "collections": [], "title": r["title"]})
                self.topical.append([])
                for j, kk in enumerate(keys_arxiv(r["authors"], 15)):
                    self.pos_auth[kk] += w * (1.0 if j < 3 else 0.5)
        if dn_E:
            self.En = np.array(dn_E)
        self.n_up = len(up_E)

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
        own = defaultdict(list)
        for i, p in enumerate(self.P):
            if p["arxiv"]:
                own[p["arxiv"]].append(i)
        for n, r in enumerate(rows):  # a paper never matches its own record (library entry or vote)
            for i in own.get(r["id"], ()):
                S[n, i] = -9
        text = replay.text_scores(S[:, idx], self.wt[idx], cfg["method"], cfg.get("tau", 0.05), cfg.get("k", 5))
        if len(self.En) and cfg["method"] == "kde":
            # "less like this": text = log(P / sum w), so P is recoverable; D is the same kernel sum over downvotes.
            # The penalty log(1 + D/P) is ~0 when a paper resembles your positives far more than your downvotes.
            Sn = E @ self.En.T
            neg = {aid: j for j, aid in enumerate(self.neg_ids)}
            for n, r in enumerate(rows):
                if r["id"] in neg:
                    Sn[n, neg[r["id"]]] = -9
            tau = cfg.get("tau", 0.05)
            Pk = np.exp(text) * self.wt[idx].sum()
            Dk = np.exp((Sn - 1) / tau).sum(1)
            text = text - cfg.get("vote_down_gamma", 1.0) * np.log1p(Dk / np.maximum(Pk, 1e-300))
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
