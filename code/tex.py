"""Turn arXiv title/abstract TeX into HTML: math segments are left for MathJax (escaped only);
text-mode commands are converted here (MathJax only typesets math)."""
import html, re, unicodedata

# TeX accents -> Unicode combining marks
ACCENT = {"'": "\u0301", "`": "\u0300", "^": "\u0302", '"': "\u0308", "~": "\u0303", "=": "\u0304", ".": "\u0307",
          "u": "\u0306", "v": "\u030c", "H": "\u030b", "c": "\u0327", "k": "\u0328", "r": "\u030a", "d": "\u0323",
          "b": "\u0331"}
LETTER = {"ss": "ß", "aa": "å", "AA": "Å", "ae": "æ", "AE": "Æ", "oe": "œ", "OE": "Œ", "dh": "ð", "DH": "Ð", "th": "þ",
          "TH": "Þ", "ng": "ŋ", "NG": "Ŋ", "dj": "đ", "DJ": "Đ", "o": "ø", "O": "Ø", "l": "ł", "L": "Ł", "i": "ı", "j": "ȷ"}
DOTLESS = {"ı": "i", "ȷ": "j"}  # an accent on \i or \j sits on a plain i/j


def accents(s):
    """\\'a, \\'{a}, {\\'a}, \\v{s}, \\c c, \\'{\\i}, {\\ss}, {\\o} ... -> Unicode (NFC)."""
    s = re.sub(r"\\(ss|aa|AA|ae|AE|oe|OE|dh|DH|th|TH|ng|NG|dj|DJ|o|O|l|L|i|j)(?![A-Za-z])\s?", lambda m: LETTER[m.group(1)], s)
    mark = lambda m: DOTLESS.get(m.group(2), m.group(2)) + ACCENT[m.group(1)]
    s = re.sub(r"\\([uvHckrdb])\s*\{\s*([A-Za-zıȷ])\s*\}", mark, s)
    s = re.sub(r"\\([uvHckrdb])\s+([A-Za-zıȷ])(?![A-Za-z])", mark, s)
    s = re.sub(r"\\(['`^\"~=.])\s*\{\s*([A-Za-zıȷ])\s*\}", mark, s)
    s = re.sub(r"\\(['`^\"~=.])([A-Za-zıȷ])", mark, s)
    return unicodedata.normalize("NFC", s)


def detex_plain(s):
    """Plain-text cleanup for author lists: accents, \\&, ties, grouping braces."""
    s = accents(s or "").replace("\\&", "&")
    s = re.sub(r"(?<!\\)~", " ", s)
    return re.sub(r"[{}]", "", s)


MATH = re.compile(r"(?<!\\)\$\$.+?(?<!\\)\$\$|(?<!\\)\$.+?(?<!\\)\$|\\\(.+?\\\)|\\\[.+?\\\]", re.S)

GREEK = {n: c for n, c in zip(
    "alpha beta gamma delta epsilon varepsilon zeta eta theta kappa lambda mu nu xi pi rho sigma tau phi varphi chi psi omega "
    "Gamma Delta Theta Lambda Xi Pi Sigma Phi Psi Omega".split(),
    "αβγδεεζηθκλμνξπρστφφχψωΓΔΘΛΞΠΣΦΨΩ")}
SYMBOLS = {"deg": "°", "degr": "°", "pm": "±", "sim": "∼", "approx": "≈", "times": "×", "odot": "⊙", "sun": "⊙",
           "lesssim": "≲", "gtrsim": "≳", "le": "≤", "leq": "≤", "ge": "≥", "geq": "≥", "AA": "Å", "ell": "ℓ",
           "arcsec": "″", "arcmin": "′", "prime": "′", "infty": "∞", "rightarrow": "→", "to": "→", "propto": "∝"}
ROMAN = ["", "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII", "XIII", "XIV", "XV",
         "XVI", "XVII", "XVIII", "XIX", "XX"]
FONT = {"textit": "i", "emph": "i", "it": "i", "em": "i", "textbf": "b", "bf": "b",
        "texttt": "code", "tt": "code", "textsc": "sc", "sc": "sc", "textrm": "", "rm": "", "textup": "", "mathrm": ""}


def _wrap(tag, x):
    if tag == "sc":
        return f'<span style="font-variant:small-caps">{x}</span>'
    return f"<{tag}>{x}</{tag}>" if tag else x


def _text(t):
    t = html.escape(accents(t), quote=False)
    t = t.replace("``", "“").replace("''", "”").replace("---", "—").replace("--", "–")
    t = re.sub(r"\\&amp;", "&amp;", t)
    t = re.sub(r"\\([%_#])", r"\1", t)
    t = re.sub(r"\\r\{A\}", "Å", t)
    t = re.sub(r"\\ion\{([A-Za-z]+)\}\{(\d+)\}", lambda m: f"{m.group(1)}&nbsp;{ROMAN[int(m.group(2))] if int(m.group(2)) < len(ROMAN) else m.group(2)}", t)
    t = re.sub(r"\\cite[pt]?\*?\{([^}]*)\}", r"(\1)", t)
    # \textit{X} and {\it X}
    for _ in range(2):
        t = re.sub(r"\\(textit|emph|textbf|texttt|textsc|textrm|textup)\{([^{}]*)\}", lambda m: _wrap(FONT[m.group(1)], m.group(2)), t)
        t = re.sub(r"\{\\(it|em|bf|tt|sc|rm)\s+([^{}]*)\}", lambda m: _wrap(FONT[m.group(1)], m.group(2)), t)
    t = re.sub(r"\\([A-Za-z]+)(?![A-Za-z])", lambda m: GREEK.get(m.group(1)) or SYMBOLS.get(m.group(1)) or m.group(0), t)
    t = re.sub(r"\\[ ,;!]", " ", t)
    # TeX tie: keep "~" when it means "approximately" (" ~10", "~+0.2"); a tie between word characters
    # ("[O~III]", "Fig.~3"; but "z~2" means z≈2 and stays) becomes a non-breaking space
    t = re.sub(r"(?<=\w)~(?=[A-Z])|(?<=\.)~(?=\d)", "&nbsp;", t)
    t = re.sub(r"\{([^{}<>]*)\}", r"\1", t)  # leftover grouping braces, e.g. H{α}
    return t


def tex_html(s):
    out, pos = [], 0
    for m in MATH.finditer(s or ""):
        out.append(_text(s[pos:m.start()]))
        out.append(html.escape(m.group(0), quote=False))
        pos = m.end()
    out.append(_text((s or "")[pos:]))
    return "".join(out)


MATHJAX = r"""<script>
MathJax={tex:{inlineMath:[['$','$'],['\\(','\\)']],displayMath:[['$$','$$'],['\\[','\\]']],processEscapes:true,
 macros:{AA:'\\unicode{x212B}',msun:'M_\\odot',Msun:'M_\\odot',sun:'\\odot',degr:'^\\circ',arcsec:'^{\\prime\\prime}',
 kms:'\\,\\mathrm{km\\,s^{-1}}',micron:'\\mu\\mathrm{m}',farcs:'.\\!\\!^{\\prime\\prime}',ion:['\\mathrm{#1\\,\\small #2}',2]}},
 options:{skipHtmlTags:['script','noscript','style','textarea','pre','code']},chtml:{scale:0.97}};
</script><script async src="https://cdn.jsdelivr.net/npm/mathjax@3.2.2/es5/tex-chtml.js" integrity="sha384-AHAnt9ZhGeHIrydA1Kp1L7FN+2UosbF7RQg6C+9Is/a7kDpQ1684C2iH2VWil6r4" crossorigin="anonymous"></script>"""


if __name__ == "__main__":
    for s in ["The $R$-Process Alliance: On J0010$-$1735, an Accreted, Chemically Unusual",
              "A Comprehensive JWST Slitless Census of $\\sim$12,000 Emission-Line Galaxies",
              "less than 3\\% (90\\% credible interval) of ``cocoon'' A--F--G stars by ~+0.2dex",
              "detected by \\textit{Swift} and {\\it HST} in [O~III], H{\\alpha} at 4607 \\AA\\, and \\ion{C}{2}] 2326",
              "z~2 galaxies, Fig.~3, cost of \\$10, \\texttt{scipy.signal.find\\_peaks}, \\citet{Almeida2022}",
              "Imaging dark matter at the smallest scales with $z\\approx1$ lensed stars & <things>"]:
        print(tex_html(s))
