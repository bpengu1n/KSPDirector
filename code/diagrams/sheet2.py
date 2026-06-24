import sys
sys.path.insert(0, '/home/claude/nasa_dev')
from dsys import *
from parts import (part_pod, part_parachute, part_heat_shield, part_decoupler, part_tank)

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


if __name__ == '__main__':
    svg = build_sheet2()
    with open('/home/claude/nasa_dev/sheet2.svg', 'w') as f:
        f.write(svg)
    print('written', len(svg))
