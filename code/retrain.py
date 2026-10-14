"""Quarterly update, run on Charlie's Mac (needs the local Zotero database).

  1. git pull (brings the daily archives written by the GitHub job)
  2. Zotero -> ADS records for the library; own papers + citations from ADS
  3. astro-ph metadata since the last harvest (arXiv OAI) -> field author counts
  4. rebuild the reference set, embed it (INDUS), recalibrate the selection bar
  5. commit + push the model files the daily job reads

  retrain.py            full run
  retrain.py --no-push  everything but the push
"""
import json, os, subprocess, sys
from datetime import date, datetime, timedelta

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PY = os.path.join(ROOT, ".venv", "bin", "python")
SHIPPED = ["data/positives.json", "data/field_authors.json", "models/indus/positives.npy", "models/indus/calib.json"]


def log(msg):
    print(f"{datetime.now():%Y-%m-%d %H:%M:%S} {msg}", flush=True)


def run(*cmd, cwd=ROOT):
    log("$ " + " ".join(cmd))
    subprocess.run(cmd, cwd=cwd, check=True)


def notify(msg):
    subprocess.run(["osascript", "-e", f'display notification "{msg}" with title "arXiv Digest"'], check=False)


def main():
    push = "--no-push" not in sys.argv
    if push:
        run("git", "pull", "--rebase", "--autostash")
    code = os.path.join(ROOT, "code")
    run(PY, "extract_zotero.py", cwd=code)
    run(PY, "resolve_library.py", cwd=code)
    run(PY, "fetch_mine.py", cwd=code)
    last = max(a["mailing"] for a in json.load(open(os.path.join(ROOT, "data", "astroph.json"))))
    since = (date.fromisoformat(last) - timedelta(days=5)).isoformat()
    run(PY, "harvest_arxiv.py", since, cwd=code)
    run(PY, "parse_arxiv.py", cwd=code)
    run(PY, "corpus.py", cwd=code)
    run(PY, "embed.py", "indus", "positives", cwd=code)
    run(PY, "calibrate.py", cwd=code)
    if push:
        run("git", "add", *SHIPPED)
        if subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=ROOT).returncode:
            run("git", "commit", "-m", f"Quarterly model update {date.today().isoformat()}")
            run("git", "push")
    notify("Quarterly update finished.")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log(f"FAILED: {e}")
        notify("Quarterly update failed; see data/retrain.log.")
        sys.exit(1)
