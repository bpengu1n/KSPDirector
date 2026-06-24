import sys
sys.path.insert(0, '/home/claude/nasa_dev')
from dsys import *
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


if __name__ == '__main__':
    svg = build_sheet4()
    open('/home/claude/nasa_dev/sheet4.svg', 'w').write(svg)
    print('written', len(svg))
