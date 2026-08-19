# Tablaco v2 — first iteration

A truth table you can hold. This cartridge is the CadQuery (B-Rep) realization of the
Tablaco v2 design brief (20 structural decisions; see the standalone `tablaco-v2` repo's
`docs/DESIGN-BRIEF.md` and `Tablaco_V2_ES` deck).

## The object
- **Cell** — a cube built from two press-fit **half-shells**: white = **V**, dark = **F**
  (Decision #6, panel-scale colour). It rides a **vertical rail**, sliding up/down into a
  detented seat and rotating to present a face (Decision #11).
- **Tactile glyph** — on the presented face, **V is sunken** and **F is raised**
  (Decision #15): the value resolves by fingertip — inside vs outside — before the letter
  is read. First-class non-visual legibility (Decision #7).
- **Panel** — the canonical **8×8** matrix (Decision #2/#14): 2³ = 8 assignments over p, q, r.
  The first three columns show the canonical V/F pattern; result columns sit neutral.
- **Manufacturing** — FDM, undercuts allowed, no parting-line constraints (Decision #16).

## Modes
| Mode | Parts | What it shows |
| :-- | :-- | :-- |
| **Unit (cell)** | `cell_v`, `cell_f`, `rod` | one assembled two-tone cell on its rail |
| **Half-shell** | `shell` | a single half-shell with its rail channel + mating pins |
| **Panel (8×8)** | `board`, `rails`, `cells_light`, `cells_dark` | the full truth-table board |

## Parameters
`cell` (edge, mm), `rod_dia` (rail Ø), `clearance` (slide fit — never jam, Decision #17),
`glyph` (V/F relief depth), `corner` (edge fillet); panel-only: `pitch`, `rows`, `cols`.

## Geometry contract
`main.py` follows the sandbox contract in `apps/api/services/engine/cq_runner.py`: read each
parameter via `PARAM(lambda: name, default)`, dispatch on the injected `target_part`, and
assign the final solid/compound to `result`.

## Ownership (Decision #20)
Work-for-hire. Copyright in the resulting design, geometry and source vests in
**Xóchitl Martínez Nava** on delivery; MADFAM retains a non-exclusive portfolio licence.
This cartridge is excluded from the published Hyperobjects Commons catalogue.

## Status (2026-08-18)

**Working now** (renders in the local Yantra4D instance, live slider re-render):
- `unit` — two-tone cell (white V / dark F) on a rail, V sunken / F raised. ✓
- `panel` — 8×8 two-tone board showing the canonical p/q/r pattern. ✓
- Live sliders auto-render (500ms debounce; estimate constants tuned so the
  "long render" modal no longer fires).

**Known gaps / not yet done:**
- `half_shell` is an incomplete first pass — it renders a plain half-cube + bore +
  two pins. It should be rebuilt as a *complete* half-shell. **Reference the original
  tablaco v1** `projects/tablaco/half_cube.scad` (dual-U topology, mitered walls,
  cantilever snap beams, adaptive rod boss) for a proper mechanism.
- Glyph quality (V/F) is legible but rough; refine.

## Next iteration — design decisions locked from the client's dated sketch (Tablaco V2, notebook)

Confirmed with the client 2026-08-18. Integrate these next:
1. **Cube size stays 18mm.** The sketch's "5cm" refers to a *different* dimension
   (panel depth / rail length — still to confirm which); it is NOT the cube edge.
2. **Cubes stack Lego-style, contiguous.** Each cube's **male (♂) top** plugs into the
   **female (♀) bottom** of the cube above; a column is a solid stack threaded by a
   **notched rail** (pitch = cube height, no gap — replaces the current 20mm-spaced model).
   Add the **"muesca"** (notch) on the cube and detent **notches on the rail**.
3. **Backing board doubles as the "pintarrón"** (whiteboard) — it carries ♂/♀ holders to
   park the cells/keys *not in use* for the current exercise ("solo los que no usamos").
4. Neutral = edge-on ("◇ / no se usa") and V/F two-tone are already correct.
5. **Open question to resolve with client:** notation — the sketch's "VF 1 0" may mean
   1/0 selectable alongside V/F. Currently V/F only.

Source notes: the standalone `tablaco-v2` repo `docs/DESIGN-BRIEF.md`, the `Tablaco_V2_ES`
deck (20 structural decisions), and the client's dated notebook sketch.
