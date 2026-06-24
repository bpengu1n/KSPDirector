import sys
sys.path.insert(0, '/home/claude/nasa_dev')
from dsys import *


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


if __name__ == '__main__':
    W, H = 900, 420
    margin = 16
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">']
    out.append(hatch_defs())
    out.append(sheet_frame(W, H, margin))
    out.append(part_parachute(120, 40))
    out.append(part_pod(260, 40))
    out.append(part_heat_shield(400, 60))
    out.append(part_decoupler(540, 70))
    out.append(part_tank(680, 40, 100, 150, FILL_BLUE, 'FL-T800', 'mission'))
    out.append(part_terrier(120, 230))
    out.append(part_swivel(280, 230))
    out.append(part_hammer_pair(560, 230))
    out.append(part_fins(560, 380))
    out.append('</svg>')
    with open('/home/claude/nasa_dev/test2.svg', 'w') as f:
        f.write('\n'.join(out))
    print('ok')
