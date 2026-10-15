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
a:focus-visible,.tg:focus-visible{outline:2px solid var(--accent);outline-offset:3px}
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
.au{margin:10px 0 0;font-size:19.5px;line-height:1.45;color:var(--ink-2)}
.cm{margin:4px 0 0;font-size:18.4px;line-height:1.45;color:var(--note)}
[hidden]{display:none!important}
.act{display:flex;align-items:baseline;gap:0 40px;margin-top:12px;font-size:14px;font-weight:600;letter-spacing:.14em;text-transform:uppercase}
.act a.pdf,.tg{color:var(--accent);text-decoration:none}
.tg{appearance:none;background:none;border:0;padding:0;margin:0;font:inherit;letter-spacing:inherit;text-transform:inherit;cursor:pointer}
.tg::after{content:" +";}
.tg.on::after{content:" \\2212";}
.act a.pdf:hover,.tg:hover{text-decoration:underline;text-underline-offset:4px}
.act .dtag{display:none;margin-left:auto;font-weight:500;color:var(--ink-3)}
.catchup .act .dtag{display:block}
.vote{display:none;gap:6px;margin-right:-8px}
.can-vote .vote{display:flex}
.vb{appearance:none;background:none;border:0;padding:0 2px;margin:0;font-size:15px;line-height:1;color:var(--ink-3);cursor:pointer;transition:color .15s}
.vb:hover{color:var(--ink)}
.vu.on{color:var(--accent)}
.vd.on{color:var(--note)}
.mast .vstat{font-size:15px;color:var(--ink-3)}
.mast .vstat:empty{display:none}
.mast .vstat.bad{color:var(--accent)}
.setup{margin:18px 0 0;padding:14px 18px;border:1px solid var(--rule);font-size:16px}
.setup p{margin:4px 0}
.setup input{width:min(520px,100%);padding:6px 8px;font:14px ui-monospace,Menlo,monospace;border:1px solid var(--rule);background:var(--paper);color:var(--ink)}
.setup button{padding:6px 12px;font:600 14px var(--sans);border:1px solid var(--ink-3);background:var(--paper);color:var(--ink);cursor:pointer}
.fg{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:28px;margin-top:18px}
.fgnote{grid-column:1/-1;margin:0 0 -12px;font-size:15px;color:var(--ink-3)}
.fig{margin:0;cursor:zoom-in}
.fig .im{height:250px;display:flex;gap:6px;align-items:center;justify-content:center;padding:10px;background:#fff;border:1px solid var(--rule);transition:border-color .15s}
.fig:hover .im{border-color:var(--ink-3)}
.fig .im img{min-width:0;max-width:100%;max-height:100%;object-fit:contain}
.fig figcaption{margin-top:8px;font-size:15px;line-height:1.45;color:var(--ink-2)}
.fig figcaption b,.lbin .cap b{color:var(--ink);font-weight:600}
.lb{position:fixed;inset:0;z-index:20;display:flex;align-items:center;justify-content:center;padding:3vh 3vw;background:rgba(12,14,18,.82);cursor:zoom-out}
.lbin{max-width:min(1500px,94vw);max-height:94vh;overflow:auto;padding:22px 26px;background:var(--paper);cursor:auto}
.lbin .ims{display:flex;flex-wrap:wrap;gap:10px;justify-content:center;padding:12px;background:#fff;cursor:zoom-out}
.lbin .ims img{max-width:100%;max-height:72vh;object-fit:contain}
.lbin .cap{margin:14px 0 0;font-size:17px;line-height:1.55}
.ab{margin-top:12px;font-weight:400;font-size:19px;line-height:1.62;letter-spacing:0;text-transform:none;color:var(--ink);max-width:80em}

/* archive page */
.rest{list-style:none;margin:0;padding:0}
.rest li{border-bottom:1px solid var(--rule)}
.rest li > a{display:block;padding:12px 0;font-family:var(--title);font-size:20px;font-weight:600;line-height:1.32;color:var(--ink);text-decoration:none;transition:color .15s}
.rest li > a:hover{color:var(--accent)}
footer{margin-top:64px;font-size:14px;color:var(--ink-3)}
"""

PAGE_JS = """
(function(){
 var REPO='cconroy20/astroph-digest', API='https://api.github.com/repos/'+REPO+'/contents/data/votes.json';
 var b=document.body, today=b.dataset.date, isIndex=!!b.dataset.index;
 function get(k){try{return localStorage.getItem(k)}catch(e){return null}}
 function set(k,v){try{v===null?localStorage.removeItem(k):localStorage.setItem(k,v)}catch(e){}}
 function $(q,el){return (el||document).querySelector(q)}

 /* ---------- abstract / figures toggles and the figure viewer ---------- */
 function load(el){el.querySelectorAll('img[data-src]').forEach(function(i){i.src=i.getAttribute('data-src');i.removeAttribute('data-src')})}
 function typeset(el){var M=window.MathJax; if(M&&M.typesetPromise) M.typesetPromise(el?[el]:undefined)}
 document.addEventListener('click',function(e){
  var t=e.target.closest('.tg');
  if(t){var p=$('.'+t.getAttribute('data-p'),t.closest('.entry')), open=p.hidden;
   p.hidden=!open; t.classList.toggle('on',open); if(open) load(p); return}
  var v=e.target.closest('.vb');
  if(v){var a=v.closest('.entry'); vote(a.dataset.id,a.dataset.day,v.classList.contains('vu')?1:-1); return}
  var f=e.target.closest('.fig');
  if(f){var lb=document.createElement('div'); lb.className='lb';
   lb.innerHTML='<div class="lbin">'+$('.full',f).innerHTML+'</div>'; document.body.appendChild(lb); load(lb); typeset(lb); return}
  var lb=e.target.closest('.lb'); if(lb&&(!e.target.closest('.lbin')||e.target.closest('.ims'))) lb.remove();  /* click outside or on the figure */
 });
 document.addEventListener('keydown',function(e){if(e.key==='Escape'){var lb=$('.lb'); if(lb) lb.remove()}});

 /* ---------- votes: kept in this browser, saved to data/votes.json with the token pasted at #setup ---------- */
 var token=get('arxivDigest.token'), state={votes:{},last_seen:null}, pending={votes:{}}, timer=null;
 try{pending=JSON.parse(get('arxivDigest.pending'))||pending}catch(e){}
 function status(msg,bad){var el=$('.mast .vstat'); if(!el) return; el.textContent=msg||''; el.classList.toggle('bad',!!bad);
  if(bad){var a=document.createElement('a'); a.href='#setup'; a.textContent=' Fix'; a.onclick=function(){setTimeout(function(){location.reload()},0)}; el.appendChild(a)}}
 function current(id){var p=pending.votes[id]; if(p) return p.v; var r=state.votes[id]; return r?r.v:0}
 function paint(){document.querySelectorAll('.entry[data-id]').forEach(function(a){var v=current(a.dataset.id);
  $('.vu',a).classList.toggle('on',v>0); $('.vd',a).classList.toggle('on',v<0)})}
 function savePending(){set('arxivDigest.pending',JSON.stringify(pending))}
 function vote(id,day,dir){var v=current(id)===dir?0:dir;
  pending.votes[id]={v:v,day:day,t:new Date().toISOString()}; savePending(); paint(); schedule(6000)}
 function schedule(ms){clearTimeout(timer); timer=setTimeout(flush,ms)}
 function api(method,body){return fetch(API,{method:method,cache:'no-store',body:body?JSON.stringify(body):undefined,
  headers:{'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28'}})}
 function dec(c){return JSON.parse(decodeURIComponent(escape(atob(c.replace(/\\n/g,'')))))}
 function enc(o){return btoa(unescape(encodeURIComponent(JSON.stringify(o,null,1)+'\\n')))}
 function readRemote(){return api('GET').then(function(r){
  if(r.status===404) return {sha:null,data:{last_seen:null,votes:{}}};
  if(!r.ok) throw new Error(r.status===401||r.status===403?'token rejected':'GitHub error '+r.status);
  return r.json().then(function(j){return {sha:j.sha,data:dec(j.content)}})})}
 function flush(retry){
  if(!token) return;
  var ids=Object.keys(pending.votes); if(!ids.length&&!pending.last_seen) return;
  var sent=JSON.parse(JSON.stringify(pending)); status('Saving votes\\u2026');
  readRemote().then(function(rem){
   var d=rem.data; d.votes=d.votes||{};
   Object.keys(sent.votes).forEach(function(id){var v=sent.votes[id]; if(v.v) d.votes[id]=v; else delete d.votes[id]});
   if(sent.last_seen&&(!d.last_seen||sent.last_seen>d.last_seen)) d.last_seen=sent.last_seen;
   var n=Object.keys(sent.votes).length;
   return api('PUT',{message:n?'Votes: '+n+' change'+(n>1?'s':''):'Last read '+d.last_seen,content:enc(d),sha:rem.sha||undefined})
    .then(function(r){
     if(r.status===409||r.status===422){if(!retry) return flush(true); throw new Error('conflict')}
     if(!r.ok) throw new Error(r.status===401||r.status===403?'token rejected':'GitHub error '+r.status);
     state=d;   /* drop what was sent; keep anything voted while saving */
     Object.keys(sent.votes).forEach(function(id){if(pending.votes[id]&&pending.votes[id].t===sent.votes[id].t) delete pending.votes[id]});
     if(pending.last_seen===sent.last_seen) delete pending.last_seen;
     savePending(); status('');
    })
  }).catch(function(e){status('Votes not saved ('+e.message+').',true)});
 }
 document.addEventListener('visibilitychange',function(){if(document.visibilityState==='hidden') flush()});

 /* ---------- setup panel: #setup ---------- */
 if(location.hash==='#setup'){
  var box=document.createElement('section'); box.className='setup';
  box.innerHTML='<p><b>Voting setup.</b> Paste a GitHub fine-grained token with <i>Contents: read and write</i> access to '
   +REPO+' only. It is kept in this browser and sent only to GitHub.</p>'
   +'<p><input id="tok" type="password" autocomplete="off" placeholder="github_pat_\\u2026"> <button id="tok-save">Save</button> '
   +'<button id="tok-clear">Remove token</button> <span id="tok-msg"></span></p>';
  $('.mast').after(box);
  $('#tok-save').onclick=function(){var t=$('#tok').value.trim(); if(!t) return; token=t;
   readRemote().then(function(){set('arxivDigest.token',t); $('#tok-msg').textContent='Saved. Voting is on.';
    setTimeout(function(){location.hash=''; location.reload()},800)})
   .catch(function(e){token=get('arxivDigest.token'); $('#tok-msg').textContent='Not saved: '+e.message+'.'})};
  $('#tok-clear').onclick=function(){set('arxivDigest.token',null); token=null; $('#tok-msg').textContent='Token removed from this browser.'};
 }

 /* ---------- catch-up: merge every listing since the last one read ---------- */
 function fmt(d){return new Date(d+'T12:00:00').toLocaleDateString('en-GB',{weekday:'short',day:'numeric',month:'short'})}
 function catchup(seen){
  var view=null; try{view=JSON.parse(get('arxivDigest.view')||'null')}catch(e){}
  var from=null;
  if(view&&view.to===today) from=view.from;      /* same day: keep the merged view on reload */
  else if(seen&&seen<today) from=seen;           /* listings after the last one read are unread */
  set('arxivDigest.seen',today); set('arxivDigest.view',from?JSON.stringify({from:from,to:today}):null);
  if(token){pending.last_seen=today; savePending(); schedule(2000)}
  if(!from) return;
  fetch('days/index.json',{cache:'no-cache'}).then(function(r){return r.json()}).then(function(idx){
   var days=idx.filter(function(d){return d>from&&d<=today}).slice(-15);
   if(days.length<2) return;
   return Promise.all(days.map(function(d){return fetch('days/'+d+'.json').then(function(r){return r.json()})})).then(function(data){
    var ps=[].concat.apply([],data.map(function(x){return x.papers})).sort(function(a,c){return c.s-a.s});
    $('main.list').innerHTML=ps.map(function(p){return p.html}).join('');
    b.classList.add('catchup');
    $('.mast .when').textContent=fmt(days[0])+' \\u2013 '+fmt(today);
    $('.mast .count').textContent=days.length+' listings \\u00b7 '+ps.length+' new submissions';
    var a=document.createElement('a'); a.className='arch'; a.href='#'; a.textContent='Today only';
    a.onclick=function(e){e.preventDefault(); set('arxivDigest.view',null); location.reload()};
    var arch=$('.mast .arch'); arch.parentNode.insertBefore(a,arch);
    paint();
    (function ts(){var M=window.MathJax; if(M&&M.typesetPromise){(M.startup&&M.startup.promise||Promise.resolve()).then(function(){M.typesetPromise()})} else setTimeout(ts,200)})();
   });
  }).catch(function(){});
 }

 /* ---------- start ---------- */
 if(token){
  b.classList.add('can-vote'); paint();
  readRemote().then(function(rem){state=rem.data; state.votes=state.votes||{}; paint();
   /* the repo keeps the last-read date, so catch-up survives a browser that wiped its storage */
   var seen=[rem.data.last_seen,pending.last_seen].filter(Boolean).sort().pop()||get('arxivDigest.seen');
   if(isIndex) catchup(seen); if(Object.keys(pending.votes).length) schedule(1000)})
  .catch(function(e){status('Votes not saved ('+e.message+').',true); if(isIndex) catchup(get('arxivDigest.seen'))});
 } else if(isIndex) catchup(get('arxivDigest.seen'));
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


def short_caption(cap, n=170):
    """First sentence of a caption (never cut inside $...$), at most about n characters."""
    for m in re.finditer(r"\. ", cap):
        if m.start() > 30 and cap[:m.start()].count("$") % 2 == 0:
            cap = cap[:m.start() + 1]
            break
    if len(cap) > n:
        cut = max((i for i in range(30, n) if cap[i] == " " and cap[:i].count("$") % 2 == 0), default=None)
        cap = cap[:cut] + " \u2026" if cut else cap
    return cap


def figure_html(f):
    thumbs = "".join(f'<img data-src="{esc(u)}" alt="">' for u in f["imgs"][:4])
    full = "".join(f'<img data-src="{esc(u)}" alt="">' for u in f["imgs"])
    n = esc(f["n"])
    return (f'<figure class="fig"><div class="im">{thumbs}</div><figcaption><b>{n}.</b> {tex_html(short_caption(f["cap"]))}</figcaption>'
            f'<div class="full" hidden><div class="ims">{full}</div><p class="cap"><b>{n}.</b> {tex_html(f["cap"])}</p></div></figure>')


def card(r, day_tag="", day_iso=""):
    cm = f'<p class="cm">{esc(r["comments"])}</p>' if r.get("comments") else ""
    figs = r.get("figs") or []
    fbtn = '<button class="tg" data-p="fg">Figures</button>' if figs else ""
    note = '<p class="fgnote">Key figures as named by the authors</p>' if any(f.get("key") for f in figs) else ""
    fpanel = f'<div class="fg" hidden>{note}{"".join(figure_html(f) for f in figs)}</div>' if figs else ""
    return f"""<article class="entry" data-id="{r['id']}" data-day="{day_iso}">
<h4 class="t"><a href="https://arxiv.org/abs/{r['id']}">{tex_html(r['title'])}</a></h4>
<p class="au">{authors_html(r['authors'])}</p>
{cm}
<div class="act"><span class="vote"><button class="vb vu" title="More like this" aria-label="Upvote">&#9650;</button><button class="vb vd" title="Less like this" aria-label="Downvote">&#9660;</button></span><button class="tg" data-p="ab">Abstract</button>{fbtn}<a class="pdf" href="https://arxiv.org/pdf/{r['id']}">PDF</a><span class="dtag">{day_tag}</span></div>
<div class="ab" hidden>{tex_html(r["abstract"])}</div>
{fpanel}
</article>"""


def masthead(label, n):
    m = re.match(r"(\w+), (\d+) (\w+) (\d{4})", label)
    when = f"{m.group(1)[:3]} {m.group(2)} {m.group(3)[:3]} {m.group(4)}" if m else esc(label)
    return (f'<header class="mast"><div class="name">arXiv Digest</div><div class="info"><span class="when">{when}</span>'
            f'<span class="count">{n} new submissions</span><span class="vstat"></span><a class="arch" href="archive.html">Past digests</a></div></header>')


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
    items = [{"s": round(float(comb[i]), 4), "html": card(rows[i], f"{day:%a %-d %b}", f"{day:%Y-%m-%d}")} for i in order]
    parts = [masthead(label, len(rows)), '<main class="list">'] + [it["html"] for it in items] + ["</main>"]
    parts.append(f"<footer>Ranked by {cfg['model']} against {int((sc.wt > 0).sum()):,} papers from your library and citations "
                 f"&middot; generated {datetime.now():%-d %b %Y, %H:%M}</footer>")
    page = f"<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><meta name='robots' content='noindex, nofollow'>" \
           f"<title>arXiv Digest · {esc(label)}</title>{ICONS}{FONTS}<style>{CSS}</style>{MATHJAX}</head><body data-date='{day:%Y-%m-%d}'>" \
           f"<div class='wrap'>{''.join(parts)}</div><script>{PAGE_JS}</script></body></html>"
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
