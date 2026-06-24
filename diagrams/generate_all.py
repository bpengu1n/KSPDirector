"""
Perseus 1 -- NASA-style technical reference sheets (KSP mission-pack appendix)
Sheet 1: Vehicle General Arrangement
Sheet 2: Stage Separation Sequence
Sheet 3: Ascent Guidance Program
Sheet 4: Ascent Contingency & Abort Criteria
"""
from pathlib import Path
import math

OUT = Path('/opt/data')

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

def engine_bell(cx, top_y, throat_w, bottom_w, h, hatch=True):
    x1, x2 = cx - throat_w / 2, cx + throat_w / 2
    xb1, xb2 = cx - bottom_w / 2, cx + bottom_w / 2
    pts = [(x1, top_y), (x2, top_y), (xb2 - 10, top_y + h - 10), (xb2, top_y + h),
           (xb1, top_y + h), (xb1 + 10, top_y + h - 10)]
    parts = [poly(pts, fill=FILL_BASE, stroke=INK, sw=1.6)]
    if hatch:
        parts.append(poly(pts, fill='url(#hatch)', stroke='none'))
    parts.append(line(x1, top_y, x2, top_y, stroke=INK, sw=1.6))
    return '\n'.join(parts)


def part_pod(cx, y):
    parts = []
    pts = [(cx - 44, y + 86), (cx - 28, y + 34), (cx, y), (cx + 28, y + 34), (cx + 44, y + 86)]
    parts.append(poly(pts, fill=FILL_BASE, stroke=INK, sw=1.8))
    parts.append(rect(cx - 26, y + 32, 52, 40, PANEL, stroke=INK, sw=1.3, rx=6))
    parts.append(path(f'M {cx-18} {y+42} Q {cx} {y+24} {cx+18} {y+42}', stroke=BLUEPRINT, sw=2.2))
    parts.append(text(cx, y + 58, 'MK1', size=11.5, fill=INK, anchor='middle', weight='800', family=FONT_MONO))
    return '\n'.join(parts)


def part_parachute(cx, y):
    parts = []
    pts = [(cx - 45, y + 28), (cx - 30, y + 8), (cx, y), (cx + 30, y + 8), (cx + 45, y + 28), (cx + 40, y + 42), (cx - 40, y + 42)]
    parts.append(poly(pts, fill=FILL_BASE, stroke=INK, sw=1.7))
    parts.append(poly(pts, fill='url(#hatch)', stroke='none'))
    for dx in (-24, -8, 8, 24):
        parts.append(line(cx + dx, y + 42, cx, y + 66, stroke=INK_SOFT, sw=1.0))
    parts.append(text(cx, y + 84, 'MK16', size=11, fill=INK, anchor='middle', weight='800', family=FONT_MONO))
    return '\n'.join(parts)


def part_heat_shield(cx, y):
    pts = [(cx - 54, y + 10), (cx + 54, y + 10), (cx + 42, y + 42), (cx - 42, y + 42)]
    return '\n'.join([
        poly(pts, fill=FILL_BASE, stroke=INK, sw=1.7),
        poly(pts, fill='url(#hatch)', stroke='none'),
        text(cx, y + 30, '1.25M HEAT SHIELD', size=9, fill=INK, anchor='middle', weight='800', family=FONT_MONO),
    ])


def part_decoupler(cx, y, w=120, h=18):
    return '\n'.join([
        rect(cx - w / 2, y, w, h, PANEL, stroke=INK, sw=1.6, rx=3),
        text(cx, y + 12.5, 'TR-18A', size=9.5, fill=INK, anchor='middle', weight='800', family=FONT_MONO),
    ])


def part_avionics(cx, y, w=104, h=30):
    """Slim inline avionics ring: reaction wheel + battery."""
    return '\n'.join([
        rect(cx - w / 2, y, w, h, PANEL, stroke=INK, sw=1.6, rx=4),
        line(cx - w / 2 + 10, y + h / 2, cx + w / 2 - 10, y + h / 2, stroke=INK_SOFT, sw=1, dash='4 4'),
        text(cx, y + h / 2 + 3.5, 'RW + BATT', size=8.5, fill=INK, anchor='middle', weight='800', family=FONT_MONO),
    ])


def part_service_bay(cx, y, w=132, h=72):
    """Inline service bay; dashed interior implies stowed contents on centerline."""
    parts = [rect(cx - w / 2, y, w, h, FILL_BASE, stroke=INK, sw=1.7, rx=10)]
    # door seam down the middle
    parts.append(line(cx, y + 6, cx, y + h - 6, stroke=INK_SOFT, sw=1.1, dash='5 4'))
    # stowed-contents hint: two faint rounded blocks inside
    parts.append(rect(cx - w / 2 + 16, y + 14, w / 2 - 26, h - 28, PANEL, stroke=INK_FAINT, sw=1, rx=3, opacity=0.6))
    parts.append(rect(cx + 6, y + 14, w / 2 - 26, h - 28, PANEL, stroke=INK_FAINT, sw=1, rx=3, opacity=0.6))
    parts.append(text(cx, y + h / 2 + 3, 'SERVICE BAY', size=8.5, fill=INK, anchor='middle', weight='800', family=FONT_MONO))
    return '\n'.join(parts)


def part_tank(cx, y, w, h, fill, title, subtitle=''):
    parts = [rect(cx - w / 2, y, w, h, fill, stroke=INK, sw=1.7, rx=12)]
    parts.append(line(cx - w / 2 + 12, y + 15, cx + w / 2 - 12, y + 15, stroke=INK, sw=1, dash='9 6', opacity=0.45))
    parts.append(line(cx - w / 2 + 12, y + h - 15, cx + w / 2 - 12, y + h - 15, stroke=INK, sw=1, dash='9 6', opacity=0.45))
    parts.append(text(cx, y + h / 2 - 2, title, size=13.5, fill=INK, anchor='middle', weight='800', family=FONT_MONO))
    if subtitle:
        parts.append(text(cx, y + h / 2 + 16, subtitle, size=9.5, fill=INK_SOFT, anchor='middle', weight='600', family=FONT_MONO))
    return '\n'.join(parts)


def part_swivel(cx, y):
    parts = [engine_bell(cx, y + 18, 44, 86, 92)]
    parts.append(rect(cx - 34, y, 68, 20, FILL_BLUE, stroke=INK, sw=1.7, rx=5))
    parts.append(line(cx, y + 10, cx, y + 100, stroke=INK_SOFT, sw=1, dash='4 4'))
    parts.append(path(f'M {cx-34} {y+22} L {cx-54} {y+48}', stroke=INK_SOFT, sw=3))
    parts.append(path(f'M {cx+34} {y+22} L {cx+54} {y+48}', stroke=INK_SOFT, sw=3))
    parts.append(text(cx, y + 54, 'LV-T45', size=10.5, fill=INK, anchor='middle', weight='800', family=FONT_MONO))
    parts.append(text(cx, y + 68, 'SWIVEL', size=10.5, fill=INK, anchor='middle', weight='800', family=FONT_MONO))
    return '\n'.join(parts)


def part_terrier(cx, y):
    parts = [rect(cx - 28, y, 56, 18, FILL_BLUE, stroke=INK, sw=1.6, rx=5)]
    parts.append(engine_bell(cx, y + 18, 30, 58, 70))
    parts.append(text(cx, y + 44, 'LV-909', size=9.5, fill=INK, anchor='middle', weight='800', family=FONT_MONO))
    parts.append(text(cx, y + 57, 'TERRIER', size=9.5, fill=INK, anchor='middle', weight='800', family=FONT_MONO))
    return '\n'.join(parts)


def part_nose_cone(cx, y, w=17, h=26):
    """y is the base (attachment point, sits on the booster tip); cone extends upward by h."""
    pts = [(cx - w / 2, y), (cx, y - h), (cx + w / 2, y)]
    parts = [poly(pts, fill=FILL_BASE, stroke=INK, sw=1.5)]
    parts.append(poly(pts, fill='url(#hatch)', stroke='none'))
    return '\n'.join(parts)


def part_hammer_pair(cx, swivel_nozzle_y, body_h=154, bell_h=34):
    """Hammers are positioned so their nozzle EXITS sit at swivel_nozzle_y --
    i.e. level with the Swivel's nozzle exit, never hanging below it. This keeps
    the booster bodies high against the core tank and out of the Swivel's exhaust
    plume (avoids plume-impingement heat damage during ascent).
    """
    # build upward from the nozzle exit
    bell_top_y = swivel_nozzle_y - bell_h
    body_bottom_y = bell_top_y
    y = body_bottom_y - body_h          # body top (sits up on the core tank)

    # inner brace block between boosters (kept near the core, upper region)
    parts = [rect(cx - 24, y + 34, 48, 86, FILL_BLUE_DK, stroke=INK, sw=1.7, rx=8)]
    for side in (-1, 1):
        x = cx + side * 82
        inward = -side
        parts.append(rect(x - 24, y, 48, body_h, FILL_BASE, stroke=INK, sw=1.7, rx=10))
        parts.append(poly([(x - 24, y + 16), (x, y), (x + 24, y + 16)], fill=FILL_BASE, stroke=INK, sw=1.4))
        parts.append(part_nose_cone(x, y))
        parts.append(engine_bell(x, bell_top_y, 20, 38, bell_h))
        parts.append(text(x, y + 84, 'HAMMER', size=9.5, fill=INK, anchor='middle', weight='800', family=FONT_MONO,
                           extra='transform="rotate(90 {} {})"'.format(x, y + 84)))
        inner_x = x + inward * 24
        puck_w, puck_h = 15, 25
        puck_x = inner_x if inward > 0 else inner_x - puck_w
        parts.append(rect(puck_x, y + 24, puck_w, puck_h, PANEL, stroke=SAFETY_RED, sw=1.4, rx=3))
        parts.append(line(inner_x, y + 24 + puck_h / 2, inner_x + inward * 18, y + 24 + puck_h / 2, stroke=SAFETY_RED, sw=1.2, dash='3 3'))
    return '\n'.join(parts), y   # return the body-top y so the caller can place balloons/badges


def part_fins(cx, y, outer_only=False):
    pts_sets = [
        [(cx - 112, y + 14), (cx - 70, y), (cx - 72, y + 50), (cx - 112, y + 58)],
        [(cx + 112, y + 14), (cx + 70, y), (cx + 72, y + 50), (cx + 112, y + 58)],
    ]
    if not outer_only:
        pts_sets += [
            [(cx - 34, y + 20), (cx - 6, y + 4), (cx - 8, y + 40), (cx - 34, y + 48)],
            [(cx + 34, y + 20), (cx + 6, y + 4), (cx + 8, y + 40), (cx + 34, y + 48)],
        ]
    out = []
    for p in pts_sets:
        out.append(poly(p, fill=FILL_BASE, stroke=INK, sw=1.5))
        out.append(poly(p, fill='url(#hatch)', stroke='none'))
    return '\n'.join(out)


PARTS_LIST = [
    ('1', 'MK16 PARACHUTE', '0.10 T', 'DEPLOY 350M ASL'),
    ('2', 'MK1 COMMAND POD', '0.84 T', 'CREW: 1'),
    ('3', 'REACTION WHEEL + BATTERY', '~0.10 T', 'INLINE, ATTITUDE/POWER'),
    ('4', '1.25M HEAT SHIELD', '0.10 T', 'ABLATIVE, ATMO ENTRY'),
    ('5', 'TR-18A STACK DECOUPLER (X2)', '0.05 T EA', 'PYROTECHNIC SEPARATION'),
    ('6', '1.25M SERVICE BAY', '~0.10 T', 'HOUSES ITEMS 7-8, CENTERLINE'),
    ('7', 'TELEMACHUS ANTENNA', 'IN BAY', 'STOWED FOR LAUNCH/ENTRY'),
    ('8', 'FUEL CELL ARRAY (6)', 'IN BAY', 'SUSTAINED POWER'),
    ('9', 'FL-T800 FUEL TANK (X2)', '4.50 T EA', 'LF/OX, 0.50 T DRY'),
    ('10', 'LV-909 "TERRIER"', '0.50 T', '60 KN VAC, UPPER STAGE'),
    ('11', 'LV-T45 "SWIVEL"', '1.50 T', '200 KN VAC, GIMBALLED'),
    ('12', 'TT-38K RADIAL DECOUPLER (X2)', '0.03 T EA', 'PYROTECHNIC SEPARATION'),
    ('13', 'RT-10 "HAMMER" SRB (X2)', '0.75 T EA', '227 KN, SOLID FUEL'),
    ('14', 'AERODYNAMIC NOSE CONE (X2)', '0.03 T EA', 'DRAG REDUCTION, BOOSTER TOP'),
    ('15', 'BASIC FIN (X4)', '0.08 T EA', 'PASSIVE AERO STABILITY'),
]


def parts_list_table(x, y, w, rows):
    row_h = 32
    col_item, col_name, col_mass = 40, 248, 110
    col_notes = w - col_item - col_name - col_mass
    parts = [rect(x, y, w, row_h * (len(rows) + 1), PANEL, stroke=INK, sw=1.6)]
    headers = [('ITEM', col_item), ('NOMENCLATURE', col_name), ('MASS', col_mass), ('NOTES', col_notes)]
    cx = x
    for h, cw in headers:
        parts.append(text(cx + 8, y + 20, h, size=9.5, fill=INK_FAINT, weight='800', family=FONT_MONO, spacing='0.5'))
        cx += cw
    parts.append(line(x, y + row_h, x + w, y + row_h, stroke=INK, sw=1.3))
    cx = x
    for h, cw in headers[:-1]:
        cx += cw
        parts.append(line(cx, y, cx, y + row_h * (len(rows) + 1), stroke=INK, sw=0.7, opacity=0.35))
    for i, (num, name, mass, note) in enumerate(rows):
        ry = y + row_h * (i + 1)
        parts.append(text(x + 8, ry + 21, num, size=10.5, fill=BLUEPRINT, weight='800', family=FONT_MONO))
        parts.append(text(x + col_item + 8, ry + 21, name, size=10, fill=INK, weight='700', family=FONT_MONO))
        parts.append(text(x + col_item + col_name + 8, ry + 21, mass, size=10, fill=INK, weight='600', family=FONT_MONO))
        parts.append(text(x + col_item + col_name + col_mass + 8, ry + 21, note, size=9, fill=INK_SOFT, weight='500', family=FONT_MONO))
        if i > 0:
            parts.append(line(x, ry, x + w, ry, stroke=INK, sw=0.6, opacity=0.3))
    return '\n'.join(parts)


def plan_view_inset(cx, cy, R=120):
    """Plan view looking down the roll axis: shows radial clocking of boosters and fins.
    Boosters at 3 and 9 o'clock (matching the side elevation); fins at the 4 diagonals,
    mounted on the core. Disambiguates 'where exactly do the fins go'."""
    import math as _m
    out = []
    # title + section label
    out.append(text(cx, cy - R - 34, 'VIEW A-A', size=12, fill=BLUEPRINT, weight='800', family=FONT_HEAD, spacing='1'))
    out.append(text(cx, cy - R - 18, 'PLAN \u2014 LOOKING DOWN ROLL AXIS', size=8.5, fill=INK_FAINT, weight='700', family=FONT_MONO, spacing='0.5'))

    # outer reference circle (envelope)
    out.append(circle(cx, cy, R, 'none', stroke=INK_FAINT, sw=1))
    # crosshair / clocking reference
    out.append(line(cx - R - 8, cy, cx + R + 8, cy, stroke=INK_FAINT, sw=0.8, dash='3 4'))
    out.append(line(cx, cy - R - 8, cx, cy + R + 8, stroke=INK_FAINT, sw=0.8, dash='3 4'))

    # core tank (center circle)
    core_r = 30
    out.append(circle(cx, cy, core_r, FILL_BLUE_DK, stroke=INK, sw=1.6))
    out.append(circle(cx, cy, core_r, 'url(#hatchBlue)', stroke='none'))
    out.append(text(cx, cy + 3, 'CORE', size=7.5, fill=INK, anchor='middle', weight='800', family=FONT_MONO))

    # boosters at 3 and 9 o'clock
    b_r = 20
    for ang in (0, 180):
        bx = cx + (core_r + b_r + 6) * _m.cos(_m.radians(ang))
        by = cy - (core_r + b_r + 6) * _m.sin(_m.radians(ang))
        out.append(circle(bx, by, b_r, FILL_BASE, stroke=INK, sw=1.5))
        out.append(circle(bx, by, b_r, 'url(#hatch)', stroke='none'))
        out.append(text(bx, by + 2.5, 'SRB', size=6.5, fill=INK, anchor='middle', weight='800', family=FONT_MONO))

    # fins at the 4 diagonals (45, 135, 225, 315), mounted on the core, pointing outward
    for ang in (45, 135, 225, 315):
        a = _m.radians(ang)
        root_x = cx + core_r * _m.cos(a)
        root_y = cy - core_r * _m.sin(a)
        tip_x = cx + (core_r + 34) * _m.cos(a)
        tip_y = cy - (core_r + 34) * _m.sin(a)
        # small wedge fin
        perp = _m.radians(ang + 90)
        wx, wy = 7 * _m.cos(perp), -7 * _m.sin(perp)
        pts = [(root_x + wx, root_y + wy), (root_x - wx, root_y - wy), (tip_x, tip_y)]
        out.append(poly(pts, fill=FILL_BASE, stroke=INK, sw=1.4))
        out.append(poly(pts, fill='url(#hatch)', stroke='none'))

    # callout
    out.append(text(cx, cy + R + 22, '4X FIN ON CORE TANK \u2014 90\u00b0 SYMMETRIC,', size=8, fill=INK_SOFT, anchor='middle', weight='700', family=FONT_MONO))
    out.append(text(cx, cy + R + 33, 'CLOCKED 45\u00b0 OFF THE BOOSTERS', size=8, fill=INK_SOFT, anchor='middle', weight='700', family=FONT_MONO))
    return '\n'.join(out)


def build_sheet1():
    W, H = 1280, 1540
    margin = 16
    cx = 300
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">']
    out.append(hatch_defs())
    out.append(sheet_frame(W, H, margin))

    # ---- header
    out.append(mission_insignia(margin + 50, 76, r=29))
    out.append(text(150, 56, 'PERSEUS 1 \u00b7 MISSION PACK \u00b7 APPENDIX A', size=10.5, fill=BLUEPRINT, weight='800', family=FONT_HEAD, spacing='1.2'))
    out.append(text(150, 96, 'VEHICLE GENERAL ARRANGEMENT', size=30, fill=INK, weight='800', family=FONT_HEAD))
    out.append(text(150, 122, 'Stock-part stack \u00b7 NASA reference-sheet format \u00b7 see Sheet 2 for stage separation sequence', size=12.5, fill=INK_SOFT, weight='500'))
    out.append(line(margin + 24, 140, W - margin - 24, 140, stroke=INK, sw=1.3))

    # ---- centerline + dimension
    out.append(line(cx, 186, cx, 1404, stroke=INK_FAINT, sw=1, dash='2 6'))
    out.append(dim_line_vertical(44, 196, 1388, '\u2248 8.0 M OAL \u00b7 CORE STACK'))

    y = 196
    balloons = []  # (num, anchor_x, anchor_y, by)

    out.append(part_parachute(cx, y))
    balloons.append(('1', cx + 45, y + 22, y + 40))
    y += 96

    out.append(part_pod(cx, y))
    balloons.append(('2', cx + 44, y + 50, y + 43))
    y += 106

    out.append(part_avionics(cx, y))
    balloons.append(('3', cx + 56, y + 15, y + 15))
    y += 40

    out.append(part_heat_shield(cx, y))
    balloons.append(('4', cx + 54, y + 26, y + 28))
    y += 58

    out.append(part_decoupler(cx, y))
    out.append(line(170, y + 9, 460, y + 9, stroke=SAFETY_RED, sw=1.8, dash='7 6'))
    out.append(stage_badge(95, y + 9, 1, fill=SAFETY_RED))
    balloons.append(('5', cx + 60, y + 9, y + 9))
    y += 34

    out.append(part_service_bay(cx, y))
    balloons.append(('6', cx + 76, y + 24, y + 18))
    balloons.append(('7', cx + 76, y + 40, y + 44))
    balloons.append(('8', cx + 76, y + 56, y + 70))
    y += 84

    out.append(part_tank(cx, y, 140, 184, FILL_BLUE, 'FL-T800', 'mission stage'))
    out.append(stage_badge(95, y + 92, 2, fill=TEAL))
    balloons.append(('9', cx + 70, y + 70, y + 60))
    y += 192

    out.append(part_terrier(cx, y))
    balloons.append(('10', cx + 29, y + 44, y + 46))
    y += 98

    out.append(part_decoupler(cx, y))
    out.append(line(170, y + 9, 460, y + 9, stroke=SAFETY_RED, sw=1.8, dash='7 6'))
    out.append(stage_badge(95, y + 9, 3, fill=SAFETY_RED))
    balloons.append(('5', cx + 60, y + 9, y + 9))
    y += 34

    out.append(part_tank(cx, y, 140, 184, FILL_BLUE_DK, 'FL-T800', 'launch core'))
    balloons.append(('9', cx + 70, y + 80, y + 76))
    y += 192

    out.append(part_swivel(cx, y))
    balloons.append(('11', cx + 34, y + 44, y + 34))
    swivel_nozzle_y = y + 110   # Swivel bell: top at y+18, height 92

    hammer_svg, htop = part_hammer_pair(cx, swivel_nozzle_y)
    out.append(hammer_svg)
    # stage badges keyed to the booster geometry
    out.append(stage_badge(95, htop + 90, 4, fill=VIOLET))
    out.append(line(170, htop + 90, 460, htop + 90, stroke=VIOLET, sw=1.8, dash='7 6'))
    out.append(stage_badge(95, swivel_nozzle_y + 70, 5, fill=BLUEPRINT))
    # booster callouts: 14 nose cone (top), 12 radial decoupler (inner puck), 13 hammer body
    balloons.append(('14', cx + 82, htop - 20, htop - 14))
    balloons.append(('12', cx + 58, htop + 36, htop + 30))
    balloons.append(('13', cx + 106, htop + 96, htop + 120))

    # fins shown at the base in side elevation; precise radial arrangement is given
    # in the VIEW A-A plan inset (drawn below), which disambiguates mount clocking.
    fin_y = swivel_nozzle_y - 80
    out.append(part_fins(cx, fin_y, outer_only=True))
    balloons.append(('15', cx + 120, fin_y + 30, fin_y + 26))

    # section-cut indicator A-A at the fin/core level (references the plan inset)
    sec_y = fin_y + 30
    out.append(line(cx - 175, sec_y, cx - 132, sec_y, stroke=BLUEPRINT, sw=1.4))
    out.append(text(cx - 188, sec_y + 4, 'A', size=11, fill=BLUEPRINT, anchor='middle', weight='800', family=FONT_HEAD))
    out.append(text(cx - 158, sec_y - 6, 'SECTION', size=6.5, fill=INK_FAINT, anchor='middle', weight='700', family=FONT_MONO))

    # nozzle-plane alignment cue + plume-clearance note (this alignment was previously ambiguous)
    out.append(line(cx - 150, swivel_nozzle_y, cx + 150, swivel_nozzle_y, stroke=TEAL, sw=1.1, dash='4 4'))
    out.append(text(cx, swivel_nozzle_y + 24, 'NOZZLE EXIT PLANE \u2014 ALIGN HAMMER & SWIVEL', size=7.8, fill=TEAL, anchor='middle', weight='800', family=FONT_MONO, spacing='0.3'))
    out.append(text(cx, swivel_nozzle_y + 38, 'MOUNT HAMMERS WITH NOZZLES AT OR ABOVE THE SWIVEL BELL;', size=7.8, fill=SAFETY_RED, anchor='middle', weight='700', family=FONT_MONO))
    out.append(text(cx, swivel_nozzle_y + 49, 'KEEP TOPS HIGH ON CORE TANK TO CLEAR EXHAUST PLUME', size=7.8, fill=SAFETY_RED, anchor='middle', weight='700', family=FONT_MONO))

    # ---- balloons + leaders (drawn after geometry so they sit on top)
    elbow_x, bx = 465, 497
    for num, ax, ay, by in balloons:
        out.append(leader(ax, ay, elbow_x, by, bx - 11))
        out.append(balloon(bx, by, num))

    # ---- parts list
    out.append(parts_list_table(560, 196, 620, PARTS_LIST))
    out.append(text(560, 186, 'PARTS LIST \u2014 REFERENCE DATA, STOCK COMPONENTS', size=10, fill=INK_FAINT, weight='800', family=FONT_MONO, spacing='0.5'))

    # ---- notes (placed in the open area under the parts-list table)
    notes_y = 748
    out.append(text(560, notes_y, 'NOTES', size=12, fill=BLUEPRINT, weight='800', family=FONT_HEAD, spacing='1'))
    notes = [
        'Drawing is schematic (NTS) \u2014 dimensions and masses are stock-part reference values, not drawn to scale.',
        'Both FL-T800 tanks share item no. 9; both TR-18A decouplers share item no. 5 (see parts list).',
        'Items 7-8 (antenna, fuel cells) are stowed inside the service bay (item 6) on the centerline.',
        'Dashed red lines mark pyrotechnic stack-separation planes; see Sheet 2 for full staging sequence.',
        'Fin radial clocking (4X on core tank, 45\u00b0 off boosters): see VIEW A-A.',
    ]
    for i, n in enumerate(notes):
        out.append(text(560, notes_y + 24 + i * 19, '\u2022 ' + n, size=11, fill=INK_SOFT, weight='500'))

    # ---- VIEW A-A : plan view (looking down the roll axis) to disambiguate radial mounting
    out.append(plan_view_inset(760, 1080, R=120))

    # ---- title block
    tb_h = 70
    tb_y = H - margin - tb_h
    tb_w = W - 2 * margin
    c1, c3, c4 = 150, 190, 150
    c2 = tb_w - c1 - c3 - c4 - 150
    cells = [
        (c1, [('PERSEUS 1', 9, '800', FONT_HEAD, INK_SOFT), ('MISSION PACK', 9, '800', FONT_HEAD, INK_SOFT)]),
        (c2, [('VEHICLE GENERAL ARRANGEMENT', 13, '800', FONT_BODY, INK), ('Kerbal Space Program \u2014 mission documentation appendix', 9.5, '500', FONT_BODY, INK_SOFT)]),
        (c3, [('DWG NO', 8, '700', FONT_MONO, INK_FAINT), ('KSP-PRS1-GA-01', 12, '700', FONT_MONO, INK)]),
        (c4, [('SCALE', 8, '700', FONT_MONO, INK_FAINT), ('NTS', 12, '700', FONT_MONO, INK)]),
        (150, [('SHEET', 8, '700', FONT_MONO, INK_FAINT), ('1 OF 4  REV A', 12, '700', FONT_MONO, INK)]),
    ]
    out.append(title_block(margin, tb_y, tb_w, tb_h, cells))

    out.append('</svg>')
    return '\n'.join(out)

STAGES = [
    ('5', 'LIFTOFF STACK', BLUEPRINT, ['MK16 PARACHUTE', 'MK1 COMMAND POD', '1.25M HEAT SHIELD',
                                       '2X FL-T800 + TERRIER/SWIVEL', '2X HAMMER (NOSE CONE) + FINS']),
    ('4', 'BOOSTER JETTISON', VIOLET, ['RADIAL HAMMERS RELEASED', 'CORE STACK REMAINS INTACT', 'SWIVEL CONTINUES ASCENT']),
    ('3', 'CORE SEPARATION', SAFETY_RED, ['SPENT LOWER FL-T800 DROPPED', 'SWIVEL DISCARDED', 'TERRIER ASSUMES PROPULSION']),
    ('2', 'MISSION STAGE', TEAL, ['FL-T800 + TERRIER ACTIVE', 'CAPSULE STACK REMAINS MATED', 'USED FOR ORBIT, TMI, TRIM']),
    ('1', 'ENTRY CONFIG', SAFETY_RED, ['MISSION STAGE JETTISONED', 'CAPSULE + HEAT SHIELD KEPT', 'PARACHUTE ARMED FOR RECOVERY']),
]
CUES = ['BOOSTER SEP', 'CORE SEP', 'MISSION HANDOFF', 'ENTRY SEP']

SEQ_BARS = [
    ('5 // LIFTOFF ASSEMBLY', BLUEPRINT, 'pod + mission stage + launch core + boosters'),
    ('4 // BOOSTER SEP', VIOLET, 'core + mission stage continue under Swivel only'),
    ('3 // CORE SEP', SAFETY_RED, 'mission stage isolated with Terrier propulsion'),
    ('2 // MISSION STAGE', TEAL, 'orbit, TMI, flyby, trim before final separation'),
    ('1 // RECOVERY STACK', SAFETY_RED, 'capsule + heat shield + chute \u2014 final config'),
]


def stage_card(x, y, w, h, num, title, accent, items):
    parts = [rect(x, y, w, h, PANEL, stroke=accent, sw=1.8, rx=10)]
    parts.append(stage_badge(x + 24, y + 25, num, fill=accent, r=15))
    parts.append(text(x + 48, y + 30, title, size=13.5, fill=INK, weight='800', family=FONT_HEAD))
    parts.append(line(x + 16, y + 44, x + w - 16, y + 44, stroke=accent, sw=1, opacity=0.5))
    for i, item in enumerate(items):
        parts.append(text(x + 18, y + 66 + i * 19, '\u2022 ' + item, size=9.5, fill=INK_SOFT, weight='600', family=FONT_MONO))
    return '\n'.join(parts)


def mini_legend_table(x, y, w, rows):
    """rows: (badge_num, accent, label) -- compact 2-col reference used in the cut-line panel."""
    row_h = 26
    parts = []
    for i, (num, accent, label) in enumerate(rows):
        ry = y + i * row_h
        parts.append(stage_badge(x + 12, ry + 12, num, fill=accent, r=11))
        parts.append(text(x + 32, ry + 16, label, size=10.5, fill=accent, weight='800', family=FONT_MONO))
    return '\n'.join(parts)


def recovery_spec_table(x, y, rows):
    parts = []
    for i, (label, val) in enumerate(rows):
        ry = y + i * 22
        parts.append(text(x, ry, label, size=10.5, fill=INK_SOFT, weight='600', family=FONT_MONO))
        parts.append(text(x + 150, ry, val, size=10.5, fill=INK, weight='700', family=FONT_MONO, anchor='end'))
    return '\n'.join(parts)


def build_sheet2():
    W, H = 1400, 1080
    margin = 16
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">']
    out.append(hatch_defs())
    out.append(sheet_frame(W, H, margin))

    # ---- header
    out.append(mission_insignia(margin + 50, 76, r=29))
    out.append(text(150, 56, 'PERSEUS 1 \u00b7 MISSION PACK \u00b7 APPENDIX A', size=10.5, fill=BLUEPRINT, weight='800', family=FONT_HEAD, spacing='1.2'))
    out.append(text(150, 96, 'STAGE SEPARATION SEQUENCE', size=30, fill=INK, weight='800', family=FONT_HEAD))
    out.append(text(150, 122, 'Exploded configuration states, flight order \u00b7 companion to Sheet 1 general arrangement', size=12.5, fill=INK_SOFT, weight='500'))
    out.append(line(margin + 24, 140, W - margin - 24, 140, stroke=INK, sw=1.3))

    # ---- stage cards
    start_x, y0, step_w, gap, card_h = 32, 168, 248, 14, 188
    for i, (num, title, accent, items) in enumerate(STAGES):
        x = start_x + i * (step_w + gap)
        out.append(stage_card(x, y0, step_w, card_h, num, title, accent, items))

    arrow_y = y0 + card_h + 26
    for i in range(len(STAGES) - 1):
        x_from = start_x + i * (step_w + gap) + step_w
        x_to = start_x + (i + 1) * (step_w + gap)
        accent = STAGES[i][2]
        out.append(line(x_from, arrow_y, x_to, arrow_y, stroke=accent, sw=2.6))
        out.append(poly([(x_to, arrow_y), (x_to - 12, arrow_y - 7), (x_to - 12, arrow_y + 7)], fill=accent))
        cue_x = (x_from + x_to) / 2
        out.append(rect(cue_x - 58, arrow_y - 25, 116, 20, PANEL, stroke=accent, sw=1.4, rx=10))
        out.append(text(cue_x, arrow_y - 11, CUES[i], size=9.5, fill=accent, anchor='middle', weight='800', family=FONT_MONO))

    # ---- bottom panel row
    panel_y = arrow_y + 30
    panel_h = 540
    cut_x, cut_w = 32, 350
    seq_x, seq_w = 410, 380
    rec_x, rec_w = 818, W - margin - 24 - 818

    # CUT-LINE REFERENCE
    out.append(rect(cut_x, panel_y, cut_w, panel_h, PANEL, stroke=INK, sw=1.6, rx=8))
    out.append(text(cut_x + 16, panel_y + 26, 'CUT-LINE REFERENCE', size=13, fill=INK, weight='800', family=FONT_HEAD))
    out.append(text(cut_x + 16, panel_y + 44, 'split points \u00b7 retained elements', size=10, fill=INK_SOFT, weight='500'))
    scx = cut_x + 268
    top = panel_y + 70
    out.append(part_parachute(scx, top))
    out.append(part_pod(scx, top + 96))
    out.append(part_heat_shield(scx, top + 204))
    out.append(part_decoupler(scx, top + 260, w=108))
    out.append(part_tank(scx, top + 288, 112, 42, FILL_BLUE, 'FL-T800', 'mission'))
    out.append(part_decoupler(scx, top + 338, w=108))
    out.append(part_tank(scx, top + 366, 112, 42, FILL_BLUE_DK, 'FL-T800', 'core'))
    cutline_bot = top + 408
    out.append(line(cut_x + 26, top, cut_x + 26, cutline_bot, stroke=INK_FAINT, sw=1, dash='3 5'))
    cut_points = [
        (top + 270, '1', SAFETY_RED, 'ENTRY SEP'),
        (top + 350, '3', SAFETY_RED, 'CORE SEP'),
        (top + 404, '4', VIOLET, 'BOOSTER SEP'),
    ]
    for cy, num, accent, label in cut_points:
        out.append(stage_badge(cut_x + 26, cy, num, fill=accent, r=11))
        out.append(text(cut_x + 46, cy + 4, label, size=10.5, fill=accent, weight='800', family=FONT_MONO))

    # STAGE SEQUENCE SUMMARY
    out.append(rect(seq_x, panel_y, seq_w, panel_h, PANEL, stroke=INK, sw=1.6, rx=8))
    out.append(text(seq_x + 16, panel_y + 26, 'STAGE SEQUENCE SUMMARY', size=13, fill=INK, weight='800', family=FONT_HEAD))
    out.append(text(seq_x + 16, panel_y + 44, 'configuration after each separation event', size=10, fill=INK_SOFT, weight='500'))
    bar_y0, bar_h, bar_gap = panel_y + 64, 64, 26
    for i, (title, accent, desc) in enumerate(SEQ_BARS):
        yy = bar_y0 + i * (bar_h + bar_gap)
        out.append(rect(seq_x + 18, yy, seq_w - 36, bar_h, PANEL, stroke=accent, sw=1.6, rx=8))
        out.append(text(seq_x + 30, yy + 24, title, size=12, fill=INK, weight='800', family=FONT_MONO))
        out.append(text(seq_x + 30, yy + 44, desc, size=9.5, fill=INK_SOFT, weight='500', family=FONT_MONO))

    # POST-STAGE-1 RECOVERY VEHICLE
    out.append(rect(rec_x, panel_y, rec_w, panel_h, PANEL, stroke=INK, sw=1.6, rx=8))
    out.append(text(rec_x + 16, panel_y + 26, 'POST-STAGE-1 RECOVERY VEHICLE', size=13, fill=INK, weight='800', family=FONT_HEAD))
    out.append(text(rec_x + 16, panel_y + 44, 'retained configuration, Kerbin atmospheric entry', size=10, fill=INK_SOFT, weight='500'))
    rcx = rec_x + 100
    out.append(part_parachute(rcx, panel_y + 74))
    out.append(part_pod(rcx, panel_y + 206))
    out.append(part_heat_shield(rcx, panel_y + 346))
    spec_x = rec_x + 220
    out.append(recovery_spec_table(spec_x, panel_y + 110, [
        ('MK16 CHUTE', '0.10 T'),
        ('MK1 POD', '0.84 T'),
        ('HEAT SHIELD', '0.10 T'),
        ('TOTAL MASS', '1.04 T'),
    ]))
    out.append(line(spec_x, panel_y + 230, spec_x + 150, panel_y + 230, stroke=INK, sw=0.8, opacity=0.4))
    prose = [
        'Mission stage jettisoned before entry.',
        'Lowers reentry mass and improves',
        'parachute-recovery reliability.',
        '',
        'Only configuration remaining',
        'after final staging event.',
        '',
        'Touchdown under parachute alone;',
        'no powered descent stage carried.',
    ]
    for i, p in enumerate(prose):
        out.append(text(spec_x, panel_y + 260 + i * 20, p, size=10, fill=INK_SOFT, weight='500'))

    # ---- footer / title block
    foot_y = panel_y + panel_h + 30
    out.append(text(margin + 24, foot_y, 'Staging doctrine: one propulsion handoff at the core/mission interface, then a final capsule-only entry separation.', size=11.5, fill=INK_SOFT, weight='500'))

    tb_h = 70
    tb_y = H - margin - tb_h
    tb_w = W - 2 * margin
    c1, c3, c4 = 150, 190, 150
    c2 = tb_w - c1 - c3 - c4 - 150
    cells = [
        (c1, [('PERSEUS 1', 9, '800', FONT_HEAD, INK_SOFT), ('MISSION PACK', 9, '800', FONT_HEAD, INK_SOFT)]),
        (c2, [('STAGE SEPARATION SEQUENCE', 13, '800', FONT_BODY, INK), ('Kerbal Space Program \u2014 mission documentation appendix', 9.5, '500', FONT_BODY, INK_SOFT)]),
        (c3, [('DWG NO', 8, '700', FONT_MONO, INK_FAINT), ('KSP-PRS1-SS-02', 12, '700', FONT_MONO, INK)]),
        (c4, [('SCALE', 8, '700', FONT_MONO, INK_FAINT), ('NTS', 12, '700', FONT_MONO, INK)]),
        (150, [('SHEET', 8, '700', FONT_MONO, INK_FAINT), ('2 OF 4  REV A', 12, '700', FONT_MONO, INK)]),
    ]
    out.append(title_block(margin, tb_y, tb_w, tb_h, cells))

    out.append('</svg>')
    return '\n'.join(out)

import math

# ---- Ascent program data (derived from the verified ascent simulation, 20% Hammer) ----
# Each row: (event, met, alt, vel, pitch_from_vertical, roll, action)
# pitch given as deg from vertical (0 = straight up). NTS / nominal values.
PROGRAM = [
    ('LIFTOFF',        'T+00:00', 'PAD',     '0',   '0\u00b0',   'HOLD',   'Swivel 100%, Hammers ignite. Hold vertical. SAS ON.'),
    ('PITCH PROGRAM',  'T+00:08', '250 M',   '60',  '1\u00b0',   'HOLD',   'Begin gentle pitch east. Initiate gravity turn.'),
    ('ROLL PROGRAM',   'T+00:10', '350 M',   '70',  '2\u00b0',   '90\u00b0 E', 'Roll to flight heading 090. Establish downrange azimuth.'),
    ('THROTTLE WATCH', 'T+00:16', '1.0 KM',  '130', '3\u00b0',   'HOLD',   'Confirm prograde tracking. Keep nose near velocity vector.'),
    ('BOOSTER SEP',    'T+00:25', '2.6 KM',  '233', '9\u00b0',   'HOLD',   'Hammer burnout & jettison. Confirm core stable.'),
    ('MAX Q',          'T+00:30', '3.5 KM',  '270', '14\u00b0',  'HOLD',   'Through max dynamic pressure. Steering smooth, near prograde.'),
    ('PITCH 45',       'T+00:50', '10.0 KM', '450', '37\u00b0',  'HOLD',   'Approx 45\u00b0 from vertical. Hand off to gravity turn.'),
    ('CORE BURNOUT',   'T+01:03', '14.8 KM', '633', '50\u00b0',  'HOLD',   'Lower FL-T800 dry. Stage: jettison core, ignite Terrier.'),
    ('TERRIER ASCENT', 'T+01:05', '15+ KM',  '640', 'PRO',   'HOLD',   'Terrier finishes climb. Track prograde to apoapsis target.'),
    ('APO SHAPING',    '--',      '70-85 KM','VAR', 'PRO',   'HOLD',   'Coast/burn to set apoapsis ~80 km (upper end of band).'),
    ('CIRCULARIZE',    '--',      '~80 KM',  '2279', 'PRO',  'HOLD',   'Begin burn ~\u00bd burn-time BEFORE apoapsis. Burn until Pe rises to ~80 km.'),
]

# Ascent trajectory arc from the verified simulation: (downrange_km, altitude_km, pitch_from_vertical_deg)
# This is the powered core-stage arc (liftoff -> core burnout). Terrier continuation shown schematically.
TRAJECTORY = [
    (0.00, 0.00, 0), (0.00, 0.14, 0), (0.00, 0.32, 0), (0.00, 0.58, 1), (0.01, 0.93, 2),
    (0.02, 1.14, 3), (0.04, 1.37, 4), (0.06, 1.63, 5), (0.09, 1.92, 6), (0.13, 2.23, 7),
    (0.17, 2.57, 9), (0.23, 2.93, 10), (0.31, 3.31, 12), (0.39, 3.70, 13), (0.49, 4.10, 15),
    (0.60, 4.51, 16), (0.73, 4.94, 18), (0.88, 5.38, 20), (1.05, 5.84, 21), (1.24, 6.31, 23),
    (1.46, 6.79, 25), (1.70, 7.29, 27), (1.97, 7.80, 29), (2.27, 8.32, 31), (2.60, 8.85, 33),
    (2.96, 9.39, 35), (3.37, 9.94, 37), (3.81, 10.51, 39), (4.29, 11.07, 41), (4.81, 11.65, 44),
    (5.38, 12.22, 45), (5.99, 12.81, 47), (6.64, 13.41, 48), (7.32, 14.03, 49), (8.05, 14.65, 50),
    (8.23, 14.81, 50),
]
SEP_PT = (0.18, 2.64)      # downrange_km, altitude_km
BURNOUT_PT = (8.23, 14.81)



def event_badge(x, y, label, accent, r=15):
    return '\n'.join([
        circle(x, y, r, PANEL, stroke=accent, sw=1.7),
        circle(x, y, r - 4, 'none', stroke=accent, sw=0.8),
    ])


def program_table(x, y, w):
    cols = [
        ('EVENT', 0, 118),
        ('MET', 118, 66),
        ('ALT', 184, 64),
        ('V (M/S)', 248, 58),
        ('PITCH', 306, 50),
        ('ROLL', 356, 56),
        ('ACTION', 412, w - 412),
    ]
    row_h = 40
    n = len(PROGRAM)
    parts = [rect(x, y, w, row_h * (n + 1), PANEL, stroke=INK, sw=1.6)]
    # header band
    parts.append(rect(x, y, w, row_h, FILL_BLUE, stroke=INK, sw=1.6))
    for name, cx_off, cw in cols:
        parts.append(text(x + cx_off + 7, y + 25, name, size=9.5, fill=INK, weight='800', family=FONT_MONO, spacing='0.3'))
    # column separators
    for name, cx_off, cw in cols[1:]:
        parts.append(line(x + cx_off, y, x + cx_off, y + row_h * (n + 1), stroke=INK, sw=0.7, opacity=0.3))

    accents = {
        'BOOSTER SEP': VIOLET, 'CORE BURNOUT': SAFETY_RED, 'MAX Q': SAFETY_RED,
        'LIFTOFF': BLUEPRINT, 'TERRIER ASCENT': TEAL, 'APO SHAPING': TEAL, 'CIRCULARIZE': TEAL,
    }
    for i, row in enumerate(PROGRAM):
        ry = y + row_h * (i + 1)
        if i % 2 == 1:
            parts.append(rect(x, ry, w, row_h, INK, sw=0, opacity=0.025))
        event, met, alt, vel, pitch, roll, action = row
        ac = accents.get(event, INK)
        # event name (accent for keyed events)
        parts.append(text(x + 7, ry + 18, event, size=9.5, fill=ac, weight='800', family=FONT_MONO))
        parts.append(text(x + 7, ry + 31, met if event != 'LIFTOFF' else '', size=8, fill=INK_FAINT, weight='600', family=FONT_MONO))
        parts.append(text(x + 118 + 7, ry + 25, met, size=9, fill=INK_SOFT, weight='700', family=FONT_MONO))
        parts.append(text(x + 184 + 7, ry + 25, alt, size=9, fill=INK_SOFT, weight='700', family=FONT_MONO))
        parts.append(text(x + 248 + 7, ry + 25, vel, size=9, fill=INK_SOFT, weight='700', family=FONT_MONO))
        parts.append(text(x + 306 + 7, ry + 25, pitch, size=9, fill=INK, weight='800', family=FONT_MONO))
        parts.append(text(x + 356 + 7, ry + 25, roll, size=9, fill=INK, weight='800', family=FONT_MONO))
        parts.append(text(x + 412 + 7, ry + 25, action, size=8.3, fill=INK_SOFT, weight='600', family=FONT_BODY))
        if i > 0:
            parts.append(line(x, ry, x + w, ry, stroke=INK, sw=0.6, opacity=0.25))
    return '\n'.join(parts)


def trajectory_graph(x, y, w, h):
    """Ascent trajectory: altitude (Y) vs downrange (X), with vehicle attitude ticks
    along the flight path showing the pitch program. Classic flight-package figure."""
    parts = [rect(x, y, w, h, PANEL, stroke=INK, sw=1.4)]
    parts.append(text(x + 10, y + 18, 'ASCENT TRAJECTORY \u2014 ALTITUDE vs DOWNRANGE', size=8.5, fill=INK_FAINT, weight='800', family=FONT_MONO, spacing='0.3'))

    pad_l, pad_r, pad_t, pad_b = 46, 18, 34, 34
    gx, gy = x + pad_l, y + pad_t
    gw, gh = w - pad_l - pad_r, h - pad_t - pad_b

    dr_max, alt_max = 9.0, 16.0   # km; bounds the powered core arc with a little headroom

    def px(dr):
        return gx + (dr / dr_max) * gw

    def py(alt):
        return gy + gh - (alt / alt_max) * gh   # altitude increases UPWARD

    # grid: altitude (Y) lines
    for ak in range(0, int(alt_max) + 1, 2):
        yy = py(ak)
        parts.append(line(gx, yy, gx + gw, yy, stroke=INK_FAINT, sw=0.5, opacity=0.4))
        parts.append(text(gx - 6, yy + 3, f'{ak}', size=7.5, fill=INK_FAINT, anchor='end', weight='600', family=FONT_MONO))
    # grid: downrange (X) lines
    for dk in range(0, int(dr_max) + 1, 1):
        xx = px(dk)
        parts.append(line(xx, gy, xx, gy + gh, stroke=INK_FAINT, sw=0.5, opacity=0.3))
        parts.append(text(xx, gy + gh + 14, f'{dk}', size=7.5, fill=INK_FAINT, anchor='middle', weight='600', family=FONT_MONO))
    parts.append(text(gx + gw / 2, gy + gh + 28, 'DOWNRANGE (KM)', size=7.5, fill=INK_SOFT, anchor='middle', weight='700', family=FONT_MONO))
    # Y axis title (rotated)
    parts.append(text(gx - 32, gy + gh / 2, 'ALTITUDE (KM)', size=7.5, fill=INK_SOFT, anchor='middle', weight='700', family=FONT_MONO, extra=f'transform="rotate(-90 {gx - 32} {gy + gh / 2})"'))

    # the trajectory curve
    pts = [(px(dr), py(al)) for dr, al, _ in TRAJECTORY]
    d = 'M ' + ' L '.join(f'{xx:.1f} {yy:.1f}' for xx, yy in pts)
    parts.append(path(d, stroke=BLUEPRINT, sw=2.4))

    # attitude ticks: short bars along the path oriented to the vehicle pitch.
    # pitch is deg-from-vertical; tick points "up the body" -> direction (sin p, cos p) in screen-ish space.
    tick_len = 13
    for i in range(2, len(TRAJECTORY) - 1, 4):
        dr, al, pitch = TRAJECTORY[i]
        cxp, cyp = px(dr), py(al)
        a = math.radians(pitch)
        # body up-vector: vertical when pitch=0, tilting toward +downrange as pitch grows
        ux, uy = math.sin(a), -math.cos(a)   # screen y is inverted
        parts.append(line(cxp, cyp, cxp + ux * tick_len, cyp + uy * tick_len, stroke=INK_SOFT, sw=1.4))

    # event markers
    sx, sy = px(SEP_PT[0]), py(SEP_PT[1])
    parts.append(circle(sx, sy, 4, PANEL, stroke=VIOLET, sw=1.8))
    parts.append(text(sx + 7, sy + 2, 'BOOSTER SEP', size=7, fill=VIOLET, weight='800', family=FONT_MONO))
    # max Q (approx 3.5 km alt, interpolate downrange ~0.35)
    mqx, mqy = px(0.35), py(3.5)
    parts.append(circle(mqx, mqy, 4, PANEL, stroke=SAFETY_RED, sw=1.8))
    parts.append(text(mqx + 7, mqy + 2, 'MAX Q', size=7, fill=SAFETY_RED, weight='800', family=FONT_MONO))
    bx, by = px(BURNOUT_PT[0]), py(BURNOUT_PT[1])
    parts.append(circle(bx, by, 4, PANEL, stroke=SAFETY_RED, sw=1.8))
    parts.append(text(bx - 6, by - 8, 'CORE BURNOUT', size=7, fill=SAFETY_RED, anchor='end', weight='800', family=FONT_MONO))

    # Terrier continuation (schematic dashed arc beyond core burnout, climbing off-chart toward orbit)
    parts.append(path(f'M {bx} {by} Q {px(9.0)} {py(15.5)} {px(9.0)} {py(15.2)}', stroke=TEAL, sw=1.8, extra='stroke-dasharray="5 4"'))
    parts.append(text(bx + 6, by + 12, '\u2192 TERRIER TO ORBIT', size=7, fill=TEAL, weight='800', family=FONT_MONO))

    # attitude-tick legend
    parts.append(text(gx + gw - 4, gy + gh - 8, 'TICKS = VEHICLE PITCH', size=6.8, fill=INK_FAINT, anchor='end', weight='700', family=FONT_MONO))
    return '\n'.join(parts)


def roll_diagram(x, y, w, h):
    """Small heading/roll reference: top-down compass showing launch azimuth 090."""
    parts = [rect(x, y, w, h, PANEL, stroke=INK, sw=1.4)]
    parts.append(text(x + 10, y + 18, 'ROLL / HEADING REFERENCE', size=8.5, fill=INK_FAINT, weight='800', family=FONT_MONO, spacing='0.3'))
    cx0, cy0 = x + w / 2, y + h / 2 + 8
    r = min(w, h) / 2 - 30
    parts.append(circle(cx0, cy0, r, 'none', stroke=INK_FAINT, sw=1))
    # cardinal ticks
    for ang, lab in [(90, 'N'), (0, 'E'), (-90, 'S'), (180, 'W')]:
        a = math.radians(ang)
        x1, y1 = cx0 + (r - 6) * math.cos(a), cy0 - (r - 6) * math.sin(a)
        x2, y2 = cx0 + r * math.cos(a), cy0 - r * math.sin(a)
        parts.append(line(x1, y1, x2, y2, stroke=INK_SOFT, sw=1))
        lx, ly = cx0 + (r + 10) * math.cos(a), cy0 - (r + 10) * math.sin(a)
        parts.append(text(lx, ly + 3, lab, size=8, fill=INK_SOFT, anchor='middle', weight='800', family=FONT_MONO))
    # launch azimuth arrow to East (090)
    parts.append(path(f'M {cx0} {cy0} L {cx0 + r} {cy0}', stroke=BLUEPRINT, sw=2.4))
    parts.append(poly([(cx0 + r, cy0), (cx0 + r - 10, cy0 - 5), (cx0 + r - 10, cy0 + 5)], fill=BLUEPRINT))
    parts.append(text(cx0, y + h - 14, 'LAUNCH AZIMUTH 090\u00b0 (DUE EAST)', size=7.5, fill=BLUEPRINT, anchor='middle', weight='800', family=FONT_MONO))
    return '\n'.join(parts)


def stage_timeline(x, y, w):
    """Horizontal MET timeline showing the three powered-flight phases and key events."""
    parts = [text(x, y - 8, 'POWERED FLIGHT TIMELINE \u2014 MET', size=8.5, fill=INK_FAINT, weight='800', family=FONT_MONO, spacing='0.3')]
    bar_y = y + 6
    bar_h = 26
    # phases: (label, start_frac, end_frac, color)  -- fractions of the ~65s powered window shown
    phases = [
        ('BOOST  (2X HAMMER + SWIVEL)', 0.00, 0.39, FILL_BLUE_DK),
        ('CORE  (SWIVEL)', 0.39, 0.97, FILL_BLUE),
        ('TERRIER \u2192', 0.97, 1.00, FILL_BASE),
    ]
    for label, s, e, col in phases:
        bx = x + s * w
        bw = (e - s) * w
        parts.append(rect(bx, bar_y, bw, bar_h, col, stroke=INK, sw=1.3))
        if bw > 80:
            parts.append(text(bx + bw / 2, bar_y + 17, label, size=8, fill=INK, anchor='middle', weight='800', family=FONT_MONO))
    # event ticks: (frac, label, color)
    events = [
        (0.00, 'LIFTOFF', BLUEPRINT, 0),
        (0.39, 'SEP T+25s', VIOLET, 0),
        (0.46, 'MAXQ', SAFETY_RED, 11),
        (0.97, 'B/O T+63s', SAFETY_RED, 0),
        (1.00, 'STAGE', TEAL, 11),
    ]
    for frac, lab, col, dy in events:
        ex = x + frac * w
        parts.append(line(ex, bar_y - 6, ex, bar_y + bar_h + 6, stroke=col, sw=1.4))
        if frac <= 0.01:
            anchor = 'start'
        elif frac >= 0.99:
            anchor = 'end'
        else:
            anchor = 'middle'
        parts.append(text(ex, bar_y + bar_h + 18 + dy, lab, size=7.5, fill=col, anchor=anchor, weight='800', family=FONT_MONO))
    return '\n'.join(parts)


def build_sheet3():
    W, H = 1280, 1500
    margin = 16
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">']
    out.append(hatch_defs())
    out.append(sheet_frame(W, H, margin))

    # header
    out.append(mission_insignia(margin + 50, 76, r=29))
    out.append(text(150, 56, 'PERSEUS 1 \u00b7 MISSION PACK \u00b7 APPENDIX D', size=10.5, fill=BLUEPRINT, weight='800', family=FONT_HEAD, spacing='1.2'))
    out.append(text(150, 96, 'ASCENT GUIDANCE PROGRAM', size=30, fill=INK, weight='800', family=FONT_HEAD))
    out.append(text(150, 122, 'Powered flight sequence \u00b7 pitch & roll program \u00b7 nominal values (NTS)', size=12.5, fill=INK_SOFT, weight='500'))
    out.append(line(margin + 24, 140, W - margin - 24, 140, stroke=INK, sw=1.3))

    # main program table
    out.append(text(margin + 24, 174, 'POWERED FLIGHT SEQUENCE \u2014 NOMINAL (20% HAMMER, SWIVEL 100%)', size=10, fill=INK_FAINT, weight='800', family=FONT_MONO, spacing='0.5'))
    out.append(program_table(margin + 24, 186, W - 2 * (margin + 24)))

    # lower row: trajectory plot (left) + roll reference (right)
    gy = 186 + 40 * (len(PROGRAM) + 1) + 40
    gw = (W - 2 * (margin + 24) - 30)
    panel_h = 380
    out.append(trajectory_graph(margin + 24, gy, gw * 0.62, panel_h))
    out.append(roll_diagram(margin + 24 + gw * 0.62 + 30, gy, gw * 0.38, panel_h))

    # stage-phase MET timeline strip
    ty = gy + panel_h + 40
    out.append(stage_timeline(margin + 24, ty, W - 2 * (margin + 24)))

    # notes
    ny = ty + 92
    out.append(text(margin + 24, ny, 'PROGRAM NOTES', size=12, fill=BLUEPRINT, weight='800', family=FONT_HEAD, spacing='1'))
    notes = [
        'Pitch is given as degrees from vertical (0\u00b0 = straight up). Values are nominal for a smooth, hand-flown gravity turn.',
        'Below ~15 km keep the nose near the velocity vector; over-steering in thick air is the leading cause of departures.',
        'After booster separation the gravity turn is largely self-shaping \u2014 follow prograde rather than forcing pitch.',
        'Core stage nominally reaches ~15 km / ~25-30 km apoapsis; the Terrier completes the climb to the 70-85 km target.',
        'CIRCULARIZE: aim ~80 km apoapsis and LEAD it \u2014 start the burn a few seconds before apoapsis, not at it.',
        'The Terrier\u2019s low thrust makes the burn long; starting at apoapsis lets you fall back into atmosphere. Burn until periapsis meets apoapsis.',
    ]
    for i, n in enumerate(notes):
        out.append(text(margin + 24, ny + 24 + i * 19, '\u2022 ' + n, size=11, fill=INK_SOFT, weight='500'))

    # title block
    tb_h = 70
    tb_y = H - margin - tb_h
    tb_w = W - 2 * margin
    c1, c3, c4 = 150, 190, 150
    c2 = tb_w - c1 - c3 - c4 - 150
    cells = [
        (c1, [('PERSEUS 1', 9, '800', FONT_HEAD, INK_SOFT), ('MISSION PACK', 9, '800', FONT_HEAD, INK_SOFT)]),
        (c2, [('ASCENT GUIDANCE PROGRAM', 13, '800', FONT_BODY, INK), ('Kerbal Space Program \u2014 mission documentation appendix', 9.5, '500', FONT_BODY, INK_SOFT)]),
        (c3, [('DWG NO', 8, '700', FONT_MONO, INK_FAINT), ('KSP-PRS1-AG-03', 12, '700', FONT_MONO, INK)]),
        (c4, [('SCALE', 8, '700', FONT_MONO, INK_FAINT), ('NTS', 12, '700', FONT_MONO, INK)]),
        (150, [('SHEET', 8, '700', FONT_MONO, INK_FAINT), ('3 OF 4  REV A', 12, '700', FONT_MONO, INK)]),
    ]
    out.append(title_block(margin, tb_y, tb_w, tb_h, cells))

    out.append('</svg>')
    return '\n'.join(out)

import math

# Go/No-Go gates: (phase, nominal, marginal, abort)
GATES = [
    ('CORE BURNOUT', 'Apoapsis 20-30 km, rising', 'Apoapsis 15-20 km', 'Apoapsis < 12 km, or already falling'),
    ('MID TERRIER BURN', 'Apoapsis climbing toward 70-80 km', 'Apoapsis rising slowly \u2014 pitch flatter', 'Apoapsis stalled < 40 km, > \u00bd Terrier fuel spent'),
    ('LATE TERRIER BURN', 'Apoapsis ~80 km, periapsis rising thru 0', 'Periapsis lagging \u2014 keep burning prograde', 'Terrier < 25% fuel, periapsis still < -100 km'),
    ('ORBIT INSERTION', 'Periapsis clears 70 km, ~80 km circular', 'Periapsis 40-70 km \u2014 trim w/ remaining fuel', 'Cannot raise periapsis > 70 km w/ fuel left'),
]

CORRECTIONS = [
    ('1', 'Apoapsis rising slowly / periapsis not climbing',
     'Pitch TOWARD THE HORIZON now. Most common cause is too steep a climb; flatter flight converts thrust into the horizontal speed that raises periapsis. Single most effective fix.'),
    ('2', 'Apoapsis overshooting 85 km, periapsis still low',
     'Climbing too much. Pitch further toward horizon; let apoapsis settle while horizontal speed catches up.'),
    ('3', 'Apoapsis stalled but fuel remains',
     'Likely fighting gravity near-vertical. Lower the nose hard toward prograde/horizon and keep burning.'),
    ('4', 'Off-nominal but fuel-positive',
     'Terrier carries ~3.4 km/s; ascent needs ~1.8 km/s horizontal make-up plus losses. Real margin to recover a sloppy climb IF caught early.'),
]


def gate_table(x, y, w):
    cols = [('FLIGHT PHASE', 0, 150), ('NOMINAL  (GO)', 150, 250),
            ('MARGINAL  (CORRECT)', 400, 250), ('ABORT / NO-GO', 650, w - 650)]
    row_h = 56
    n = len(GATES)
    parts = [rect(x, y, w, row_h * (n + 1), PANEL, stroke=INK, sw=1.6)]
    parts.append(rect(x, y, w, row_h, FILL_BLUE, stroke=INK, sw=1.6))
    # color key strips at column tops
    parts.append(rect(x + 150, y, 250, 5, TEAL, sw=0))
    parts.append(rect(x + 400, y, 250, 5, VIOLET, sw=0))
    parts.append(rect(x + 650, y, w - 650, 5, SAFETY_RED, sw=0))
    for name, off, cw in cols:
        parts.append(text(x + off + 8, y + 34, name, size=9.5, fill=INK, weight='800', family=FONT_MONO, spacing='0.3'))
    for name, off, cw in cols[1:]:
        parts.append(line(x + off, y, x + off, y + row_h * (n + 1), stroke=INK, sw=0.7, opacity=0.3))

    def wrap(s, x0, y0, cw, fill, size=8.3):
        # crude word-wrap to fit column width
        words = s.split(' ')
        lines, cur = [], ''
        maxchars = int(cw / (size * 0.56))
        for wd in words:
            if len(cur) + len(wd) + 1 <= maxchars:
                cur = (cur + ' ' + wd).strip()
            else:
                lines.append(cur); cur = wd
        if cur:
            lines.append(cur)
        return [text(x0, y0 + i * 11, ln, size=size, fill=fill, weight='600', family=FONT_BODY) for i, ln in enumerate(lines)]

    for i, (phase, nom, marg, ab) in enumerate(GATES):
        ry = y + row_h * (i + 1)
        if i % 2 == 1:
            parts.append(rect(x, ry, w, row_h, INK, sw=0, opacity=0.025))
        parts.append(text(x + 8, ry + 24, phase, size=9, fill=INK, weight='800', family=FONT_MONO))
        parts.extend(wrap(nom, x + 158, ry + 18, 238, INK_SOFT))
        parts.extend(wrap(marg, x + 408, ry + 18, 238, INK_SOFT))
        parts.extend(wrap(ab, x + 658, ry + 18, w - 650 - 16, SAFETY_RED))
        if i > 0:
            parts.append(line(x, ry, x + w, ry, stroke=INK, sw=0.6, opacity=0.25))
    return '\n'.join(parts)


def corrections_block(x, y, w):
    parts = [text(x, y, 'CORRECTIONS \u2014 IN PRIORITY ORDER', size=11, fill=BLUEPRINT, weight='800', family=FONT_HEAD, spacing='0.6')]
    yy = y + 26
    for num, cond, action in CORRECTIONS:
        parts.append(circle(x + 9, yy - 4, 10, PANEL, stroke=BLUEPRINT, sw=1.6))
        parts.append(text(x + 9, yy, num, size=10, fill=BLUEPRINT, anchor='middle', weight='800', family=FONT_MONO))
        parts.append(text(x + 28, yy - 2, cond, size=9.5, fill=INK, weight='800', family=FONT_BODY))
        # wrap action text
        words = action.split(' ')
        lines, cur = [], ''
        maxchars = int((w - 28) / (8.6 * 0.55))
        for wd in words:
            if len(cur) + len(wd) + 1 <= maxchars:
                cur = (cur + ' ' + wd).strip()
            else:
                lines.append(cur); cur = wd
        if cur:
            lines.append(cur)
        for j, ln in enumerate(lines):
            parts.append(text(x + 28, yy + 13 + j * 12, ln, size=8.6, fill=INK_SOFT, weight='500', family=FONT_BODY))
        yy += 24 + len(lines) * 12
    return '\n'.join(parts)


def abort_box(x, y, w, h):
    parts = [rect(x, y, w, h, PANEL, stroke=SAFETY_RED, sw=2.2, rx=6)]
    parts.append(rect(x, y, w, 26, SAFETY_RED, sw=0, rx=0))
    parts.append(text(x + 12, y + 18, 'HARD ABORT WINDOW', size=11, fill='#ffffff', weight='800', family=FONT_HEAD, spacing='0.6'))
    lines = [
        ('Abort orbital insertion if, with \u2264 25% Terrier fuel remaining, periapsis is still', '800'),
        ('below -100 km (apoapsis stalled under ~40 km). Beyond this point there is not', '500'),
        ('enough propellant to both raise apoapsis and build orbital horizontal speed;', '500'),
        ('continuing only deepens an unrecoverable suborbital arc.', '500'),
        ('', '500'),
        ('ON ABORT:  stop climbing \u2014 hold capsule prograde and shallow for survivable', '800'),
        ('re-entry \u00b7 close service bay \u00b7 heat shield forward \u00b7 retain fuel for retrograde', '500'),
        ('slow-down if available \u00b7 ride down as suborbital crew recovery.', '500'),
        ('A clean suborbital abort that recovers the crew beats burning the last fuel', '500'),
        ('into a steeper crash.', '500'),
    ]
    for i, (ln, wt) in enumerate(lines):
        parts.append(text(x + 12, y + 46 + i * 15, ln, size=8.8, fill=INK if wt == '800' else INK_SOFT, weight=wt, family=FONT_BODY))
    return '\n'.join(parts)


def build_sheet4():
    W, H = 1280, 1500
    margin = 16
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">']
    out.append(hatch_defs())
    out.append(sheet_frame(W, H, margin))

    out.append(mission_insignia(margin + 50, 76, r=29))
    out.append(text(150, 56, 'PERSEUS 1 \u00b7 MISSION PACK \u00b7 APPENDIX D', size=10.5, fill=BLUEPRINT, weight='800', family=FONT_HEAD, spacing='1.2'))
    out.append(text(150, 96, 'ASCENT CONTINGENCY & ABORT CRITERIA', size=27, fill=INK, weight='800', family=FONT_HEAD))
    out.append(text(150, 122, 'Go / No-Go gates \u00b7 corrections \u00b7 hard abort window', size=12.5, fill=INK_SOFT, weight='500'))
    out.append(line(margin + 24, 140, W - margin - 24, 140, stroke=INK, sw=1.3))

    # explainer band
    ex_y = 168
    out.append(rect(margin + 24, ex_y, W - 2 * (margin + 24), 70, PANEL, stroke=INK, sw=1.3))
    out.append(text(margin + 38, ex_y + 22, 'READING THE CLIMB \u2014 WATCH APOAPSIS, NOT PERIAPSIS', size=10, fill=BLUEPRINT, weight='800', family=FONT_HEAD, spacing='0.5'))
    expl = [
        'A deeply negative periapsis (even -400 km) is NORMAL for most of the ascent: at core burnout you have ~485 m/s horizontal vs ~2279 m/s needed for orbit.',
        'Periapsis only climbs from far-negative, through the surface, up past 70 km in the FINAL portion of the Terrier burn. Judge ascent health by apoapsis trend.',
    ]
    for i, e in enumerate(expl):
        out.append(text(margin + 38, ex_y + 42 + i * 15, '\u2022 ' + e, size=9, fill=INK_SOFT, weight='500'))

    # gate table
    gt_y = ex_y + 90
    out.append(text(margin + 24, gt_y - 8, 'GO / NO-GO GATES', size=11, fill=BLUEPRINT, weight='800', family=FONT_HEAD, spacing='0.6'))
    out.append(gate_table(margin + 24, gt_y, W - 2 * (margin + 24)))

    # corrections + abort box side by side
    lower_y = gt_y + 56 * 5 + 44
    col_w = (W - 2 * (margin + 24) - 36)
    out.append(corrections_block(margin + 24, lower_y, col_w * 0.52))
    out.append(abort_box(margin + 24 + col_w * 0.52 + 36, lower_y - 14, col_w * 0.48, 210))

    # failure-mode note at bottom
    fm_y = lower_y + 210
    out.append(text(margin + 24, fm_y, 'PRIMARY FAILURE MODE', size=11, fill=SAFETY_RED, weight='800', family=FONT_HEAD, spacing='0.6'))
    fm = [
        'Flying too steep \u2014 putting Terrier thrust into climbing instead of building horizontal speed. The nose held toward vertical gains altitude',
        'but stalls horizontal velocity; apoapsis stops rising, the vehicle arcs over, and it falls back before periapsis clears the atmosphere.',
        'Signature: -400 km periapsis at END of burn with apoapsis stuck ~30 km. Correction: pitch toward the horizon, keep the prograde marker low.',
    ]
    for i, f in enumerate(fm):
        out.append(text(margin + 24, fm_y + 22 + i * 15, '\u2022 ' + f, size=9, fill=INK_SOFT, weight='500'))

    # title block
    tb_h = 70
    tb_y = H - margin - tb_h
    tb_w = W - 2 * margin
    c1, c3, c4 = 150, 190, 150
    c2 = tb_w - c1 - c3 - c4 - 150
    cells = [
        (c1, [('PERSEUS 1', 9, '800', FONT_HEAD, INK_SOFT), ('MISSION PACK', 9, '800', FONT_HEAD, INK_SOFT)]),
        (c2, [('ASCENT CONTINGENCY & ABORT CRITERIA', 13, '800', FONT_BODY, INK), ('Kerbal Space Program \u2014 mission documentation appendix', 9.5, '500', FONT_BODY, INK_SOFT)]),
        (c3, [('DWG NO', 8, '700', FONT_MONO, INK_FAINT), ('KSP-PRS1-AB-04', 12, '700', FONT_MONO, INK)]),
        (c4, [('SCALE', 8, '700', FONT_MONO, INK_FAINT), ('NTS', 12, '700', FONT_MONO, INK)]),
        (150, [('SHEET', 8, '700', FONT_MONO, INK_FAINT), ('4 OF 4  REV A', 12, '700', FONT_MONO, INK)]),
    ]
    out.append(title_block(margin, tb_y, tb_w, tb_h, cells))

    out.append('</svg>')
    return '\n'.join(out)

(OUT / 'perseus_rocket_stack_technical.svg').write_text(build_sheet1(), encoding='utf-8')
(OUT / 'perseus_staging_technical.svg').write_text(build_sheet2(), encoding='utf-8')
(OUT / 'perseus_ascent_program_technical.svg').write_text(build_sheet3(), encoding='utf-8')
(OUT / 'perseus_abort_criteria_technical.svg').write_text(build_sheet4(), encoding='utf-8')
print('wrote four sheets')