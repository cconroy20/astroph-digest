"""Print new=true/false for $GITHUB_OUTPUT: has arXiv announced a listing that docs/ does not have yet?

Standard library only, so the workflow can ask before installing anything; when nothing is new the run ends in
seconds. On any doubt (arXiv unreachable, a partial page) the answer is true, and daily.py does the careful fetch.
"""
import os, re, sys, time, urllib.request
from datetime import datetime

new = "true"
try:
    req = urllib.request.Request(f"https://arxiv.org/list/astro-ph/new?skip=0&show=2000&_={int(time.time())}",
                                 headers={"User-Agent": "arxivsort (personal digest)"})
    page = urllib.request.urlopen(req, timeout=60).read().decode("utf-8", "replace")
    m = re.search(r"Showing new listings for \w+, (\d+ \w+ \d{4})", page)
    if m and "New submissions (showing" in page:
        day = datetime.strptime(m.group(1), "%d %B %Y").strftime("%Y-%m-%d")
        done = os.path.exists(os.path.join(sys.argv[1] if len(sys.argv) > 1 else "docs", day + ".html"))
        print(f"arXiv listing {day}: {'already built' if done else 'new'}", file=sys.stderr)
        new = "false" if done else "true"
    else:
        print("listing page incomplete; taking the full path", file=sys.stderr)
except Exception as e:
    print(f"check failed ({e}); taking the full path", file=sys.stderr)
print(f"new={new}")
