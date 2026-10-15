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
from authors import split_arxiv
from tex import tex_html, MATHJAX
from scorer import Scorer, leaf

ROOT = os.path.join(os.path.dirname(__file__), "..")
OUT = os.path.join(ROOT, "digests")
esc = html.escape

CSS = """
/* Layout: one wide reading column under a masthead bar; every paper of the listing in score order.
   Entries are set like a contents page: no boxes, hairline separators, one accent. Graphite paper, amber accent. */
:root{
 --paper:#F3F4F6; --ink:#16191D; --ink-2:#3F4650; --ink-3:#6A717B; --rule:#D9DCE1; --accent:#A65800; --note:#35577F;
 --sans:'Instrument Sans','Helvetica Neue',Helvetica,Arial,sans-serif;
 --title:'Libre Franklin','Instrument Sans','Helvetica Neue',Helvetica,Arial,sans-serif;
 color-scheme:light}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){
 --paper:#14171B; --ink:#ECEDEF; --ink-2:#C0C5CC; --ink-3:#8A919B; --rule:#2B2F36; --accent:#F2A33A; --note:#9DB8DB; color-scheme:dark}}
:root[data-theme="dark"]{
 --paper:#14171B; --ink:#ECEDEF; --ink-2:#C0C5CC; --ink-3:#8A919B; --rule:#2B2F36; --accent:#F2A33A; --note:#9DB8DB; color-scheme:dark}
*{box-sizing:border-box}
body{margin:0;background:var(--paper);color:var(--ink);font:400 19px/1.6 var(--sans);-webkit-font-smoothing:antialiased;font-kerning:normal}
::selection{background:var(--accent);color:var(--paper)}
a{color:inherit}
a:focus-visible,summary:focus-visible{outline:2px solid var(--accent);outline-offset:3px}
.wrap{max-width:1320px;margin:0 auto;padding-inline:4vw;padding-block:48px 120px}

/* masthead */
.mast{display:flex;flex-wrap:wrap;align-items:baseline;justify-content:space-between;gap:10px 40px;
 padding-bottom:18px;border-bottom:2px solid var(--ink)}
.mast .name{font-size:30px;font-weight:700;letter-spacing:-.02em;line-height:1.1}
.mast .info{display:flex;flex-wrap:wrap;align-items:baseline;gap:6px 28px;font-size:17px;font-variant-numeric:tabular-nums}
.mast .when{font-weight:500;color:var(--accent)}
.mast .count{color:var(--ink-2)}
.mast .arch{font-size:14px;font-weight:600;letter-spacing:.12em;text-transform:uppercase;color:var(--accent);text-decoration:none}
.mast .arch:hover{text-decoration:underline;text-underline-offset:4px}

/* entries */
.entry{padding:28px 0 26px;border-top:1px solid var(--rule)}
.list .entry:first-child{border-top:none}
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
.act .dtag{display:none;position:absolute;right:0;top:0;font-weight:500;color:var(--ink-3)}
.catchup .act .dtag{display:block}
.ab{margin-top:12px;font-weight:400;font-size:19px;line-height:1.62;letter-spacing:0;text-transform:none;color:var(--ink);max-width:80em}

/* archive page */
.rest{list-style:none;margin:0;padding:0}
.rest li{border-bottom:1px solid var(--rule)}
.rest li > a{display:block;padding:12px 0;font-family:var(--title);font-size:20px;font-weight:600;line-height:1.32;color:var(--ink);text-decoration:none;transition:color .15s}
.rest li > a:hover{color:var(--accent)}
footer{margin-top:64px;font-size:14px;color:var(--ink-3)}
"""

CATCHUP_JS = """
(function(){
 var b=document.body; if(!b.dataset.index) return;
 var today=b.dataset.date, KEY='arxivDigest.seen', VIEW='arxivDigest.view', MAX=15;
 function get(k){try{return localStorage.getItem(k)}catch(e){return null}}
 function set(k,v){try{v===null?localStorage.removeItem(k):localStorage.setItem(k,v)}catch(e){}}
 var seen=get(KEY), view=null; try{view=JSON.parse(get(VIEW)||'null')}catch(e){}
 var from=null;
 if(view&&view.to===today) from=view.from;            /* same day: keep the merged view on reload */
 else if(seen&&seen<today) from=seen;                 /* listings after the last one viewed are unread */
 set(KEY,today); set(VIEW,from?JSON.stringify({from:from,to:today}):null);
 if(!from) return;
 function fmt(d){return new Date(d+'T12:00:00').toLocaleDateString('en-GB',{weekday:'short',day:'numeric',month:'short'})}
 fetch('days/index.json',{cache:'no-cache'}).then(function(r){return r.json()}).then(function(idx){
  var days=idx.filter(function(d){return d>from&&d<=today}).slice(-MAX);
  if(days.length<2) return;
  return Promise.all(days.map(function(d){return fetch('days/'+d+'.json').then(function(r){return r.json()})})).then(function(data){
   var ps=[].concat.apply([],data.map(function(x){return x.papers})).sort(function(a,c){return c.s-a.s});
   document.querySelector('main.list').innerHTML=ps.map(function(p){return p.html}).join('');
   b.classList.add('catchup');
   document.querySelector('.mast .when').textContent=fmt(days[0])+' \\u2013 '+fmt(today);
   document.querySelector('.mast .count').textContent=days.length+' listings \\u00b7 '+ps.length+' new submissions';
   var a=document.createElement('a'); a.className='arch'; a.href='#'; a.textContent='Today only';
   a.onclick=function(e){e.preventDefault(); set(VIEW,null); location.reload()};
   var arch=document.querySelector('.mast .arch'); arch.parentNode.insertBefore(a,arch);
   (function ts(){var M=window.MathJax; if(M&&M.typesetPromise){(M.startup&&M.startup.promise||Promise.resolve()).then(function(){M.typesetPromise()})} else setTimeout(ts,200)})();
  });
 }).catch(function(){});
})();
"""

# file names carry the design ("chi"): browsers cache icons by URL, so a new design needs new names
ICONS = ("<link rel='icon' href='icon-chi-32.png' sizes='32x32' type='image/png'>"
         "<link rel='icon' href='icon-chi.svg' type='image/svg+xml'><link rel='apple-touch-icon' href='apple-touch-icon-chi.png'>")

FONTS = ("<link rel='preconnect' href='https://fonts.googleapis.com'><link rel='preconnect' href='https://fonts.gstatic.com' crossorigin>"
         "<link rel='stylesheet' href='https://fonts.googleapis.com/css2?family=Instrument+Sans:wght@400;500;600;700&family=Libre+Franklin:wght@400;600&display=swap'>")


def authors_html(authors):
    names = split_arxiv(authors)
    extra = len(names) - 5
    return ", ".join(esc(n) for n in names[:5]) + (f" +{extra}" if extra > 0 else "")


def card(r, day_tag=""):
    cm = f'<p class="cm">{esc(r["comments"])}</p>' if r.get("comments") else ""
    return f"""<article class="entry">
<h4 class="t"><a href="https://arxiv.org/abs/{r['id']}">{tex_html(r['title'])}</a></h4>
<p class="au">{authors_html(r['authors'])}</p>
{cm}
<div class="act"><details><summary>Abstract</summary><div class="ab">{tex_html(r["abstract"])}</div></details><a class="pdf" href="https://arxiv.org/pdf/{r['id']}">PDF</a><span class="dtag">{day_tag}</span></div>
</article>"""


def masthead(label, n):
    m = re.match(r"(\w+), (\d+) (\w+) (\d{4})", label)
    when = f"{m.group(1)[:3]} {m.group(2)} {m.group(3)[:3]} {m.group(4)}" if m else esc(label)
    return (f'<header class="mast"><div class="name">arXiv Digest</div><div class="info"><span class="when">{when}</span>'
            f'<span class="count">{n} new submissions</span><a class="arch" href="archive.html">Past digests</a></div></header>')


def build(label, rows, sc, E=None):
    """The whole listing as one list in score order. Pass E (text vectors) to skip embedding.
    Also returns items = [{s: score, html: entry}] for the catch-up data file (scores share one scale across days)."""
    cfg = sc.cfg
    cal = json.load(open(os.path.join(ROOT, "models", cfg["model"], "calib.json")))
    E = sc.embed(rows) if E is None else E
    res, S = sc.score(rows, E=E)
    text = np.array([x["text"] for x in res])
    auth = np.array([x["auth"] for x in res])
    comb = (text - cal["mu"]) / cal["sd"] + cfg.get("alpha_auth", 0.0) * auth
    order = list(np.argsort(-comb))
    day = datetime.strptime(label, "%A, %d %B %Y")
    items = [{"s": round(float(comb[i]), 4), "html": card(rows[i], f"{day:%a %-d %b}")} for i in order]
    parts = [masthead(label, len(rows)), '<main class="list">'] + [it["html"] for it in items] + ["</main>"]
    parts.append(f"<footer>Ranked by {cfg['model']} against {int((sc.wt > 0).sum()):,} papers from your library and citations "
                 f"&middot; generated {datetime.now():%-d %b %Y, %H:%M}</footer>")
    page = f"<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>" \
           f"<title>arXiv Digest · {esc(label)}</title>{ICONS}{FONTS}<style>{CSS}</style>{MATHJAX}</head><body data-date='{day:%Y-%m-%d}'>" \
           f"<div class='wrap'>{''.join(parts)}</div><script>{CATCHUP_JS}</script></body></html>"
    return page, order, res, E, items


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
