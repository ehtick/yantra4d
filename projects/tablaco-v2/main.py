"""
Tablaco v2 — geometry generator (CadQuery / B-Rep). Single source of truth.

A truth table you can hold. This file is sandbox-contract compatible with the
Yantra4D cq_runner (params injected as bare globals, `cq` + `math` pre-imported,
result assigned to `result`) AND runs standalone for tests/exports. It is copied
verbatim into yantra4d/projects/tablaco-v2/main.py (keep them identical).

── Design sources ────────────────────────────────────────────────────────────────
* Tablaco_V2_ES deck (20 structural decisions) — bivalent, 3 vars/8x8, rotate-to-
  assign, V sunken / F raised (Decision #15), FDM-only (Decision #16), 18mm cell
  on the A1 bed (Decision #18), per-joint fit strategy (Decision #17).
* Client notebook sketch (2026-08-18, decisions locked in conversation):
  - cubes stack LEGO-STYLE CONTIGUOUS: male (♂) castellated crown on top, female
    (♀) recess underneath; a column is a solid stack; pitch = cell height.
  - NOTCHED rails (axial detent grooves).
  - the backing board doubles as the "pintarrón", parking unused pieces:
    one strip of ♀ sockets (holds cube ♂ crowns), one strip of ♂ studs
    (holds cube ♀ recesses).
* v1 lessons (tablaco/half_cube.scad): scale-clamped features
  (max(k*scale, printable_min)), cantilever snap beams with ramped lead-in and
  relief, adaptive rod boss (bore + 0.7×available), proportional seam gap
  (0.005×size), self-mating dual-U topology, and the anti-lesson — v1 exposed 49
  parameters; v2 exposes SEVEN and derives the rest. The answer pattern of the
  operator key is derived from the logic engine and never exposed (locked
  parameter doctrine).

── Additive-manufacturing standards applied ──────────────────────────────────────
* Print orientation: shells print MATING FACE DOWN → the rail bore is a half-
  channel open to the bed (no overhang, no teardrop needed); glyph faces are
  vertical walls (crisp).
* Elephant-foot chamfer on every bed-contact edge (0.45mm).
* Feature floors: no wall below 1.2mm, no relief below 0.5mm, snap beams clamped
  to printable minimums (v1 clamp system).
* 45° rule respected: castellation teeth chamfered, sockets are through/open.
* One "tightness" dial (0..1) derives every clearance/interference pair
  (Decision #13's partition: exposed / derived / locked).
"""

import cadquery as cq
import math
from cadquery import Compound


def PARAM(getter, default):
    """Injected global if present else default (sandbox hides globals()/NameError)."""
    try:
        v = getter()
        return default if v is None else v
    except Exception:
        return default


# ══════════════════════════════════════════════════════════════════════════════
# Exposed parameters (seven — everything else is derived or locked)
# ══════════════════════════════════════════════════════════════════════════════
target_part = str(PARAM(lambda: target_part, "cell_v"))

cell      = float(PARAM(lambda: cell, 18.0))        # cube edge (mm) — Decision #18
tightness = float(PARAM(lambda: tightness, 0.5))    # 0 loose … 1 tight (one dial)
glyph     = float(PARAM(lambda: glyph, 1.2))        # V sink / F relief depth (mm)
corner    = float(PARAM(lambda: corner, 1.5))       # outer vertical edge fillet (mm)
rows      = int(PARAM(lambda: rows, 8))             # panel rows (canonical 8)
cols      = int(PARAM(lambda: cols, 8))             # panel columns (canonical 8)
connective = str(PARAM(lambda: connective, "and"))  # operator key: and|or|implies|iff|not

# Clamps — extreme UI values must still build watertight and printable.
cell = max(12.0, min(cell, 30.0))
tightness = max(0.0, min(tightness, 1.0))
glyph = max(0.6, min(glyph, cell * 0.12))
corner = max(0.0, min(corner, cell * 0.24))
rows = max(1, min(rows, 8))
cols = max(1, min(cols, 8))
if connective not in ("and", "or", "implies", "iff", "not"):
    connective = "and"

# ══════════════════════════════════════════════════════════════════════════════
# Derived dimensions (v1 scale-clamp system; never exposed)
# ══════════════════════════════════════════════════════════════════════════════
S = cell / 18.0                                   # scale factor vs reference cell

wall = max(1.2, 2.2 * S)                          # shell wall (≥3 perimeters)
rod_d = max(3.0, min(cell * 0.28, 8.0))           # rail diameter, adaptive
slide_clear = 0.50 - 0.30 * tightness             # bore-over-rail sliding fit
seam = max(0.06, cell * 0.005)                    # mating-face gap (v1 proportional)
mate_clear = 0.38 - 0.18 * tightness              # castellation ♂/♀ backlash
foot = 0.45                                       # elephant-foot chamfer
bore_r = rod_d / 2.0 + slide_clear

# Central boss around the bore (v1 adaptive formula: bore + 0.7×available space)
boss_r = bore_r + (cell / 2.0 - wall - bore_r) * 0.7

# Snap-fit beams (v1 research ratios, clamped to printable minimums)
beam_len = max(1.5, 6.0 * S * 0.55)
beam_w = max(0.9, 3.0 * S * 0.8)
beam_t = max(0.5, 1.2 * S * 0.8)
undercut = max(0.18, 0.5 * S * (0.6 + 0.5 * tightness))
head_len = max(0.5, 1.5 * S * 0.7)

# Castellated crown (♂ up / ♀ down) — the Lego-style stack + rotation detent.
crown_r_out = boss_r                              # crown rides on the boss ring
crown_r_in = bore_r + max(0.7, wall * 0.5)
crown_h = max(1.2, 1.8 * S)                       # engagement height
TEETH = 8                                         # detents every 45°: V, F, neutral
tooth_arc = 360.0 / TEETH / 2.0                   # tooth fills half its sector

half_y = cell / 2.0
EPS = 0.01


# ══════════════════════════════════════════════════════════════════════════════
# Logic engine (inline mirror of logic/truth_tables.py — sandbox has no imports)
# ══════════════════════════════════════════════════════════════════════════════
_CONN = {
    "not":     (1, lambda p, q=None: not p),
    "and":     (2, lambda p, q: p and q),
    "or":      (2, lambda p, q: p or q),
    "implies": (2, lambda p, q: (not p) or q),
    "iff":     (2, lambda p, q: p == q),
}


def _rows(n):
    total = 2 ** n
    out = []
    for i in range(total):
        bits = total - 1 - i
        out.append(tuple(bool((bits >> (n - 1 - k)) & 1) for k in range(n)))
    return out


def _result_column(name, n_vars):
    arity, fn = _CONN[name]
    col = []
    for a in _rows(n_vars):
        col.append(bool(fn(*a[:arity])))
    return col


# ══════════════════════════════════════════════════════════════════════════════
# Primitive helpers
# ══════════════════════════════════════════════════════════════════════════════
def _annulus(r_out, r_in, h):
    return (cq.Workplane("XY").circle(r_out).extrude(h)
            .cut(cq.Workplane("XY").circle(r_in).extrude(h + EPS)))


def _crown_teeth(r_out, r_in, h, backlash=0.0, z0=0.0):
    """8 castellation teeth as annular sector prisms (± backlash on the arc)."""
    solids = []
    half = math.radians(tooth_arc) - (backlash / max(r_out, 1.0))
    for k in range(TEETH):
        a0 = math.radians(k * 360.0 / TEETH)
        pts = []
        steps = 6
        for s in range(steps + 1):                       # outer arc
            a = a0 - half + (2 * half) * s / steps
            pts.append((r_out * math.cos(a), r_out * math.sin(a)))
        for s in range(steps + 1):                       # inner arc, back
            a = a0 + half - (2 * half) * s / steps
            pts.append((r_in * math.cos(a), r_in * math.sin(a)))
        w = cq.Workplane("XY").polyline(pts).close().extrude(h)
        if z0:
            w = w.translate((0, 0, z0))
        solids.append(w)
    out = solids[0]
    for s in solids[1:]:
        out = out.union(s)
    return out


def _stroke(x0, z0, x1, z1, width, y_center, depth):
    """A straight glyph stroke as a box from (x0,z0) to (x1,z1) on a Y-normal face."""
    L = math.hypot(x1 - x0, z1 - z0) + width
    ang = math.degrees(math.atan2(x1 - x0, z1 - z0))
    s = (cq.Workplane("XY").box(width, depth, L)
         .rotate((0, 0, 0), (0, 1, 0), ang)
         .translate(((x0 + x1) / 2.0, y_center, (z0 + z1) / 2.0)))
    return s


def glyph_V(y_face, depth, sunken=True):
    """Geometric 'V' strokes centred on a Y-normal face (fontless, Decision #15)."""
    gw, gh = cell * 0.40, cell * 0.44
    w = max(1.5, cell * 0.09)                     # ≥1.5mm vs 14% shrink (Decision #18)
    yc = y_face - depth / 2.0 + (EPS if sunken else -EPS)
    a = _stroke(-gw / 2.0, gh / 2.0, 0.0, -gh / 2.0, w, yc, depth + 0.2)
    b = _stroke(gw / 2.0, gh / 2.0, 0.0, -gh / 2.0, w, yc, depth + 0.2)
    return a.union(b)


def glyph_F(y_face, depth):
    """Geometric 'F' strokes, raised, centred on a Y-normal face."""
    gw, gh = cell * 0.32, cell * 0.44
    w = max(1.5, cell * 0.09)
    yc = y_face - depth / 2.0
    spine = _stroke(-gw / 2.0 + w / 2.0, gh / 2.0, -gw / 2.0 + w / 2.0, -gh / 2.0, w, yc, depth)
    top = _stroke(-gw / 2.0, gh / 2.0 - w / 2.0, gw / 2.0, gh / 2.0 - w / 2.0, w, yc, depth)
    mid = _stroke(-gw / 2.0, 0.0, gw * 0.18, 0.0, w, yc, depth)
    return spine.union(top).union(mid)


# ══════════════════════════════════════════════════════════════════════════════
# The half-shell — complete, self-mating (dual-U), snap-fit, stackable
# ══════════════════════════════════════════════════════════════════════════════
def half_shell(kind="v"):
    """One half of a cell. kind='v': white half, sunken V on its +Y face.
    kind='f': dark half, raised F. Same base geometry; a part mates with its
    partner rotated 180° about Z (v1 dual-U): features at +X map to -X.

    Print orientation: mating face (Y=0) DOWN on the bed.
    """
    h = cell
    # 1) Body: outer half-box, hollowed to wall thickness (open toward Y=0).
    outer = (cq.Workplane("XY")
             .box(cell, half_y, h)
             .translate((0, half_y / 2.0, 0)))
    cavity = (cq.Workplane("XY")
              .box(cell - 2 * wall, half_y - wall, h - 2 * wall)
              .translate((0, (half_y - wall) / 2.0 - EPS, 0)))
    body = outer.cut(cavity)

    # 2) Mating-face seam relief: shave the proportional gap (v1 fit_clear).
    body = body.cut(cq.Workplane("XY").box(cell + EPS, 2 * seam, h + EPS)
                    .translate((0, seam, 0)))

    # 3) Central boss half-ring around the bore + the bore channel itself.
    boss = _annulus(boss_r, bore_r, h - 2 * wall).translate((0, 0, -(h - 2 * wall) / 2.0))
    boss = boss.intersect(cq.Workplane("XY").box(cell, half_y, h)
                          .translate((0, half_y / 2.0, 0)))
    body = body.union(boss)
    body = body.cut(cq.Workplane("XY").circle(bore_r).extrude(h * 2, both=True))

    # 4) Crown ♂ (top) and recess ♀ (bottom) — Lego-style contiguous stacking.
    crown = _crown_teeth(crown_r_out, crown_r_in, crown_h, backlash=0.0, z0=h / 2.0)
    crown = crown.intersect(cq.Workplane("XY").box(cell, half_y, h + 2 * crown_h)
                            .translate((0, half_y / 2.0, 0)))
    try:  # 45°-rule: chamfer tooth tops for clean bridging + easy engagement
        crown = crown.faces(">Z").chamfer(min(0.6, crown_h * 0.4))
    except Exception:
        pass
    body = body.union(crown)

    recess = _crown_teeth(crown_r_out + mate_clear, crown_r_in - mate_clear,
                          crown_h + mate_clear, backlash=-mate_clear,
                          z0=-h / 2.0 - EPS)
    body = body.cut(recess)

    # 5) Snap-fit: beam at +X of the flat face, catch window at -X (self-mating
    #    under rotZ-180). Ramped head (30° lead-in), v1 ratios.
    bx = boss_r + beam_len / 2.0
    if bx + beam_len / 2.0 < cell / 2.0 - wall:
        beam = (cq.Workplane("XY")
                .box(beam_len, beam_t, beam_w)
                .translate((bx, beam_t / 2.0 - EPS, 0)))
        head = (cq.Workplane("XY")
                .box(head_len, beam_t + undercut, beam_w)
                .translate((bx + beam_len / 2.0 - head_len / 2.0,
                            (beam_t + undercut) / 2.0 - EPS, 0)))
        try:
            head = head.edges("|Z and >Y").chamfer(min(undercut * 0.8, head_len * 0.8))
        except Exception:
            pass
        body = body.union(beam.union(head))
        # catch window at -X: pocket sized for head + travel clearance
        win = (cq.Workplane("XY")
               .box(head_len + 2 * mate_clear, beam_t + undercut + mate_clear,
                    beam_w + 2 * mate_clear)
               .translate((-(bx + beam_len / 2.0 - head_len / 2.0),
                           (beam_t + undercut + mate_clear) / 2.0 - EPS, 0)))
        body = body.cut(win)

    # 6) Alignment pin (+X diagonal) and socket (-X) — self-mating pair.
    pr = max(0.9, cell * 0.05)
    px, pz = cell * 0.30, cell * 0.30
    pin = (cq.Workplane("XZ").workplane(offset=0)
           .center(px, pz).circle(pr).extrude(-max(1.2, 1.8 * S)))
    try:
        pin = pin.faces("<Y").chamfer(min(0.4, pr * 0.5))
    except Exception:
        pass
    body = body.union(pin)
    socket = (cq.Workplane("XZ")
              .center(-px, pz).circle(pr + mate_clear)
              .extrude(-(max(1.2, 1.8 * S) + mate_clear)))
    body = body.cut(socket)

    # 7) Outer cosmetics: vertical-edge fillet, elephant-foot chamfer at bed edges.
    if corner > 0.1:
        try:
            body = body.edges("|Z").edges(">Y").fillet(corner)
        except Exception:
            pass
    try:  # bed-contact = the mating plane edges when printed face-down
        body = body.faces("<Y").edges("|X").chamfer(foot)
    except Exception:
        pass

    # 8) Glyph — V sunken on the white half, F raised on the dark half.
    if kind == "v":
        body = body.cut(glyph_V(half_y, glyph, sunken=True))
    else:
        body = body.union(glyph_F(half_y + glyph, glyph))

    return body


def cell_f_positioned():
    """The dark (F) half, rotated into assembly position (-Y side)."""
    return half_shell("f").rotate((0, 0, 0), (0, 0, 1), 180)


# ══════════════════════════════════════════════════════════════════════════════
# Rail — notched (sketch decision #2's detent hardware)
# ══════════════════════════════════════════════════════════════════════════════
def rail(n_cells):
    """Vertical rail: cylinder with shallow annular detent notches at cell pitch
    and a foot spigot that plants into the board."""
    length = n_cells * cell + crown_h + 2.0
    r = rod_d / 2.0
    body = cq.Workplane("XY").circle(r).extrude(length)
    notch_d = max(0.25, 0.3 * S)
    for k in range(n_cells + 1):
        z = k * cell + crown_h / 2.0
        groove = (_annulus(r + EPS, r - notch_d, max(0.6, 0.8 * S))
                  .translate((0, 0, z)))
        body = body.cut(groove)
    try:
        body = body.faces(">Z").chamfer(min(0.8, r * 0.5))
    except Exception:
        pass
    # foot spigot (press-fits the board socket — interference from the dial)
    spigot = cq.Workplane("XY").circle(r + 0.15 + 0.15 * tightness).extrude(-3.0)
    body = body.union(spigot)
    return body.translate((0, 0, -(n_cells * cell) / 2.0))


# ══════════════════════════════════════════════════════════════════════════════
# Board / pintarrón — structure + parking (sketch decision #3)
# ══════════════════════════════════════════════════════════════════════════════
BT = 5.0  # board thickness


def board():
    """Backing board: rail sockets + base ♀ crown rings per column, one parking
    strip of ♂ studs (bottom margin) and one of ♀ sockets (top margin)."""
    margin = cell * 0.8
    w = cols * cell + 2 * margin
    h = rows * cell + 2 * margin
    y0 = -(half_y + BT / 2.0 + 1.0)
    plate = cq.Workplane("XY").box(w, BT, h).translate((0, y0, 0))
    try:
        plate = plate.edges("|Y").fillet(min(3.0, BT * 0.6))
    except Exception:
        pass

    z_base = -(rows * cell) / 2.0
    for c in range(cols):
        x = _col_x(c)
        # rail socket through the board
        plate = plate.cut(cq.Workplane("XY").circle(rod_d / 2.0 + 0.1)
                          .extrude(BT + 2).translate((x, y0 - BT / 2.0 - 1, z_base - 1))
                          .rotate((x, y0, z_base), (1, 0, 0), 90))
    # ♂ parking studs (bottom margin) — cubes hang by their ♀ recess
    stud = _crown_teeth(crown_r_out - mate_clear, crown_r_in + mate_clear,
                        crown_h * 0.9, backlash=mate_clear)
    n_park = min(cols, 5)
    for k in range(n_park):
        x = (k - (n_park - 1) / 2.0) * cell * 1.2
        s = stud.rotate((0, 0, 0), (1, 0, 0), -90).translate(
            (x, y0 + BT / 2.0, z_base - margin * 0.55))
        plate = plate.union(s)
    # ♀ parking sockets (top margin) — cubes park by their ♂ crown
    pocket = _crown_teeth(crown_r_out + mate_clear, crown_r_in - mate_clear,
                          crown_h + mate_clear, backlash=-mate_clear)
    for k in range(n_park):
        x = (k - (n_park - 1) / 2.0) * cell * 1.2
        p = pocket.rotate((0, 0, 0), (1, 0, 0), -90).translate(
            (x, y0 + BT / 2.0 + EPS, (rows * cell) / 2.0 + margin * 0.55))
        plate = plate.cut(p)
    return plate


# ══════════════════════════════════════════════════════════════════════════════
# Operator key — the connective made physical (logic-derived, never hand-set)
# ══════════════════════════════════════════════════════════════════════════════
def operator_key():
    """A bar spanning the result column. Per row: answer V → probe pin that
    reaches INTO the sunken V; answer F → relief pocket that CLEARS the raised F.
    The key sits flush iff every cell is correct (Decision #4/#5). The pin/answer
    mapping comes from the logic engine — the locked parameter."""
    arity, _ = _CONN[connective]
    n_vars = max(arity, min(3, int(math.log2(max(rows, 2)))))
    col = _result_column(connective, n_vars)[:rows]
    n = len(col)

    bar_w = cell * 0.8
    bar_t = max(3.0, 4.0 * S)
    bar_l = n * cell
    bar = (cq.Workplane("XY").box(bar_w, bar_t, bar_l)
           .translate((0, half_y + glyph + bar_t / 2.0 + 0.2, 0)))
    try:
        bar = bar.edges("|Z").fillet(min(2.0, bar_w * 0.12))
    except Exception:
        pass

    pin_r = max(1.4, cell * 0.09)
    for i, is_true in enumerate(col):
        z = (n - 1) / 2.0 * cell - i * cell
        if is_true:   # probe reaches into the sunken V
            pin = (cq.Workplane("XY").circle(pin_r)
                   .extrude(glyph + 0.4)
                   .rotate((0, 0, 0), (1, 0, 0), 90)
                   .translate((0, half_y + glyph + 0.21, z)))
            try:
                pin = pin.faces("<Y").chamfer(min(0.5, pin_r * 0.4))
            except Exception:
                pass
            bar = bar.union(pin)
        else:         # pocket clears the raised F
            pocket = (cq.Workplane("XY").circle(pin_r + cell * 0.10)
                      .extrude(glyph + 0.8)
                      .rotate((0, 0, 0), (1, 0, 0), 90)
                      .translate((0, half_y + glyph + bar_t / 2.0 + 0.2, z)))
            bar = bar.cut(pocket)

    # Handle with the connective's symbol position marked by a raised dot code
    handle = (cq.Workplane("XY").box(bar_w, bar_t, cell * 0.6)
              .translate((0, half_y + glyph + bar_t / 2.0 + 0.2,
                          bar_l / 2.0 + cell * 0.3)))
    try:
        handle = handle.edges("|Y").fillet(min(2.0, bar_w * 0.12))
    except Exception:
        pass
    bar = bar.union(handle)
    # dot code: 1..5 raised dots identify the connective by touch
    order = ["not", "and", "or", "implies", "iff"]
    ndots = order.index(connective) + 1
    for d in range(ndots):
        x = (d - (ndots - 1) / 2.0) * (bar_w / 6.0)
        dot = (cq.Workplane("XY").circle(max(0.9, cell * 0.05)).extrude(0.8)
               .rotate((0, 0, 0), (1, 0, 0), 90)
               .translate((x, half_y + glyph + 0.21 - 0.8,
                           bar_l / 2.0 + cell * 0.3)))
        bar = bar.union(dot)
    return bar


# ══════════════════════════════════════════════════════════════════════════════
# Panel assembly (contiguous Lego stack — pitch = cell)
# ══════════════════════════════════════════════════════════════════════════════
def _col_x(c):
    return (c - (cols - 1) / 2.0) * cell


def _row_z(r):
    return ((rows - 1) / 2.0 - r) * cell


def _cell_state(r, c):
    n_inputs = min(3, cols)
    if c < n_inputs:
        bit = (r >> (n_inputs - 1 - c)) & 1 if r < 2 ** n_inputs else 0
        return "V" if (r < 2 ** n_inputs and bit) else ("F" if r < 2 ** n_inputs else "N")
    return "N"


STATE_ANGLE = {"V": 0.0, "F": 180.0, "N": 45.0}


def panel_part(which):
    if which == "board":
        return board().val()
    if which == "rails":
        solids = []
        proto = rail(rows)
        for c in range(cols):
            solids.append(proto.translate((_col_x(c), 0, 0)).val())
        return Compound.makeCompound(solids)
    light = half_shell("v")
    dark = cell_f_positioned()
    proto = light if which == "cells_light" else dark
    solids = []
    for r in range(rows):
        for c in range(cols):
            a = STATE_ANGLE[_cell_state(r, c)]
            solids.append(proto.rotate((0, 0, 0), (0, 0, 1), a)
                          .translate((_col_x(c), 0, _row_z(r))).val())
    return Compound.makeCompound(solids)


# ══════════════════════════════════════════════════════════════════════════════
# Dispatch
# ══════════════════════════════════════════════════════════════════════════════
if target_part == "cell_v":
    result = half_shell("v")
elif target_part == "cell_f":
    result = cell_f_positioned()
elif target_part == "rod":
    result = rail(1)
elif target_part == "shell":
    result = half_shell("v")
elif target_part == "key":
    result = operator_key()
elif target_part in ("board", "rails", "cells_light", "cells_dark"):
    result = panel_part(target_part)
else:
    result = half_shell("v")
