"""Writes the arXiv Digest icon: an amber chi (after arXiv's own logo) on a graphite tile.
favicon.svg (rounded tile, browser tabs) and touch.svg (full-bleed tile; Apple rounds touch icons itself).
Chosen 2026-10-14 from the options in icon_options.py (option 1)."""
import os
D = os.path.dirname(os.path.abspath(__file__))


def svg(rx):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
<rect width="64" height="64" rx="{rx}" fill="#16191D"/>
<line x1="47" y1="14" x2="17" y2="50" stroke="#ECEDEF" stroke-width="4.5" stroke-linecap="round"/>
<path d="M14 15 C 24 14, 28 22, 32 32 C 36 42, 40 50, 51 49" fill="none" stroke="#F2A33A" stroke-width="7.5" stroke-linecap="round"/>
</svg>
"""


open(os.path.join(D, "favicon.svg"), "w").write(svg(14))
open(os.path.join(D, "touch.svg"), "w").write(svg(0))
