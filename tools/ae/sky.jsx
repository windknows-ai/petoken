// The night sky in three parallax layers, 2560 x 1440:
//   sky_far   - the deep sky: colour gradient, nebula clouds, the Milky Way with dust lanes
//   sky_stars - the star field (light on black), drawn additively and drifting a little faster
//   sky_dust  - near wisps of glowing haze (light on black), drifting fastest
// Each is rendered as one still.

var W = 2560, H = 1440;

function noise(layer, o) {
    var fx = effect(layer, "ADBE Fractal Noise");
    var p = function (id, v) { set(fx, "ADBE Fractal Noise-" + id, v); };
    p("0001", o.fractal || 6);          // Fractal type.
    p("0002", o.noise || 3);            // Noise type (3 spline).
    p("0004", o.contrast || 100);
    p("0005", o.brightness || 0);
    p("0006", o.overflow || 2);         // 2 clip.
    p("0008", o.rotation || 0);
    if (o.scaleW) {
        p("0009", 0);
        p("0011", o.scaleW);
        p("0012", o.scaleH);
    } else {
        p("0010", o.scale || 100);
    }
    if (o.offset) p("0013", o.offset);
    p("0015", o.complexity || 6);
    p("0017", o.subInfluence || 70);
    p("0018", o.subScale || 56);
    p("0023", o.evolution || 0);
    p("0027", o.seed || 0);
    return fx;
}

function tritone(layer, hi, mid, lo) {
    var t = effect(layer, "ADBE Tritone");
    setAt(t, 1, hi);
    setAt(t, 2, mid);
    setAt(t, 3, lo);
    return t;
}

function feathered(layer, cx, cy, rx, ry, feather, invert) {
    var mask = layer.property("ADBE Mask Parade").addProperty("ADBE Mask Atom");
    var s = new Shape(), kx = .5523 * rx, ky = .5523 * ry;
    s.vertices = [[cx, cy - ry], [cx + rx, cy], [cx, cy + ry], [cx - rx, cy]];
    s.inTangents = [[-kx, 0], [0, -ky], [kx, 0], [0, ky]];
    s.outTangents = [[kx, 0], [0, ky], [-kx, 0], [0, -ky]];
    s.closed = true;
    mask.property("ADBE Mask Shape").setValue(s);
    mask.property("ADBE Mask Feather").setValue([feather, feather]);
    if (invert) mask.inverted = true;
    return mask;
}

// A cloud is drawn in its own comp, then placed with a mask: a generated noise ignores masks
// on its own layer, but a masked comp layer cuts cleanly.
function cloud(comp, name, o) {
    var inner = app.project.items.addComp(name, W, H, 1, comp.duration, 30);
    var l = solid(inner, name);
    noise(l, o);
    var d = effect(l, "ADBE Turbulent Displace");
    set(d, "ADBE Turbulent Displace-0002", o.displace || 22);
    set(d, "ADBE Turbulent Displace-0003", o.displaceSize || 180);
    set(d, "ADBE Turbulent Displace-0005", 3);
    tritone(l, o.hi, o.mid, [0, 0, 0]);
    set(effect(l, "ADBE Exposure2"), "ADBE Exposure2-0003", o.exposure === undefined ? .2 : o.exposure);
    var sat = effect(l, "ADBE HUE SATURATION");                 // Richer colour.
    setAt(sat, 5, 35);
    var placed = comp.layers.add(inner);
    if (o.mask) feathered(placed, o.mask[0] * W, o.mask[1] * H, o.mask[2] * W, o.mask[3] * H, o.mask[4] * W);
    placed.blendingMode = o.mode || BlendingMode.ADD;
    placed.property("ADBE Transform Group").property("ADBE Opacity").setValue(o.opacity || 100);
    return placed;
}

// Stars from noise: tiny cells, crushed so only the brightest points survive, then a glow.
function noiseStars(comp, name, o) {
    var inner = app.project.items.addComp(name, W, H, 1, comp.duration, 30);
    var l = solid(inner, name);
    noise(l, {fractal: 1, noise: 1, scale: o.scale, contrast: 300, brightness: -60, complexity: 1, seed: o.seed});
    setAt(effect(l, "ADBE Threshold2"), 1, o.level);         // Only the brightest cells stay: the stars.
    set(effect(l, "ADBE Gaussian Blur 2"), "ADBE Gaussian Blur 2-0001", o.soft || .6);
    if (o.tint) {
        var t = effect(l, "ADBE Tint");
        set(t, "ADBE Tint-0001", [0, 0, 0]);
        set(t, "ADBE Tint-0002", o.tint);
    }
    glow(l, o.glow, o.glowIntensity || 1.5, 10, o.glowA, o.glowB);
    var placed = addMode(comp.layers.add(inner));
    if (o.mask) feathered(placed, o.mask[0] * W, o.mask[1] * H, o.mask[2] * W, o.mask[3] * H, o.mask[4] * W);
    if (o.opacity) placed.property("ADBE Transform Group").property("ADBE Opacity").setValue(o.opacity);
    return placed;
}

function farSky() {
    var comp = app.project.items.addComp("sky_far", W, H, 1, 1, 30);
    var base = solid(comp, "gradient");
    var ramp = effect(base, "ADBE Ramp");
    set(ramp, "ADBE Ramp-0001", [W * .45, 0]);
    set(ramp, "ADBE Ramp-0002", [.008, .012, .045]);
    set(ramp, "ADBE Ramp-0003", [W * .55, H]);
    set(ramp, "ADBE Ramp-0004", [.06, .03, .12]);
    // Big soft colour clouds, each in its own part of the sky.
    cloud(comp, "violet", {fractal: 6, scale: 900, contrast: 140, brightness: -40, complexity: 7, seed: 11,
                           hi: [.62, .42, 1], mid: [.05, .02, .12], mask: [.24, .3, .36, .42, .3], opacity: 70});
    cloud(comp, "blue", {fractal: 6, scale: 1000, contrast: 150, brightness: -42, complexity: 7, seed: 23,
                         hi: [.35, .62, 1], mid: [.02, .05, .14], mask: [.78, .22, .34, .38, .28], opacity: 65});
    cloud(comp, "rose", {fractal: 6, scale: 800, contrast: 160, brightness: -48, complexity: 7, seed: 37,
                         hi: [1, .5, .78], mid: [.1, .02, .08], mask: [.58, .78, .3, .3, .25], opacity: 60});
    cloud(comp, "teal", {fractal: 6, scale: 700, contrast: 160, brightness: -50, complexity: 6, seed: 41,
                         hi: [.4, .95, .95], mid: [.01, .06, .08], mask: [.1, .85, .25, .25, .22], opacity: 55});
    // Fine bright filaments over the clouds.
    cloud(comp, "filaments", {fractal: 5, scale: 520, contrast: 260, brightness: -62, complexity: 9, seed: 7,
                              displace: 30, hi: [.95, .85, 1], mid: [.06, .04, .12], mask: [.5, .45, .6, .5, .35],
                              opacity: 40, exposure: -.8});
    // The Milky Way: a long bright band across the sky with dark dust lanes through it.
    var band = cloud(comp, "milkyway", {fractal: 6, scaleW: 1400, scaleH: 260, rotation: -24, contrast: 130,
                                        brightness: -20, complexity: 8, seed: 3, displace: 25,
                                        hi: [1, .94, .9], mid: [.1, .08, .16], opacity: 60, exposure: -1.0});
    var bandMask = band.property("ADBE Mask Parade").addProperty("ADBE Mask Atom");
    var s = new Shape();
    var cx = W * .5, cy = H * .42, len = W * .75, half = H * .14, a = -24 * Math.PI / 180;
    var ux = Math.cos(a), uy = Math.sin(a), nx = -uy, ny = ux;
    s.vertices = [[cx - ux * len + nx * half, cy - uy * len + ny * half], [cx + ux * len + nx * half, cy + uy * len + ny * half],
                  [cx + ux * len - nx * half, cy + uy * len - ny * half], [cx - ux * len - nx * half, cy - uy * len - ny * half]];
    s.closed = true;
    bandMask.property("ADBE Mask Shape").setValue(s);
    bandMask.property("ADBE Mask Feather").setValue([H * .22, H * .22]);
    var lanes = cloud(comp, "dust lanes", {fractal: 5, scaleW: 900, scaleH: 140, rotation: -24, contrast: 220,
                                          brightness: -35, complexity: 8, seed: 5, displace: 30,
                                          hi: [1, 1, 1], mid: [.5, .5, .5], mode: BlendingMode.SUBTRACT,
                                          opacity: 45, exposure: 0});
    var laneMask = lanes.property("ADBE Mask Parade").addProperty("ADBE Mask Atom");
    laneMask.property("ADBE Mask Shape").setValue(s);
    laneMask.property("ADBE Mask Feather").setValue([H * .16, H * .16]);
    var bloom = comp.layers.addSolid([0, 0, 0], "bloom", W, H, 1);
    bloom.adjustmentLayer = true;
    glow(bloom, 120, .25, 70);
    var vig = comp.layers.addSolid([0, 0, 0], "vignette", W, H, 1);
    feathered(vig, W / 2, H / 2, W * .62, H * .64, W * .3, true);
    vig.property("ADBE Transform Group").property("ADBE Opacity").setValue(70);
    var item = render(comp, "sky_far");
    item.timeSpanStart = 0; item.timeSpanDuration = 1 / 30;
}

function starField() {
    var comp = app.project.items.addComp("sky_stars", W, H, 1, 4, 30);
    noiseStars(comp, "dust stars", {scale: 3, level: 205, soft: .5, seed: 3, glow: 2,
                                     glowA: [.75, .82, 1], glowB: [.5, .45, 1], opacity: 85});
    noiseStars(comp, "small stars", {scale: 5, level: 215, soft: .7, seed: 9, glow: 4,
                                      glowA: [.8, .86, 1], glowB: [.65, .55, 1]});
    noiseStars(comp, "warm stars", {scale: 7, level: 228, soft: .9, seed: 17, glow: 5,
                                     tint: [1, .9, .76], glowA: [1, .85, .65], glowB: [1, .6, .4]});
    noiseStars(comp, "band stars", {scale: 3, level: 195, soft: .5, seed: 21, glow: 2,
                                     glowA: [.85, .85, 1], glowB: [.6, .55, 1], mask: [.5, .42, .7, .17, .12]});
    // A handful of bright stars with soft cross flares.
    var bright = [[.12, .2], [.31, .62], [.47, .14], [.66, .4], [.83, .7], [.9, .18], [.22, .86], [.58, .9]];
    for (var i = 0; i < bright.length; i++) {
        var size = 3 + (i % 3) * 1.5;
        var c = orb(comp, "bright" + i, size * 2, [1, .97, .92], 2);
        c.property("ADBE Transform Group").property("ADBE Position").setValue([W * bright[i][0] - W / 2 + W / 2,
                                                                              H * bright[i][1]]);
        glow(c, 14, 1.4, 20, [.8, .86, 1], [.6, .55, 1]);
        for (var k2 = 0; k2 < 2; k2++) {
            var sp = bar(comp, "flare" + i + "_" + k2, size * 26, 1.6, [1, 1, 1], 1, k2 * 90);
            sp.property("ADBE Transform Group").property("ADBE Position").setValue([W * bright[i][0], H * bright[i][1]]);
            sp.property("ADBE Transform Group").property("ADBE Opacity").setValue(60);
        }
    }
    var item = render(comp, "sky_stars");
    item.timeSpanStart = 3.9; item.timeSpanDuration = 1 / 30;
}

function nearDust() {
    var comp = app.project.items.addComp("sky_dust", W, H, 1, 1, 30);
    cloud(comp, "wisps", {fractal: 6, scale: 1300, contrast: 200, brightness: -55, complexity: 6, seed: 51,
                          displace: 40, displaceSize: 300, hi: [.7, .62, 1], mid: [.03, .02, .06], opacity: 50, exposure: -1.2});
    cloud(comp, "gold wisps", {fractal: 6, scale: 1100, contrast: 220, brightness: -65, complexity: 6, seed: 61,
                               displace: 40, displaceSize: 260, hi: [1, .85, .62], mid: [.05, .03, .02], exposure: -1.2,
                               mask: [.7, .75, .4, .35, .3], opacity: 45});
    var item = render(comp, "sky_dust");
    item.timeSpanStart = 0; item.timeSpanDuration = 1 / 30;
}

log("sky");
farSky();
starField();
nearDust();
app.project.renderQueue.render();
log("rendered");
