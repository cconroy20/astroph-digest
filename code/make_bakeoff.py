"""Pick replay-test papers and build data/bakeoff.json = their days' full listings + 12k field sample."""
import json, os, random
D = os.path.join(os.path.dirname(__file__), "..", "data")
A = json.load(open(os.path.join(D, "astroph.json")))
P = json.load(open(os.path.join(D, "positives.json")))
byid = {a["id"]: a for a in A}
own = lambda p: any(x.lower().startswith("conroy, c") for x in p["authors"])
tests = []
for p in P:
    a = byid.get(p["arxiv"])
    if a and a["mailing"] >= "2023-01-01" and ("lib" in p["src"] or "cited" in p["src"]):
        tests.append({"pos_key": p["key"], "arxiv": p["arxiv"], "mailing": a["mailing"], "own": own(p),
                      "kind": "lib" if "lib" in p["src"] else "cited"})
days = {t["mailing"] for t in tests}
rows = [a for a in A if a["mailing"] in days]
random.seed(1)
pool = [a for a in A if a["mailing"] >= "2022-01-01" and a["mailing"] not in days]
bg = random.sample(pool, 12000)
for a in rows: a["set"] = "day"
for a in bg: a["set"] = "bg"
json.dump(rows + bg, open(os.path.join(D, "bakeoff.json"), "w"))
json.dump(tests, open(os.path.join(D, "tests.json"), "w"))
print(len(tests), "tests (", sum(t["own"] for t in tests), "own-authored );", len(days), "days;", len(rows), "day rows +", len(bg), "bg")
