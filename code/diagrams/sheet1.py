import sys
sys.path.insert(0, '/home/claude/nasa_dev')
from dsys import *
from parts import (part_pod, part_parachute, part_heat_shield, part_decoupler,
                    part_tank, part_swivel, part_terrier, part_hammer_pair, part_fins,
                    part_avionics, part_service_bay)

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


if __name__ == '__main__':
    svg = build_sheet1()
    with open('/home/claude/nasa_dev/sheet1.svg', 'w') as f:
        f.write(svg)
    print('written', len(svg))
