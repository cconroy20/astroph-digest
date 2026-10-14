"""Render a day's sorted astro-ph listing as a local HTML page.

Usage:
  digest.py [--open]        # today's listing from arxiv.org -> digests/<date>.html (daily.py is the scheduled entry point)
  digest.py --replay DAY    # a past day from data/astroph.json (mailing-window date), for testing
"""
import html, json, os, re, sys, subprocess
from collections import defaultdict
from datetime import date, datetime, timedelta
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
from authors import split_arxiv, surname
from tex import tex_html, MATHJAX
from scorer import Scorer, leaf

ROOT = os.path.join(os.path.dirname(__file__), "..")
OUT = os.path.join(ROOT, "digests")
esc = html.escape

CSS = """
/* Layout: a fixed index column (date masthead + topic list) beside one wide reading column.
   Entries are set like a contents page: no boxes, hairline separators, one accent. Graphite paper, amber accent. */
:root{
 --paper:#F3F4F6; --ink:#16191D; --ink-2:#3F4650; --ink-3:#6A717B; --rule:#D9DCE1; --accent:#A65800; --wash:#F6EADB; --note:#35577F;
 --sans:'Instrument Sans','Helvetica Neue',Helvetica,Arial,sans-serif;
 --title:'Libre Franklin','Instrument Sans','Helvetica Neue',Helvetica,Arial,sans-serif;
 color-scheme:light}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){
 --paper:#14171B; --ink:#ECEDEF; --ink-2:#C0C5CC; --ink-3:#8A919B; --rule:#2B2F36; --accent:#F2A33A; --wash:#2A2117; --note:#9DB8DB; color-scheme:dark}}
:root[data-theme="dark"]{
 --paper:#14171B; --ink:#ECEDEF; --ink-2:#C0C5CC; --ink-3:#8A919B; --rule:#2B2F36; --accent:#F2A33A; --wash:#2A2117; --note:#9DB8DB; color-scheme:dark}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
@media (prefers-reduced-motion:reduce){html{scroll-behavior:auto}}
body{margin:0;background:var(--paper);color:var(--ink);font:400 19px/1.6 var(--sans);-webkit-font-smoothing:antialiased;font-kerning:normal}
::selection{background:var(--accent);color:var(--paper)}
a{color:inherit}
a:focus-visible,summary:focus-visible{outline:2px solid var(--accent);outline-offset:3px}
.wrap{display:grid;grid-template-columns:280px minmax(0,1fr);column-gap:72px;max-width:1720px;margin:0 auto;padding-inline:4vw;padding-block:56px 120px}

/* index column */
nav.side{position:sticky;top:56px;align-self:start;max-height:calc(100vh - 80px);overflow-y:auto;
 padding-right:28px;border-right:1px solid var(--rule)}
.mast{margin-bottom:36px;padding-bottom:22px;border-bottom:2px solid var(--ink)}
.mast .name{font-size:23px;font-weight:700;letter-spacing:-.015em;line-height:1.15}
.mast .when{margin-top:6px;font-size:16px;font-weight:500;color:var(--accent);font-variant-numeric:tabular-nums}
.mast .count{margin-top:2px;font-size:16px;color:var(--ink-2);font-variant-numeric:tabular-nums}
.mast .arch{display:inline-block;margin-top:10px;font-size:14px;font-weight:600;letter-spacing:.12em;text-transform:uppercase;color:var(--accent);text-decoration:none}
.mast .arch:hover{text-decoration:underline;text-underline-offset:4px}
.toc{display:flex;flex-direction:column;gap:14px;font-family:var(--title);font-size:15px;line-height:1.35}
.toc a{position:relative;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;
 padding:0;color:var(--ink-3);text-decoration:none;transition:color .15s}
.toc a:hover{color:var(--ink)}
.toc a.on{color:var(--ink)}
.toc a.last{margin-top:14px}

/* reading column */
main{min-width:0}
.sect{font-weight:500;font-size:30px;line-height:1.15;letter-spacing:-.02em;margin:0;scroll-margin-top:40px}
.picks{margin-top:0}
.entry{padding:28px 0 26px;border-top:1px solid var(--rule);scroll-margin-top:40px}
.picks .entry:first-child{border-top:none;padding-top:0}
.t{margin:0;font-family:var(--title);font-weight:600;font-size:26px;line-height:1.28;letter-spacing:0}
.t a{text-decoration:none;background-image:linear-gradient(var(--accent),var(--accent));background-size:0 2px;
 background-repeat:no-repeat;background-position:0 100%;transition:background-size .25s}
.t a:hover{background-size:100% 2px}
.au{margin:10px 0 0;font-size:18px;line-height:1.45;color:var(--ink-2)}
.cm{margin:4px 0 0;font-size:17px;line-height:1.45;color:var(--note)}
.act{position:relative;margin-top:12px;font-size:14px;font-weight:600;letter-spacing:.14em;text-transform:uppercase}
.act a.pdf{position:absolute;left:150px;top:0;color:var(--accent);text-decoration:none}
.act a.pdf:hover,.act summary:hover{text-decoration:underline;text-underline-offset:4px}
summary{list-style:none;cursor:pointer}
summary::-webkit-details-marker{display:none}
.act summary{display:inline-block;color:var(--accent);white-space:nowrap}
.act summary::after{content:" +";}
.act details[open] summary::after{content:" \\2212";}
.ab{margin-top:12px;font-weight:400;font-size:19px;line-height:1.62;letter-spacing:0;text-transform:none;color:var(--ink);max-width:80em}

/* the rest of the listing */
.others{margin-top:96px}
.others .sect{color:var(--ink-2)}
.rest{list-style:none;margin:18px 0 0;padding:0;border-top:2px solid var(--ink)}
.rest li{border-bottom:1px solid var(--rule)}
.rest li > a{display:block;padding:12px 0;font-family:var(--title);font-size:20px;font-weight:600;line-height:1.32;letter-spacing:0;color:var(--ink);text-decoration:none;transition:color .15s}
.rest li > a:hover{color:var(--accent)}
.rest li.p{padding:12px 0}
.rest li.p > a{padding:0}
.rest summary{display:block;margin-top:4px}
.rest .fa{display:block;font-size:17px;color:var(--ink-2)}
.rest .abt{display:inline-block;margin-top:3px;font-size:15px;font-weight:400;color:var(--ink-3);transition:color .15s}
.rest .abt::after{content:" +";}
.rest details[open] .abt::after{content:" \\2212";}
.rest summary:hover .abt,.rest details[open] .abt{color:var(--accent)}
.rest .ab{margin-top:10px}
.rest .star{color:var(--accent);margin-right:8px;font-size:15px}
footer{margin-top:64px;font-size:14px;color:var(--ink-3)}
"""

JS = """
const links=[...document.querySelectorAll('.toc a')];
const heads=links.map(a=>document.getElementById(a.getAttribute('href').slice(1)));
let tick=false;
function spy(){tick=false;let cur=0;
 heads.forEach((h,i)=>{if(h&&h.getBoundingClientRect().top<160)cur=i;});
 links.forEach((a,i)=>a.classList.toggle('on',i===cur));
}
addEventListener('scroll',()=>{if(!tick){tick=true;requestAnimationFrame(spy);}},{passive:true});spy();
"""

FONTS = ("<link rel='preconnect' href='https://fonts.googleapis.com'><link rel='preconnect' href='https://fonts.gstatic.com' crossorigin>"
         "<link rel='stylesheet' href='https://fonts.googleapis.com/css2?family=Instrument+Sans:wght@400;500;600;700&family=Libre+Franklin:wght@400;600&display=swap'>")


def authors_html(authors):
    names = split_arxiv(authors)
    extra = len(names) - 5
    return ", ".join(esc(n) for n in names[:5]) + (f" +{extra}" if extra > 0 else "")


def first_author(authors):
    names = split_arxiv(authors)
    if not names:
        return ""
    return esc(surname(names[0])) + (" et al." if len(names) > 1 else "")


def card(r, aid):
    cm = f'<p class="cm">{esc(r["comments"])}</p>' if r.get("comments") else ""
    return f"""<article class="entry" id="{aid}">
<h4 class="t"><a href="https://arxiv.org/abs/{r['id']}">{tex_html(r['title'])}</a></h4>
<p class="au">{authors_html(r['authors'])}</p>
{cm}
<div class="act"><details><summary>Abstract</summary><div class="ab">{tex_html(r["abstract"])}</div></details><a class="pdf" href="https://arxiv.org/pdf/{r['id']}">PDF</a></div>
</article>"""


def masthead(label, n):
    m = re.match(r"(\w+), (\d+) (\w+) (\d{4})", label)
    when = f"{m.group(1)[:3]} {m.group(2)} {m.group(3)[:3]} {m.group(4)}" if m else esc(label)
    return (f'<div class="mast"><div class="name">arXiv Digest</div><div class="when">{when}</div>'
            f'<div class="count">{n} new submissions</div><a class="arch" href="archive.html">Past digests</a></div>')


def build(label, rows, sc, E=None):
    """Papers above the calibrated threshold (about per_day on an average day) as one ranked list;
    the rest as a title list, also in score order. Pass E (text vectors) to skip embedding."""
    cfg = sc.cfg
    cal = json.load(open(os.path.join(ROOT, "models", cfg["model"], "calib.json")))
    E = sc.embed(rows) if E is None else E
    res, S = sc.score(rows, E=E)
    text = np.array([x["text"] for x in res])
    auth = np.array([x["auth"] for x in res])
    comb = (text - cal["mu"]) / cal["sd"] + cfg.get("alpha_auth", 0.0) * auth
    order = list(np.argsort(-comb))
    n_sel = int((comb >= cal["thresh"]).sum())
    n_sel = min(max(n_sel, cfg.get("min_sel", 5)), cfg.get("max_sel", 20), len(rows))
    top, rest = order[:n_sel], order[n_sel:]
    parts = ['<div class="picks">']
    nav = []
    for k, i in enumerate(top, 1):
        parts.append(card(rows[i], f"p{k}"))
        nav.append(f'<a href="#p{k}">{tex_html(rows[i]["title"])}</a>')
    parts.append("</div><section class='others'><h2 class='sect' id='other'>Other submissions</h2><ul class='rest'>")
    nav.append('<a class="last" href="#other">Other submissions</a>')
    for i in rest:
        star = '<span class="star" title="in your Zotero">&#9733;</span>' if rows[i]["id"] in sc.lib_arxiv else ""
        parts.append(f'<li class="p"><a href="https://arxiv.org/abs/{rows[i]["id"]}">{star}{tex_html(rows[i]["title"])}</a>'
                     f'<details><summary><span class="fa">{first_author(rows[i]["authors"])}</span>'
                     f'<span class="abt">Abstract</span></summary><div class="ab">{tex_html(rows[i]["abstract"])}</div></details></li>')
    parts.append("</ul></section>")
    parts.append(f"<footer>Ranked by {cfg['model']} against {int((sc.wt > 0).sum()):,} papers from your library and citations "
                 f"&middot; generated {datetime.now():%-d %b %Y, %H:%M}</footer>")
    page = f"<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>" \
           f"<title>arXiv Digest · {esc(label)}</title>{FONTS}<style>{CSS}</style>{MATHJAX}</head><body><div class='wrap'>" \
           f"<nav class='side'>{masthead(label, len(rows))}<div class='toc'>{''.join(nav)}</div></nav><main>{''.join(parts)}</main></div>" \
           f"<script>{JS}</script></body></html>"
    return page, order, res, E


def listing_label(mailing):
    d = date.fromisoformat(mailing) + timedelta(days=1)
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d.strftime("%A, %-d %B %Y")


if __name__ == "__main__":
    cfg = json.load(open(os.path.join(ROOT, "models", "config.json")))
    sc = Scorer(cfg)
    os.makedirs(OUT, exist_ok=True)
    if "--replay" in sys.argv:
        day = sys.argv[sys.argv.index("--replay") + 1]
        rows = [a for a in json.load(open(os.path.join(ROOT, "data", "astroph.json"))) if a["mailing"] == day]
        label = listing_label(day)
        fname = f"replay_{day}.html"
    else:
        from fetch_listing import fetch
        label, rows = fetch()
        fname = datetime.strptime(label, "%A, %d %B %Y").strftime("%Y-%m-%d") + ".html"
    page, order, res, E = build(label, rows, sc)
    path = os.path.join(OUT, fname)
    open(path, "w").write(page)
    print("wrote", path)
    if "--open" in sys.argv:
        subprocess.run(["open", path])
