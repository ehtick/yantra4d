// Tablaco v2 — fast OpenSCAD preview twin (CSG, dependency-free).
//
// This is the second half of the dual-engine experience: a simplified panel that
// the browser's WASM OpenSCAD can rebuild in milliseconds while the student drags
// sliders. Exact geometry (snap-fit, crowns, keys, STEP export) lives in the
// CadQuery modes; THIS mode trades mechanism detail for live responsiveness.
// Kept dependency-free (no BOSL2) so the WASM worker needs no library path.
//
// Param names match the CadQuery cartridge (cell, rows, cols, corner, glyph).

$fn = 24;

cell     = 18.0;   // cube edge (mm)
rows     = 8;      // panel rows
cols     = 8;      // panel columns
corner   = 1.5;    // vertical edge rounding (approximated by chamfer here)
glyph    = 1.2;    // V sink / F relief (mm)
notation = "vf";   // "vf" (V/F) or "10" (1/0)

rod_d   = max(3.0, min(cell * 0.28, 8.0));
margin  = cell * 0.8;
board_t = 5.0;
stroke  = max(1.5, cell * 0.09);

// ── One preview cube: white/dark halves hinted by a seam, V sunk / F raised ──
module preview_cube(state) {  // state: 0=V (glyph front), 1=F, 2=neutral(45°)
    a = state == 0 ? 0 : state == 1 ? 180 : 45;
    rotate([0, 0, a]) {
        difference() {
            // body with chamfered verticals (cheap stand-in for fillets)
            hull() for (sx = [-1, 1], sy = [-1, 1])
                translate([sx * (cell/2 - corner), sy * (cell/2 - corner), 0])
                    cylinder(h = cell, r = max(corner, 0.1), center = true, $fn = 12);
            // rail bore
            cylinder(h = cell + 2, r = rod_d/2 + 0.4, center = true);
            // sunken V on +Y face
            translate([0, cell/2, 0]) v_glyph_cut();
        }
        // raised F on −Y face
        translate([0, -cell/2, 0]) rotate([0, 0, 180]) f_glyph();
    }
}

module v_glyph_cut() {
    gw = cell * 0.40; gh = cell * 0.44;
    if (notation == "10") {
        // sunken '1'
        translate([0, -glyph/2, 0]) cube([stroke, glyph + 0.2, gh], center = true);
        translate([-cell*0.05, -glyph/2, gh/2 - cell*0.05])
            rotate([0, 45, 0]) cube([stroke, glyph + 0.2, cell*0.14], center = true);
    } else {
        for (s = [-1, 1])
            translate([s * gw/4, -glyph/2, 0])
                rotate([0, s * atan2(gw/2, gh), 0])
                    cube([stroke, glyph + 0.2, sqrt(pow(gw/2,2) + pow(gh,2))], center = true);
    }
}

module f_glyph() {
    gw = cell * 0.32; gh = cell * 0.44;
    if (notation == "10") {
        // raised '0' — oval ring
        translate([0, -glyph/2, 0]) rotate([90, 0, 0])
            scale([1, cell*0.22/(cell*0.16), 1])
                difference() {
                    cylinder(h = glyph, r = cell*0.16 + stroke/2, center = true);
                    cylinder(h = glyph + 0.2, r = cell*0.16 - stroke/2, center = true);
                }
    } else {
        translate([0, -glyph/2, 0]) {
            translate([-gw/2 + stroke/2, 0, 0]) cube([stroke, glyph, gh], center = true);
            translate([0, 0, gh/2 - stroke/2]) cube([gw, glyph, stroke], center = true);
            translate([-gw/2 + gw*0.3, 0, 0])  cube([gw*0.6, glyph, stroke], center = true);
        }
    }
}

// ── Panel: board + rails + contiguous cube stacks (pitch = cell) ──────────────
module panel() {
    w = cols * cell + 2 * margin;
    h = rows * cell + 2 * margin;

    // board / pintarrón
    translate([0, -(cell/2 + board_t/2 + 1), 0])
        cube([w, board_t, h], center = true);

    for (c = [0 : cols - 1]) {
        x = (c - (cols - 1) / 2) * cell;
        // notched rail (notches hinted by rings)
        translate([x, 0, 0]) {
            cylinder(h = rows * cell + 4, r = rod_d/2, center = true);
            for (r = [0 : rows])
                translate([0, 0, -rows*cell/2 + r * cell])
                    cylinder(h = 0.8, r = rod_d/2 + 0.3, center = true);
        }
        // contiguous cubes, canonical pattern in the input columns
        n_inputs = min(3, cols);
        for (r = [0 : rows - 1]) {
            z = ((rows - 1) / 2 - r) * cell;
            state = c < n_inputs
                ? (r < pow(2, n_inputs)
                    ? (floor(r / pow(2, n_inputs - 1 - c)) % 2 == 0 ? 0 : 1)
                    : 2)
                : 2;
            translate([x, 0, z]) preview_cube(state);
        }
    }
}

panel();
