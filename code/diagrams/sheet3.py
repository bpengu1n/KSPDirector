import sys
sys.path.insert(0, '/home/claude/nasa_dev')
from dsys import *
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
# Derived from: sim.run_ascent(VehicleConfig(booster_pct=20))
# Regenerate: python tools/update_sheet3_trajectory.py
# VehicleConfig: booster_pct=20, extra_payload=0.0
TRAJECTORY = [
    (0.00, 0.00, 0),
    (0.00, 0.02, 0),
    (0.00, 0.05, 0),
    (0.00, 0.10, 0),
    (0.00, 0.17, 0),
    (0.00, 0.26, 0),
    (0.00, 0.36, 0),
    (0.00, 0.49, 1),
    (0.00, 0.64, 1),
    (0.01, 0.82, 2),
    (0.02, 1.01, 3),
    (0.03, 1.23, 4),
    (0.05, 1.47, 4),
    (0.07, 1.74, 6),
    (0.10, 2.03, 7),
    (0.14, 2.35, 8),
    (0.19, 2.70, 9),
    (0.26, 3.07, 11),
    (0.34, 3.46, 12),
    (0.43, 3.86, 14),
    (0.53, 4.27, 15),
    (0.66, 4.69, 17),
    (0.80, 5.13, 19),
    (0.96, 5.58, 20),
    (1.13, 6.04, 22),
    (1.34, 6.52, 24),
    (1.56, 7.01, 26),
    (1.81, 7.51, 28),
    (2.09, 8.02, 30),
    (2.40, 8.54, 32),
    (2.75, 9.07, 34),
    (3.12, 9.61, 36),
    (3.53, 10.16, 38),
    (3.98, 10.71, 40),
    (4.47, 11.27, 42),
    (5.00, 11.83, 44),
    (5.57, 12.40, 46),
    (6.17, 12.98, 47),
    (6.81, 13.57, 48),
    (7.49, 14.17, 49),
    (8.20, 14.79, 50),
]
SEP_PT = (2.89, 2.89)  # (downrange_km, alt_km) -- update if needed
BURNOUT_PT = (8.31, 14.88)
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


if __name__ == '__main__':
    svg = build_sheet3()
    open('/home/claude/nasa_dev/sheet3.svg', 'w').write(svg)
    print('written', len(svg))
