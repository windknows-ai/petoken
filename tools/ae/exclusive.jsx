// The two top rarities have their own opening before the burst: 960 x 540, 2.2 s, light on black.
//   exclusive_yinhe   - a silver galaxy sweeps in turning from far away, its arms pour into the centre
//   exclusive_xinghai - rainbow rings ripple out, prismatic sparks fly, rays, a prism flash

var PNG = "D:/Documents/ChatGPT/petoken-claude/build/wish_fx_png/";
var EW = 960, EH = 540, DUR = 2.2;

function galaxyOpening() {
    var comp = app.project.items.addComp("exclusive_yinhe", EW, EH, 1, DUR, 30);
    comp.bgColor = [0, 0, 0];
    var silver = [.72, .8, 1], deep = [.4, .44, .95], white = [1, 1, 1];
    for (var k = 0; k < 2; k++) {
        var g = picture(comp, PNG + "hero_yinhe.png");
        g.threeDLayer = true;
        var t = g.property("ADBE Transform Group");
        t.property("ADBE Position").setValue([EW / 2, EH / 2, 0]);
        t.property("ADBE Rotate X").setValue(k ? 50 : 62);
        t.property("ADBE Orientation").setValue([0, 0, k ? 20 : 335]);
        keys(t.property("ADBE Scale"), k ? [[0, [60, 60, 60]], [DUR, [260, 260, 260]]] : [[0, [20, 20, 20]], [1.6, [210, 210, 210]], [DUR, [240, 240, 240]]]);
        keys(t.property("ADBE Rotate Z"), [[0, 0], [DUR, k ? -60 : 140]]);
        keys(t.property("ADBE Opacity"), k ? [[0, 0], [.6, 35], [1.8, 30], [DUR, 0]] : [[0, 0], [.3, 100], [1.7, 90], [DUR, 0]]);
    }
    // Star streams falling into the centre (a burst played in reverse would need a second comp;
    // here the streams spiral in under a twirl).
    var streams = emitter(comp, "streams", {rate: [[0, 0], [.3, 2.4], [1.5, 2.4], [1.7, 0]], life: 1.0, rx: .9, ry: .5,
                                            velocity: .05, gravity: 0, type: 1, birth: .04, death: .01,
                                            from: white, to: silver, seed: 4, glow: [6, 1.2], glowA: silver, glowB: deep});
    var tw = effect(streams, "ADBE Twirl");
    setAt(tw, 1, [[0, 0], [DUR, 260]]);
    setAt(tw, 2, 70);
    var flash = orb(comp, "flash", 120, white, 40);
    keys(flash.property("ADBE Transform Group").property("ADBE Scale"), [[1.75, [10, 10]], [1.95, [380, 380]], [DUR, [480, 480]]]);
    keys(flash.property("ADBE Transform Group").property("ADBE Opacity"), [[1.7, 0], [1.85, 100], [DUR, 0]]);
    glow(flash, 60, 1, 20, silver, deep);
    var rays = comp.layers.addSolid([0, 0, 0], "rays", EW, EH, 1);
    rays.adjustmentLayer = true;
    var rb = effect(rays, "CC Radial Fast Blur");
    set(rb, "CC Radial Fast Blur-0001", [EW / 2, EH / 2]);
    set(rb, "CC Radial Fast Blur-0002", [[0, 20], [1.8, 60], [DUR, 30]]);
    rays.property("ADBE Transform Group").property("ADBE Opacity").setValue(55);
    vignette(comp, .98);
    render(comp, "exclusive_yinhe");
}

function prismOpening() {
    var comp = app.project.items.addComp("exclusive_xinghai", EW, EH, 1, DUR, 30);
    comp.bgColor = [0, 0, 0];
    var white = [1, 1, 1], hues = [[1, .5, .78], [.5, .85, 1], [1, .85, .45], [.6, 1, .72], [.78, .58, 1]];
    for (var k = 0; k < 5; k++) {                 // Rainbow rings rippling out, one after another.
        var start = k * .28;
        var r = picture(comp, PNG + "hero_xinghai_ring.png");
        r.threeDLayer = true;
        var t = r.property("ADBE Transform Group");
        t.property("ADBE Position").setValue([EW / 2, EH / 2, 0]);
        t.property("ADBE Rotate X").setValue(55 + k * 4);
        keys(t.property("ADBE Scale"), [[start, [10, 10, 10]], [start + 1.2, [320, 320, 320]]]);
        keys(t.property("ADBE Rotate Z"), [[start, k * 30], [start + 1.2, k * 30 + (k % 2 ? -90 : 90)]]);
        keys(t.property("ADBE Opacity"), [[start, 0], [start + .1, 100], [start + 1.2, 0]]);
    }
    for (var c = 0; c < hues.length; c++) {        // Prismatic sparks in every colour.
        emitter(comp, "sparks" + c, {rate: [[0, 0], [.2, .9], [1.4, .9], [1.6, 0]], life: 1.1, velocity: 1.1,
                                     resistance: 1.4, type: c % 2 ? 2 : 5, birth: .05, death: 0, from: white,
                                     to: hues[c], seed: 11 + c * 5, glow: [8, 1.2], glowA: hues[c], glowB: hues[(c + 2) % 5]});
    }
    var prism = picture(comp, PNG + "hero_xinghai.png");
    var pt = prism.property("ADBE Transform Group");
    pt.property("ADBE Position").setValue([EW / 2, EH / 2]);
    keys(pt.property("ADBE Scale"), [[0, [20, 20]], [1.7, [70, 70]], [1.9, [160, 160]], [DUR, [120, 120]]]);
    keys(pt.property("ADBE Rotate Z"), [[0, 0], [DUR, 50]]);
    keys(pt.property("ADBE Opacity"), [[0, 40], [1.7, 90], [1.9, 100], [DUR, 0]]);
    var flash = orb(comp, "flash", 120, white, 40);
    keys(flash.property("ADBE Transform Group").property("ADBE Scale"), [[1.75, [10, 10]], [1.95, [420, 420]], [DUR, [520, 520]]]);
    keys(flash.property("ADBE Transform Group").property("ADBE Opacity"), [[1.7, 0], [1.85, 100], [DUR, 0]]);
    glow(flash, 60, 1, 20, [1, .7, 1], [.5, .9, 1]);
    var rays = comp.layers.addSolid([0, 0, 0], "rays", EW, EH, 1);
    rays.adjustmentLayer = true;
    var rb = effect(rays, "CC Radial Fast Blur");
    set(rb, "CC Radial Fast Blur-0001", [EW / 2, EH / 2]);
    set(rb, "CC Radial Fast Blur-0002", [[0, 30], [1.8, 70], [DUR, 35]]);
    rays.property("ADBE Transform Group").property("ADBE Opacity").setValue(60);
    vignette(comp, .98);
    render(comp, "exclusive_xinghai");
}

log("exclusive");
galaxyOpening();
prismOpening();
app.project.renderQueue.render();
log("rendered");
