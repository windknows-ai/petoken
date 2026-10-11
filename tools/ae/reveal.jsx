// The five rarity reveals: what bursts out of her hands when a caught star shows what it is.
// 512 x 512, 1.6 s at 30 fps, light on black (the show adds it over the sky).

var PW = "CC Particle World";
function pw(id) { return "CC Particle World-" + id; }
var TYPE = { line: 1, star: 2, orb: 5 };

function particles(comp, name, o) {
    var l = addMode(solid(comp, name));
    var e = effect(l, PW);
    var guides = ["0051", "0052", "0053", "0055", "0060", "0061"];
    for (var g = 0; g < guides.length; g++) set(e, pw(guides[g]), 0);
    set(e, pw("0004"), o.rate);                         // Birth rate (keys allowed).
    set(e, pw("0005"), o.life);                         // Longevity.
    set(e, pw("0010"), o.radius || .01);
    set(e, pw("0011"), o.radius || .01);
    set(e, pw("0012"), o.radius || .01);
    set(e, pw("0015"), o.animation || 1);               // 1 explosive.
    set(e, pw("0016"), o.velocity);
    set(e, pw("0018"), o.gravity || 0);
    set(e, pw("0041"), o.resistance || 0);
    set(e, pw("0019"), o.extra === undefined ? .5 : o.extra);
    set(e, pw("0023"), o.type);
    set(e, pw("0024"), o.birth);
    set(e, pw("0025"), o.death);
    set(e, pw("0026"), o.variation || 60);
    set(e, pw("0027"), o.opacity || 100);
    set(e, pw("0029"), o.from);
    set(e, pw("0030"), o.to);
    set(e, pw("0104"), o.seed || 1);
    if (o.rotationSpeed !== undefined) set(e, pw("0043"), o.rotationSpeed);
    if (o.glow) glow(l, o.glow[0], o.glow[1], 30, o.glowA, o.glowB);
    return l;
}

function swirl(layer, angle) {
    var t = effect(layer, "ADBE Twirl");
    setAt(t, 1, [[0, 0], [1.6, angle]]);
    setAt(t, 2, 42);
    return t;
}

function reveal(name, c) {
    var size = 512, dur = 1.6;
    var comp = app.project.items.addComp("reveal_" + name, size, size, 1, dur, 30);
    comp.bgColor = [0, 0, 0];
    comp.motionBlur = true;
    var white = [1, 1, 1];

    // Lingering dust that drifts out slowly (the soft cloud).
    var dust = particles(comp, "dust", {rate: [[0, .9], [.3, .4], [.8, 0]], life: 1.4, velocity: .3 * c.power, resistance: 1.4,
                             animation: c.dustAnimation || 1, type: TYPE.orb, birth: .09, death: 0, opacity: 55,
                             from: c.light, to: c.colour, seed: 3, glow: [14, .9], glowA: c.colour, glowB: c.deep});
    // Sparks: fast streaks that slow down.
    var sparks = particles(comp, "sparks", {rate: [[0, 2.2 * c.power], [.05, 2.2 * c.power], [.09, 0]], life: 1.0,
                                            velocity: 1.6 * c.power, resistance: 3.2, gravity: .12, type: TYPE.line,
                                            birth: .045, death: 0, from: c.light, to: c.colour, seed: 7, glow: [9, 1.3], glowA: c.colour, glowB: c.deep});
    sparks.motionBlur = true;
    // Little four-point stars that twinkle out.
    particles(comp, "stars", {rate: [[0, .5 * c.power], [.2, .3], [.6, 0]], life: 1.3, velocity: .8 * c.power,
                              resistance: 2.4, type: TYPE.star, birth: .12, death: .02, rotationSpeed: 90,
                              from: white, to: c.accent || c.colour, seed: 11, glow: [8, 1.2],
                              glowA: c.accent || c.colour, glowB: c.colour});
    var extra = c.extraColours || [];
    for (var x = 0; x < extra.length; x++) {
        var tinted = particles(comp, "colour" + x, {rate: [[0, 1.1 * c.power], [.08, 1.1 * c.power], [.12, 0]],
                                   life: 1.25, velocity: (1.0 + .15 * x) * c.power, resistance: 2.6, type: TYPE.orb,
                                   birth: .05, death: 0, from: extra[x], to: c.colour, seed: 19 + x * 7,
                                   glow: [12, 1.2], glowA: extra[x], glowB: c.colour});
        if (c.swirl) swirl(tinted, c.swirl * (x % 2 ? -1 : 1));
    }
    if (c.swirl) swirl(dust, c.swirl);

    // The flash.
    var flash = orb(comp, "flash", 46, white, 10);
    scale(flash, [[0, [30, 30]], [.06, [150, 150]], [.4, [190, 190]]]);
    opacity(flash, [[0, 100], [.08, 95], [.4, 0]]);
    glow(flash, 30, 1.0, 20, c.colour, c.deep);
    if (c.flashes > 1) {                             // Moon: it flashes white twice.
        var again = orb(comp, "flash2", 60, white, 16);
        scale(again, [[.3, [40, 40]], [.38, [200, 200]], [.75, [240, 240]]]);
        opacity(again, [[.3, 0], [.34, 90], [.75, 0]]);
        glow(again, 40, 1.0, 20, c.colour, c.deep);
    }
    var halo = orb(comp, "halo", 200, c.colour, 60);
    scale(halo, [[0, [10, 10]], [.15, [90, 90]], [1.3, [130, 130]]]);
    opacity(halo, [[0, 0], [.06, 45 * c.halo], [1.5, 0]]);

    // Shock rings.
    for (var r = 0; r < c.rings; r++) {
        var at = r * .09;
        var ringLayer = ring(comp, "ring" + r, 200, r === 0 ? white : c.colour, r === 0 ? 7 : 4, r === 0 ? 2 : 3);
        scale(ringLayer, [[at, [8, 8]], [at + .55, [210 - r * 30, 210 - r * 30]]]);
        opacity(ringLayer, [[at, 0], [at + .03, 100], [at + .6, 0]]);
        glow(ringLayer, 14, 1.2, 20, c.colour, c.deep);
    }

    // Lens streak and star spikes.
    var streakLayer = bar(comp, "streak", 500, 7, c.light, 3, 0);
    scale(streakLayer, [[0, [10, 100]], [.12, [100, 100]], [.9, [130, 60]]]);
    opacity(streakLayer, [[0, 0], [.04, 100], [.9, 0]]);
    glow(streakLayer, 10, 1.0, 20, c.colour, c.deep);
    for (var s = 0; s < c.spikes; s++) {
        var angle = 180 / c.spikes * s + 45;
        var spike = bar(comp, "spike" + s, 320, 4, white, 2, angle);
        scale(spike, [[0, [10, 100]], [.1, [100, 100]], [1.0, [70, 80]]]);
        rotate(spike, [[0, angle], [1.6, angle + 25]]);
        opacity(spike, [[0, 0], [.05, 90], [1.0, 0]]);
        glow(spike, 8, 1.0, 20, c.colour, c.deep);
    }

    // God rays from everything above, then one glow over all.
    var rays = comp.layers.addSolid([0, 0, 0], "rays", size, size, 1);
    rays.adjustmentLayer = true;
    var rb = effect(rays, "CC Radial Fast Blur");           // God rays: everything smeared outwards.
    set(rb, "CC Radial Fast Blur-0001", [size / 2, size / 2]);
    set(rb, "CC Radial Fast Blur-0002", [[0, 70 * c.rays], [.8, 45 * c.rays], [1.6, 20]]);
    rays.property("ADBE Transform Group").property("ADBE Opacity").setValue(60);
    var top = comp.layers.addSolid([0, 0, 0], "bloom", size, size, 1);
    top.adjustmentLayer = true;
    glow(top, 50, .45, 60, c.colour, c.deep);
    vignette(comp, .78);
    render(comp, "reveal_" + name);
}

log("reveals");
reveal("fanxing", {deep: [.1, .15, .7], colour: [.25, .45, 1], light: [.7, .82, 1], accent: [.55, .7, 1], power: .7, rings: 1, spikes: 2,
                   halo: .6, rays: .6});
reveal("mingyue", {deep: [.45, .7, 1], colour: [.85, .92, 1], light: [1, 1, 1], accent: [.6, .85, 1], power: .85, rings: 2, spikes: 2,
                   halo: 1.0, rays: .8, flashes: 2});
reveal("haori", {deep: [1, .35, .05], colour: [1, .62, .16], light: [1, .9, .6], accent: [1, .8, .35], power: 1.05, rings: 2, spikes: 4,
                 halo: .9, rays: 1.2});
reveal("yinhe", {deep: [.4, .42, .9], colour: [.62, .72, 1], light: [.92, .95, 1], accent: [.8, .86, 1], power: 1.2, rings: 3, spikes: 3,
                 halo: .9, rays: 1.1, swirl: 220, extraColours: [[.75, .6, 1], [.6, .85, 1]]});
reveal("xinghai", {deep: [.3, .8, 1], colour: [.85, .55, 1], light: [1, .95, 1], accent: [.5, 1, .9], power: 1.4, rings: 3, spikes: 3,
                   halo: 1.0, rays: 1.3, swirl: 120,
                   extraColours: [[1, .55, .8], [.45, .9, 1], [1, .85, .4], [.6, 1, .65]]});
app.project.renderQueue.render();
log("rendered");
