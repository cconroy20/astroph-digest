"""Candidate site icons (64x64 viewBox) -> assets/options/*.svg and preview/icon_options.html."""
import os

D = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(D, "options")
os.makedirs(OUT, exist_ok=True)
TILE = '<rect width="64" height="64" rx="14" fill="#16191D"/>'
AMBER, LIGHT, SLATE = "#F2A33A", "#ECEDEF", "#9DB8DB"
GLOW = ('<defs><radialGradient id="g"><stop offset="0" stop-color="#F2A33A" stop-opacity=".6"/>'
        '<stop offset="1" stop-color="#F2A33A" stop-opacity="0"/></radialGradient></defs>')


def star(cx, cy, R, r, fill):
    import math
    pts = []
    for k in range(8):
        a = math.pi / 2 - k * math.pi / 4
        rad = R if k % 2 == 0 else r
        pts.append(f"{cx + rad * math.cos(a):.2f},{cy - rad * math.sin(a):.2f}")
    return f'<polygon points="{" ".join(pts)}" fill="{fill}"/>'


CHI_THIN = f'<line x1="47" y1="14" x2="17" y2="50" stroke="{LIGHT}" stroke-width="4.5" stroke-linecap="round"/>'
CHI_THICK = (f'<path d="M14 15 C 24 14, 28 22, 32 32 C 36 42, 40 50, 51 49" fill="none" stroke="{AMBER}" '
             f'stroke-width="7.5" stroke-linecap="round"/>')

OPTIONS = {
    "1 · arXiv chi": TILE + CHI_THIN + CHI_THICK,
    "2 · chi with a star": (GLOW + TILE + CHI_THIN.replace(LIGHT, "#8A919B") +
                            CHI_THICK.replace(AMBER, "#C9CED6").replace('7.5', '6') +
                            '<circle cx="32" cy="32" r="16" fill="url(#g)"/>' + star(32, 32, 15, 3.4, AMBER) +
                            '<circle cx="32" cy="32" r="3.6" fill="#FFF1DC"/>'),
    "3 · spectrum": (TILE + '<defs><linearGradient id="s" x1="0" x2="1">'
                     '<stop offset="0" stop-color="#5B4BD6"/><stop offset=".2" stop-color="#2F8FE8"/>'
                     '<stop offset=".42" stop-color="#3DBE8B"/><stop offset=".6" stop-color="#F2D33A"/>'
                     '<stop offset=".8" stop-color="#F28A2E"/><stop offset="1" stop-color="#D2433A"/></linearGradient></defs>'
                     '<rect x="8" y="19" width="48" height="26" rx="3" fill="url(#s)"/>'
                     + "".join(f'<rect x="{x}" y="19" width="{w}" height="26" fill="#16191D" opacity=".88"/>'
                               for x, w in [(14, 2.2), (21, 3.6), (30, 1.6), (36, 2.6), (46, 4.2), (52, 1.6)])),
    "4 · absorption line": (TILE + f'<path d="M9 20 H 21 C 26 20, 27.5 47, 32 47 C 36.5 47, 38 20, 43 20 H 55" '
                            f'fill="none" stroke="{AMBER}" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/>'),
    "5 · orbit": (GLOW + TILE + '<circle cx="32" cy="32" r="15" fill="url(#g)"/>'
                  f'<ellipse cx="32" cy="32" rx="24" ry="9" transform="rotate(-24 32 32)" fill="none" stroke="{LIGHT}" '
                  'stroke-width="2.6" opacity=".85"/>'
                  f'<circle cx="32" cy="32" r="7.5" fill="{AMBER}"/><circle cx="52.5" cy="22.6" r="3.6" fill="{SLATE}"/>'),
}

cells = []
for name, body in OPTIONS.items():
    fn = name.split(" ·")[0] + ".svg"
    open(os.path.join(OUT, fn), "w").write(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">{body}</svg>\n')
    src = f"../assets/options/{fn}"
    cells.append(f"""<section><h2>{name}</h2><div class="row">
<img src="{src}" width="150"><img src="{src}" width="64">
<span class="tab light"><img src="{src}" width="32"><img src="{src}" width="16">tab, light</span>
<span class="tab dark"><img src="{src}" width="32"><img src="{src}" width="16">tab, dark</span></div></section>""")
page = f"""<!doctype html><html><head><meta charset="utf-8"><title>Icon options</title>
<style>body{{margin:0;padding:40px 5vw;background:#F3F4F6;color:#16191D;font:16px/1.4 'Helvetica Neue',sans-serif}}
h1{{font-size:24px;margin:0 0 24px}}section{{padding:22px 0;border-top:2px solid #16191D}}h2{{font-size:16px;margin:0 0 14px;color:#A65800}}
.row{{display:flex;gap:36px;align-items:flex-end}}.tab{{display:flex;gap:10px;align-items:center;padding:10px 14px;border-radius:8px;font-size:13px}}
.light{{background:#fff;color:#555}}.dark{{background:#14171B;color:#aaa}}</style></head>
<body><h1>arXiv Digest icon options</h1>{''.join(cells)}</body></html>"""
open(os.path.join(D, "..", "preview", "icon_options.html"), "w").write(page)
print("wrote", len(OPTIONS), "options")
