"""Writes the arXiv Digest icon: an amber four-spike star on a graphite tile.
favicon.svg (rounded tile) and touch.svg (full-bleed tile; Apple rounds touch icons itself)."""
import math, os
D = os.path.dirname(os.path.abspath(__file__))


STARS = """<circle cx="14" cy="15" r="1.3" fill="#C0C5CC" opacity=".7"/>
<circle cx="51" cy="49" r="1.1" fill="#C0C5CC" opacity=".55"/>
<circle cx="49" cy="13" r=".9" fill="#C0C5CC" opacity=".45"/>"""


def svg(rx, small=False):
    """small=True: bolder spikes and core, no background stars -- for 16-32 px tab icons."""
    c, R, r = (32, 27, 5.2) if small else (32, 25, 3.0)
    pts = []
    for k in range(8):
        ang = math.pi / 2 - k * math.pi / 4
        rad = R if k % 2 == 0 else r
        pts.append(f"{c + rad * math.cos(ang):.2f},{c - rad * math.sin(ang):.2f}")
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
<defs><radialGradient id="g" cx="50%" cy="50%" r="50%">
<stop offset="0" stop-color="#F2A33A" stop-opacity=".55"/><stop offset="1" stop-color="#F2A33A" stop-opacity="0"/></radialGradient></defs>
<rect width="64" height="64" rx="{rx}" fill="#16191D"/>
<circle cx="32" cy="32" r="17" fill="url(#g)"/>
{'' if small else STARS}
<polygon points="{' '.join(pts)}" fill="#F2A33A"/>
<circle cx="32" cy="32" r="{5.0 if small else 3.6}" fill="#FFF1DC"/>
</svg>
"""


open(os.path.join(D, "favicon.svg"), "w").write(svg(14, small=True))
open(os.path.join(D, "touch.svg"), "w").write(svg(0))
