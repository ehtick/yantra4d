"""
Tablaco v2 — first iteration (CadQuery / B-Rep).

A truth table you can hold. Each cell is a cube built from two press-fit half-shells
(white = V, dark = F, per Decision #6) that slide and rotate on a vertical rail
(Decision #11). The presented face carries a tactile glyph: V is SUNKEN, F is RAISED
(Decision #15 — resolve the value by touch, inside vs outside, before reading the
letter). A panel stacks an 8x8 canonical matrix (Decision #2/#14).

Design source: Tablaco_V2_ES design brief, 20 structural decisions. Ownership per
Decision #20: work-for-hire, (c) Xochitl Martinez Nava; MADFAM portfolio licence.

Sandbox contract (apps/api/services/engine/cq_runner.py):
  - `cq` and `math` pre-injected; params arrive as bare globals.
  - Read each via PARAM(lambda: name, default). No globals()/eval/getattr.
  - Assign the final solid/compound to `result`.
"""

import cadquery as cq
import math
from cadquery import Compound


def PARAM(getter, default):
    try:
        v = getter()
        return default if v is None else v
    except Exception:
        return default


# ── Parameters ────────────────────────────────────────────────────────────────
target_part = str(PARAM(lambda: target_part, "cell_v"))

cell   = float(PARAM(lambda: cell, 18.0))       # cube edge (mm)
rod_dia = float(PARAM(lambda: rod_dia, 5.0))    # rail diameter (mm)
clear  = float(PARAM(lambda: clearance, 0.35))  # bore clearance over rail (mm)
glyph  = float(PARAM(lambda: glyph, 1.4))       # V sunk depth / F raised height (mm)
corner = float(PARAM(lambda: corner, 1.6))      # outer vertical edge fillet (mm)
pitch  = float(PARAM(lambda: pitch, 20.0))      # panel grid pitch (mm)
rows   = int(PARAM(lambda: rows, 8))            # panel rows (assignments)
cols   = int(PARAM(lambda: cols, 8))            # panel columns

# Clamp so extreme UI values still build watertight.
cell = max(10.0, min(cell, 30.0))
rod_dia = max(2.0, min(rod_dia, cell * 0.5))
clear = max(0.1, min(clear, 1.0))
glyph = max(0.4, min(glyph, cell * 0.16))
corner = max(0.0, min(corner, cell * 0.28))
pitch = max(cell + 1.0, min(pitch, cell + 10.0))
rows = max(1, min(rows, 8))
cols = max(1, min(cols, 8))

bore = rod_dia + clear
half_y = cell / 2.0


# ── Glyph builders (font-free geometric relief, Decision #15) ──────────────────
def glyph_V_cutter():
    """A sunken 'V' to cut into the +Y (light / V) face."""
    gw = cell * 0.42
    gh = cell * 0.46
    gs = cell * 0.085
    L = math.hypot(gw / 2.0, gh) + gs
    yc = half_y - glyph / 2.0 + 0.05
    thick = glyph + 0.3

    def stroke(x_top):
        phi = math.degrees(math.atan2(x_top, -gh))  # tilt Z-long box in X-Z plane
        s = cq.Workplane("XY").box(gs, thick, L)
        s = s.rotate((0, 0, 0), (0, 1, 0), phi)
        return s.translate((x_top / 2.0, yc, 0))

    return stroke(-gw / 2.0).union(stroke(gw / 2.0))


def glyph_F_solid():
    """A raised 'F' to union onto the -Y (dark / F) face."""
    gw = cell * 0.34
    gh = cell * 0.46
    gs = cell * 0.085
    yc = -half_y - glyph / 2.0 + 0.05
    spine = cq.Workplane("XY").box(gs, glyph, gh).translate((-gw / 2.0 + gs / 2.0, yc, 0))
    top = cq.Workplane("XY").box(gw, glyph, gs).translate((0.0, yc, gh / 2.0 - gs / 2.0))
    mid = cq.Workplane("XY").box(gw * 0.72, glyph, gs).translate((-gw / 2.0 + gw * 0.72 / 2.0, yc, 0.0))
    return spine.union(top).union(mid)


# ── Half-shell (one of the two medias conchas) ─────────────────────────────────
def half_shell(sign, with_glyph=True, with_pins=False):
    """sign=+1 -> +Y half (white, V, sunken).  sign=-1 -> -Y half (dark, F, raised)."""
    wp = cq.Workplane("XY").box(cell, cell / 2.0, cell).translate((0, sign * cell / 4.0, 0))

    # Rail bore: full cylinder on Z at the split plane -> half-channel per shell.
    borecut = cq.Workplane("XY").circle(bore / 2.0).extrude(cell * 1.3, both=True)
    wp = wp.cut(borecut)

    # Round the two OUTER vertical edges only (mating edges stay sharp).
    if corner > 0.1:
        sel = ">Y" if sign > 0 else "<Y"
        try:
            wp = wp.edges(sel).edges("|Z").fillet(min(corner, cell / 2.0 - 0.6))
        except Exception:
            pass

    if with_glyph:
        try:
            if sign > 0:
                wp = wp.cut(glyph_V_cutter())
            else:
                wp = wp.union(glyph_F_solid())
        except Exception:
            pass

    # Press-fit alignment pins/sockets on the mating (Y=0) face (Decision #17).
    if with_pins:
        pr = max(1.0, cell * 0.06)
        off = cell * 0.28
        for zx in ((off, off), (-off, -off)):
            pin = cq.Workplane("XY").circle(pr).extrude(1.6).rotate((0, 0, 0), (1, 0, 0), -90 * sign)
            pin = pin.translate((zx[0], 0, zx[1]))
            try:
                wp = wp.union(pin)
            except Exception:
                pass
    return wp


def rail(length):
    return cq.Workplane("XY").circle(rod_dia / 2.0).extrude(length / 2.0, both=True)


# ── Panel (8x8 canonical truth-table matrix) ───────────────────────────────────
def col_x(c):
    return (c - (cols - 1) / 2.0) * pitch


def row_z(r):
    return ((rows - 1) / 2.0 - r) * pitch


def cell_state(r, c):
    """Input columns show the canonical bit pattern (V/F); result columns stay neutral."""
    n_inputs = min(3, cols)
    if c < n_inputs:
        bit = (r >> (n_inputs - 1 - c)) & 1
        return "V" if bit else "F"
    return "N"


STATE_ANGLE = {"V": 0.0, "F": 180.0, "N": 45.0}


def build_panel_part(which):
    light_proto = half_shell(+1, with_glyph=False)
    dark_proto = half_shell(-1, with_glyph=False)
    rail_proto = rail(rows * pitch + pitch * 0.6)

    if which in ("cells_light", "cells_dark"):
        proto = light_proto if which == "cells_light" else dark_proto
        solids = []
        for r in range(rows):
            for c in range(cols):
                a = STATE_ANGLE[cell_state(r, c)]
                piece = proto.rotate((0, 0, 0), (0, 0, 1), a).translate((col_x(c), 0, row_z(r)))
                solids.append(piece.val())
        return Compound.makeCompound(solids)

    if which == "rails":
        solids = []
        for c in range(cols):
            solids.append(rail_proto.translate((col_x(c), 0, 0)).val())
        return Compound.makeCompound(solids)

    # board — backing plate behind the cells
    bt = 4.0
    w = cols * pitch + pitch * 0.4
    h = rows * pitch + pitch * 0.4
    y = -(half_y + bt / 2.0 + 0.6)
    plate = cq.Workplane("XY").box(w, bt, h).translate((0, y, 0))
    try:
        plate = plate.edges("|Y").fillet(min(4.0, bt))
    except Exception:
        pass
    return plate


# ── Dispatch ───────────────────────────────────────────────────────────────────
if target_part == "cell_v":
    result = half_shell(+1, with_glyph=True)
elif target_part == "cell_f":
    result = half_shell(-1, with_glyph=True)
elif target_part == "shell":
    result = half_shell(+1, with_glyph=True, with_pins=True)
elif target_part == "rod":
    result = rail(cell * 1.85)
elif target_part in ("board", "rails", "cells_light", "cells_dark"):
    result = build_panel_part(target_part)
else:
    result = half_shell(+1, with_glyph=True)
