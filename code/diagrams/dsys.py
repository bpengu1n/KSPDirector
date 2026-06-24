"""
Design system for Perseus 1 NASA-style technical sheets.
Palette + primitives shared by both drawing sheets.
"""
from xml.sax.saxutils import escape as _esc

# ---------------------------------------------------------------- palette --
PAPER        = '#f6f4ec'   # vellum background
PANEL        = '#fcfbf6'   # slightly lighter panel fill
INK          = '#16181d'   # primary line / text (near-black)
INK_SOFT     = '#52565f'   # secondary text
INK_FAINT    = '#8a8d93'   # tertiary / fine print
BLUEPRINT    = '#0b3d91'   # NASA-blue accent
SAFETY_RED   = '#c81d25'   # critical / separation accent
VIOLET       = '#5c3d8c'   # booster-event accent
TEAL         = '#0e6e5c'   # mission-stage accent
FILL_BASE    = '#eae7dd'   # warm light fill for structure
FILL_BLUE    = '#dde3ee'   # pale blue-grey fill for tankage
FILL_BLUE_DK = '#c4cee2'   # darker pale blue (second tank)
HATCH_COL    = '#9aa0aa'
GRID_OPACITY = 0.05

FONT_HEAD = "'Arial Narrow', Arial, 'Helvetica Neue', sans-serif"
FONT_BODY = "Arial, 'Helvetica Neue', sans-serif"
FONT_MONO = "'Courier New', 'DejaVu Sans Mono', monospace"


# ------------------------------------------------------------- primitives --
def rect(x, y, w, h, fill, stroke=INK, sw=1.6, rx=0, extra='', opacity=None):
    op = f' opacity="{opacity}"' if opacity is not None else ''
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}" rx="{rx}"{op} {extra}/>'


def line(x1, y1, x2, y2, stroke=INK, sw=1.4, dash=None, extra='', opacity=None):
    d = f' stroke-dasharray="{dash}"' if dash else ''
    op = f' opacity="{opacity}"' if opacity is not None else ''
    return f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{stroke}" stroke-width="{sw}"{d}{op} {extra}/>'


def text(x, y, s, size=14, fill=INK, anchor='start', weight='600', family=FONT_BODY, spacing=None, extra=''):
    ls = f' letter-spacing="{spacing}"' if spacing else ''
    return f'<text x="{x}" y="{y}" font-size="{size}" fill="{fill}" text-anchor="{anchor}" font-weight="{weight}" font-family="{family}"{ls} {extra}>{_esc(s)}</text>'


def poly(points, fill, stroke=INK, sw=1.6, extra=''):
    pts = ' '.join(f'{px},{py}' for px, py in points)
    return f'<polygon points="{pts}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}" {extra}/>'


def path(d, fill='none', stroke=INK, sw=1.6, extra=''):
    return f'<path d="{d}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}" {extra}/>'


def circle(cx, cy, r, fill, stroke=INK, sw=1.6, extra=''):
    return f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}" {extra}/>'


def ellipse(cx, cy, rx, ry, fill, stroke=INK, sw=1.4, extra=''):
    return f'<ellipse cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}" {extra}/>'


# ---------------------------------------------------------------- defs ----
def hatch_defs():
    return (
        '<defs>'
        '<pattern id="hatch" width="6" height="6" patternTransform="rotate(45)" patternUnits="userSpaceOnUse">'
        f'<line x1="0" y1="0" x2="0" y2="6" stroke="{HATCH_COL}" stroke-width="1"/>'
        '</pattern>'
        '<pattern id="hatchBlue" width="7" height="7" patternTransform="rotate(45)" patternUnits="userSpaceOnUse">'
        f'<line x1="0" y1="0" x2="0" y2="7" stroke="{BLUEPRINT}" stroke-width="1" opacity="0.30"/>'
        '</pattern>'
        '</defs>'
    )


# --------------------------------------------------------------- frame ----
def sheet_frame(W, H, margin=16, grid_step=24):
    parts = [rect(0, 0, W, H, PAPER, stroke='none')]
    # faint reference grid
    x = margin
    while x <= W - margin:
        parts.append(line(x, margin, x, H - margin, stroke=INK, sw=0.5, opacity=GRID_OPACITY))
        x += grid_step
    y = margin
    while y <= H - margin:
        parts.append(line(margin, y, W - margin, y, stroke=INK, sw=0.5, opacity=GRID_OPACITY))
        y += grid_step
    # double rule border
    parts.append(rect(margin, margin, W - 2 * margin, H - 2 * margin, 'none', stroke=INK, sw=2.4))
    parts.append(rect(margin + 7, margin + 7, W - 2 * margin - 14, H - 2 * margin - 14, 'none', stroke=INK, sw=0.8))
    # corner registration ticks
    tick = 18
    for cx0, cy0, dx, dy in [(margin, margin, 1, 1), (W - margin, margin, -1, 1),
                              (margin, H - margin, 1, -1), (W - margin, H - margin, -1, -1)]:
        parts.append(line(cx0 - dx * 6, cy0, cx0 + dx * tick, cy0, stroke=INK, sw=1.6))
        parts.append(line(cx0, cy0 - dy * 6, cx0, cy0 + dy * tick, stroke=INK, sw=1.6))
    return '\n'.join(parts)


# --------------------------------------------------------- mission patch --
def mission_insignia(cx, cy, r=27):
    parts = [circle(cx, cy, r, PANEL, stroke=INK, sw=1.8)]
    parts.append(circle(cx, cy, r - 6, 'none', stroke=BLUEPRINT, sw=1.1))
    # rocket silhouette
    nose_y = cy - r + 13
    parts.append(poly([(cx - 1.5, nose_y), (cx + 1.5, nose_y), (cx + 5, cy + 8), (cx - 5, cy + 8)], fill=INK))
    parts.append(poly([(cx - 5, cy + 8), (cx - 9, cy + 15), (cx - 4, cy + 11)], fill=SAFETY_RED))
    parts.append(poly([(cx + 5, cy + 8), (cx + 9, cy + 15), (cx + 4, cy + 11)], fill=SAFETY_RED))
    parts.append(ellipse(cx, cy + 1, r - 11, 6.5, 'none', stroke=INK, sw=1, extra=f'transform="rotate(-20 {cx} {cy+1})"'))
    parts.append(text(cx, cy + r + 12, 'PERSEUS \u00b7 I', size=8.5, fill=INK, anchor='middle', weight='800', family=FONT_HEAD, spacing='1.5'))
    return '\n'.join(parts)


# ----------------------------------------------------------- title block --
def title_block(x, y, w, h, cells):
    """cells: list of (width, [(text, size, weight, family, fill), ...]) stacked top->bottom per cell."""
    parts = [rect(x, y, w, h, PANEL, stroke=INK, sw=1.6)]
    cx = x
    for i, (cw, lines) in enumerate(cells):
        if i > 0:
            parts.append(line(cx, y, cx, y + h, stroke=INK, sw=1.1))
        ty = y + 18
        for item in lines:
            s, size, weight, family, fill = item
            parts.append(text(cx + 13, ty, s, size=size, fill=fill, weight=weight, family=family))
            ty += size + 7
        cx += cw
    return '\n'.join(parts)


# --------------------------------------------------------- balloon/leader --
def balloon(x, y, num, r=11, accent=INK):
    return '\n'.join([
        circle(x, y, r, PANEL, stroke=accent, sw=1.6),
        text(x, y + 4, str(num), size=11.5, fill=accent, anchor='middle', weight='800', family=FONT_MONO),
    ])


def leader(x1, y1, elbow_x, y2, x2, stroke=INK):
    """Two-segment leader line: part -> elbow -> balloon, NASA-drawing style."""
    return '\n'.join([
        line(x1, y1, elbow_x, y2, stroke=stroke, sw=1.1),
        line(elbow_x, y2, x2, y2, stroke=stroke, sw=1.1),
    ])


def stage_badge(x, y, num, fill=BLUEPRINT, r=17):
    return '\n'.join([
        circle(x, y, r, fill, stroke=PAPER, sw=2),
        text(x, y + 5, str(num), size=14, fill=PANEL, anchor='middle', weight='800', family=FONT_MONO),
    ])


def dim_line_vertical(x, y1, y2, label, side=-1):
    """Vertical dimension line with arrowheads + perpendicular end-ticks, label rotated alongside."""
    parts = [line(x, y1, x, y2, stroke=INK, sw=1.1)]
    aw = 5
    parts.append(poly([(x, y1), (x - aw, y1 + aw * 1.8), (x + aw, y1 + aw * 1.8)], fill=INK))
    parts.append(poly([(x, y2), (x - aw, y2 - aw * 1.8), (x + aw, y2 - aw * 1.8)], fill=INK))
    parts.append(line(x - 8 * side, y1, x + 8 * (1 if side < 0 else -1) * 0, y1, stroke=INK, sw=1))
    parts.append(line(x - 10, y1, x + 10, y1, stroke=INK, sw=1))
    parts.append(line(x - 10, y2, x + 10, y2, stroke=INK, sw=1))
    mid = (y1 + y2) / 2
    parts.append(text(x + side * 14, mid, label, size=11.5, fill=INK, anchor='middle', weight='700',
                       family=FONT_MONO, extra=f'transform="rotate(-90 {x+side*14} {mid})"'))
    return '\n'.join(parts)
