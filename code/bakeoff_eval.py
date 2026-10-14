"""Grid of scoring rules for one model on the replay test (selection on 'val' = 2023-24 only)."""
import sys, replay
m = sys.argv[1]
d = replay.Data(m)
S = lambda lab, **kw: replay.summarize(replay.run(d, **kw), f"{m} {lab}")
S("max", method="max")
for k in (3, 5, 10, 20, 40):
    S(f"topk k={k}", method="topk", k=k)
for tau in (0.02, 0.05, 0.1):
    S(f"kde tau={tau}", method="kde", tau=tau)
S("kderatio tau=0.05", method="kderatio", tau=0.05)
S("logreg C=1", method="logreg", C=1.0)
S("logreg C=0.1", method="logreg", C=0.1)
