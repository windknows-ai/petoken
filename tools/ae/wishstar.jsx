// The wishing star she catches (a 2 s loop the show plays twice offset, so it never pops),
// and the charge: light pouring into her hands (rendered as a burst, played backwards).

function particleLayer(comp, name, o) {
    var l = addMode(solid(comp, name));
    var e = effect(l, "CC Particle World");
    var guides = ["0051", "0052", "0053", "0055", "0060", "0061"];
    for (var g = 0; g < guides.length; g++) set(e, "CC Particle World-" + guides[g], 0);
    set(e, "CC Particle World-0004", o.rate);
    set(e, "CC Particle World-0005", o.life);
    set(e, "CC Particle World-0010", o.radius || .02);
    set(e, "CC Particle World-0011", o.radius || .02);
    set(e, "CC Particle World-0012", o.radius || .02);
    set(e, "CC Particle World-0016", o.velocity);
    set(e, "CC Particle World-0018", o.gravity || 0);
    set(e, "CC Particle World-0041", o.resistance || 0);
    set(e, "CC Particle World-0023", o.type);
    set(e, "CC Particle World-0024", o.birth);
    set(e, "CC Particle World-0025", o.death);
    set(e, "CC Particle World-0027", o.opacity || 100);
    set(e, "CC Particle World-0029", o.from);
    set(e, "CC Particle World-0030", o.to);
    set(e, "CC Particle World-0104", o.seed || 1);
    if (o.glow) glow(l, o.glow, 1.1, 30, o.to, o.from);
    return l;
}

function wishStar() {
    var size = 256, dur = 4;                       // Rendered 4 s; the middle 2 s are kept (particles settled).
    var comp = app.project.items.addComp("wishstar", size, size, 1, dur, 30);
    comp.bgColor = [0, 0, 0];
    var warm = [1, .93, .78], ice = [.72, .86, 1], white = [1, 1, 1];
    particleLayer(comp, "motes", {rate: .5, life: 1.2, velocity: .12, resistance: .5, type: 2, birth: .1, death: 0,
                                   from: white, to: ice, seed: 5, glow: 6});
    particleLayer(comp, "dust", {rate: .8, life: .9, velocity: .06, type: 5, birth: .07, death: 0, opacity: 60,
                                  from: warm, to: [.75, .65, 1], seed: 9, glow: 10});
    var halo = orb(comp, "halo", 90, [.5, .58, 1], 30);
    opacity(halo, [[0, 55], [.5, 70], [1, 55], [1.5, 70], [2, 55], [2.5, 70], [3, 55], [3.5, 70], [4, 55]]);
    var core = orb(comp, "core", 16, white, 4);
    glow(core, 24, 1.5, 20, warm, ice);
    scale(core, [[0, [100, 100]], [.25, [118, 118]], [.5, [100, 100]], [.75, [115, 115]], [1, [100, 100]],
                 [1.25, [118, 118]], [1.5, [100, 100]], [1.75, [115, 115]], [2, [100, 100]], [2.25, [118, 118]],
                 [2.5, [100, 100]], [2.75, [115, 115]], [3, [100, 100]], [3.25, [118, 118]], [3.5, [100, 100]],
                 [3.75, [115, 115]], [4, [100, 100]]]);
    // Long and short spikes turning slowly in opposite ways: the twinkle.
    for (var k = 0; k < 4; k++) {
        var isLong = k < 2;
        var angle = isLong ? k * 90 : 45 + (k - 2) * 90;
        var spike = bar(comp, "spike" + k, isLong ? 210 : 110, isLong ? 3 : 2.2, white, 1.5, angle);
        glow(spike, 8, 1.2, 20, warm, ice);
        rotate(spike, [[0, angle], [dur, angle + (isLong ? 45 : -60)]]);
        opacity(spike, [[0, isLong ? 95 : 70], [.7, isLong ? 70 : 95], [1.4, isLong ? 95 : 60], [2, isLong ? 75 : 90],
                        [2.7, isLong ? 95 : 65], [3.4, isLong ? 70 : 95], [4, isLong ? 95 : 70]]);
    }
    var streakLayer = bar(comp, "streak", 250, 3, ice, 2, 0);
    glow(streakLayer, 6, 1.0, 20, ice, white);
    opacity(streakLayer, [[0, 50], [1, 80], [2, 50], [3, 80], [4, 50]]);
    var top = comp.layers.addSolid([0, 0, 0], "bloom", size, size, 1);
    top.adjustmentLayer = true;
    glow(top, 30, .5, 60, ice, warm);
    vignette(comp, .9);
    var item = render(comp, "wishstar");
    item.timeSpanStart = 1; item.timeSpanDuration = 2;
}

function charge() {
    var size = 320, dur = .7;
    var comp = app.project.items.addComp("charge", size, size, 1, dur, 30);
    comp.bgColor = [0, 0, 0];
    var white = [1, 1, 1], ice = [.7, .84, 1], warm = [1, .9, .7];
    particleLayer(comp, "streams", {rate: [[0, 1], [.05, 1], [.08, 0]], life: .7, velocity: 1.1, resistance: 1.2,
                                     type: 1, birth: .04, death: .01, from: white, to: ice, seed: 3, glow: 8});
    particleLayer(comp, "motes", {rate: [[0, .5], [.05, .5], [.08, 0]], life: .7, velocity: .8, resistance: .8,
                                   type: 2, birth: .08, death: .02, from: warm, to: ice, seed: 8, glow: 6});
    var ringLayer = ring(comp, "ring", 120, ice, 3, 2);
    scale(ringLayer, [[0, [20, 20]], [.6, [230, 230]]]);
    opacity(ringLayer, [[0, 90], [.6, 0]]);
    glow(ringLayer, 10, 1.0, 20, ice, white);
    vignette(comp, .88);
    render(comp, "charge");
}

log("wishstar");
wishStar();
charge();
app.project.renderQueue.render();
log("rendered");
