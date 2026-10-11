// Light pillars (the opening: a beam shoots up from the catch; the result cards: a beam that stays)
// and the five star emblems (the found stars circling her, the light behind each card).

var RARITY = {
    fanxing: {colour: [.28, .48, 1], deep: [.1, .16, .7], light: [.75, .85, 1], power: .6},
    mingyue: {colour: [.88, .94, 1], deep: [.45, .7, 1], light: [1, 1, 1], power: .8},
    haori: {colour: [1, .66, .2], deep: [1, .36, .05], light: [1, .92, .65], power: 1},
    yinhe: {colour: [.66, .76, 1], deep: [.42, .44, .95], light: [.94, .96, 1], power: 1.15},
    xinghai: {colour: [.88, .6, 1], deep: [.3, .8, 1], light: [1, .96, 1], power: 1.35}
};
var NAMES = ["fanxing", "mingyue", "haori", "yinhe", "xinghai"];

function beam(comp, c, height, width, coreWidth) {
    var cx = comp.width / 2;
    var soft = orb(comp, "beam", width, c.colour, width * .45);
    at(soft, cx, comp.height - height / 2);
    soft.property("ADBE Transform Group").property("ADBE Scale").setValue([100, height / width * 100]);
    glow(soft, 30, .8, 20, c.colour, c.deep);
    var core = orb(comp, "core", coreWidth, c.light, coreWidth * .5);
    at(core, cx, comp.height - height / 2);
    core.property("ADBE Transform Group").property("ADBE Scale").setValue([100, height / coreWidth * 100]);
    glow(core, 12, 1.1, 20, c.colour, c.light);
    return [soft, core];
}

// The opening beam: 1.4 s, 256 x 1024, grows up from the bottom and fades.
function pillar(name) {
    var c = RARITY[name];
    var comp = app.project.items.addComp("pillar_" + name, 256, 1024, 1, 1.4, 30);
    comp.bgColor = [0, 0, 0];
    var parts = beam(comp, c, 980, 70 + 30 * c.power, 10 + 6 * c.power);
    for (var k = 0; k < parts.length; k++) {
        var tr = parts[k].property("ADBE Transform Group");
        var s = tr.property("ADBE Scale").value;
        keys(tr.property("ADBE Scale"), [[0, [s[0] * .4, 2]], [.22, [s[0] * 1.15, s[1]]], [1.4, [s[0] * .6, s[1]]]]);
        keys(tr.property("ADBE Position"), [[0, [128, 1012]], [.22, [128, 1024 - 490]]]);
        keys(tr.property("ADBE Opacity"), [[0, 0], [.04, 100], [.5, 90], [1.4, 0]]);
    }
    var base = ring(comp, "base", 150, c.light, 5, 3);
    at(base, 128, 990);
    keys(base.property("ADBE Transform Group").property("ADBE Scale"), [[0, [20, 6]], [.5, [160, 40]]]);
    keys(base.property("ADBE Transform Group").property("ADBE Opacity"), [[0, 100], [.6, 0]]);
    glow(base, 10, 1.2, 20, c.colour, c.deep);
    var motes = emitter(comp, "motes", {rate: [[0, 1.4 * c.power], [.5, .8], [1.0, 0]], life: 1.2, y: .36, rx: .05,
                                        ry: .02, velocity: .2, gravity: -.45, resistance: .3, type: 2, birth: .05,
                                        death: 0, from: c.light, to: c.colour, seed: 5, glow: [6, 1.2],
                                        glowA: c.colour, glowB: c.deep});
    var flash = orb(comp, "flash", 90, [1, 1, 1], 30);
    at(flash, 128, 985);
    keys(flash.property("ADBE Transform Group").property("ADBE Opacity"), [[0, 100], [.35, 0]]);
    vignette(comp, .96);
    render(comp, "pillar_" + name);
}

// The beam behind a result card: a 1 s loop (rendered 3 s, the middle kept), 192 x 768.
function pillarLoop(name) {
    var c = RARITY[name];
    var comp = app.project.items.addComp("cardbeam_" + name, 192, 768, 1, 3, 30);
    comp.bgColor = [0, 0, 0];
    var parts = beam(comp, c, 700, 34 + 14 * c.power, 4 + 3 * c.power);
    keys(parts[0].property("ADBE Transform Group").property("ADBE Opacity"),
         [[0, 70], [.5, 90], [1, 70], [1.5, 90], [2, 70], [2.5, 90], [3, 70]]);
    emitter(comp, "rising", {rate: .9 * c.power, life: 1.4, y: .3, rx: .06, ry: .25, velocity: .05, gravity: -.3,
                             type: 5, birth: .05, death: 0, opacity: 80, from: c.light, to: c.colour, seed: 7,
                             glow: [6, 1.1], glowA: c.colour, glowB: c.deep});
    emitter(comp, "glints", {rate: .35 * c.power, life: 1.2, y: .3, rx: .05, ry: .25, velocity: .04, gravity: -.25,
                             type: 2, birth: .07, death: 0, from: [1, 1, 1], to: c.light, seed: 9,
                             glow: [5, 1.2], glowA: c.colour, glowB: c.light});
    vignette(comp, .96);
    var item = render(comp, "cardbeam_" + name);
    item.timeSpanStart = 1; item.timeSpanDuration = 1;
}

// A crescent: a white disc with an offset disc cut out of it.
function crescent(comp, size, colour) {
    var l = comp.layers.addSolid(colour, "crescent", comp.width, comp.height, 1);
    var cx = comp.width / 2, cy = comp.height / 2;
    var masks = [[cx, cy, size / 2, MaskMode.ADD], [cx + size * .28, cy - size * .14, size * .44, MaskMode.SUBTRACT]];
    for (var m = 0; m < masks.length; m++) {
        var mk = l.property("ADBE Mask Parade").addProperty("ADBE Mask Atom");
        var sh = new Shape(), r = masks[m][2], k = .5523 * r, x = masks[m][0], y = masks[m][1];
        sh.vertices = [[x, y - r], [x + r, y], [x, y + r], [x - r, y]];
        sh.inTangents = [[-k, 0], [0, -k], [k, 0], [0, k]];
        sh.outTangents = [[k, 0], [0, k], [-k, 0], [0, -k]];
        sh.closed = true;
        mk.property("ADBE Mask Shape").setValue(sh);
        mk.maskMode = masks[m][3];
        mk.property("ADBE Mask Feather").setValue([2, 2]);
    }
    addMode(l);
    return l;
}

// The star emblems: 2 s loops (rendered 4 s, the middle kept), 256 x 256.
function emblem(name) {
    var c = RARITY[name];
    var comp = app.project.items.addComp("emblem_" + name, 256, 256, 1, 4, 30);
    comp.bgColor = [0, 0, 0];
    var white = [1, 1, 1], k, sp;
    var halo = orb(comp, "halo", 110, c.deep, 46);
    if (name === "yinhe" || name === "xinghai") halo.property("ADBE Transform Group").property("ADBE Opacity").setValue(35);
    keys(halo.property("ADBE Transform Group").property("ADBE Opacity"), [[0, 55], [1, 75], [2, 55], [3, 75], [4, 55]]);
    if (name === "fanxing") {                      // A sapphire four-point star.
        for (k = 0; k < 4; k++) {
            sp = bar(comp, "spike" + k, k < 2 ? 190 : 90, k < 2 ? 5 : 3, k < 2 ? c.light : c.colour, 1.5, k < 2 ? k * 90 : 45 + (k - 2) * 90);
            glow(sp, 8, 1.2, 20, c.colour, c.deep);
            rotate(sp, [[0, k < 2 ? k * 90 : 45 + (k - 2) * 90], [4, (k < 2 ? k * 90 : 45 + (k - 2) * 90) + 20]]);
        }
        var gem = orb(comp, "gem", 26, c.light, 4);
        glow(gem, 18, 1.4, 20, c.colour, c.deep);
    } else if (name === "mingyue") {               // A crescent moon that flashes white.
        var moon = crescent(comp, 110, [.97, .98, 1]);
        glow(moon, 22, 1.3, 30, c.light, c.deep);
        keys(moon.property("ADBE Transform Group").property("ADBE Opacity"),
             [[0, 85], [.5, 100], [.6, 85], [1.5, 85], [2, 100], [2.1, 85], [3, 85], [3.5, 100], [3.6, 85], [4, 85]]);
        var halo2 = ring(comp, "moon halo", 200, c.colour, 2, 3);
        glow(halo2, 10, .9, 20, c.colour, c.deep);
    } else if (name === "haori") {                 // A small sun with turning rays.
        for (k = 0; k < 12; k++) {
            sp = bar(comp, "ray" + k, k % 2 ? 150 : 210, k % 2 ? 3 : 5, c.light, 2, k * 15);
            glow(sp, 6, 1, 20, c.colour, c.deep);
            rotate(sp, [[0, k * 15], [4, k * 15 + 30]]);
            sp.property("ADBE Transform Group").property("ADBE Opacity").setValue(k % 2 ? 55 : 80);
        }
        var sun = orb(comp, "sun", 64, [1, .95, .8], 10);
        glow(sun, 30, 1.4, 20, c.colour, c.deep);
    } else if (name === "yinhe") {                 // A silver spiral galaxy, tilted, turning.
        var galaxy = picture(comp, "D:/Documents/ChatGPT/petoken-claude/build/wish_fx_png/hero_yinhe.png");
        galaxy.threeDLayer = true;
        var gt = galaxy.property("ADBE Transform Group");
        gt.property("ADBE Position").setValue([128, 128, 0]);
        gt.property("ADBE Scale").setValue([52, 52, 52]);
        gt.property("ADBE Rotate X").setValue(58);
        gt.property("ADBE Orientation").setValue([0, 0, 340]);
        keys(gt.property("ADBE Rotate Z"), [[0, 0], [4, 48]]);
        var bulge = orb(comp, "bulge", 16, [1, .97, .92], 6);
        bulge.property("ADBE Transform Group").property("ADBE Opacity").setValue(60);
    } else {                                       // A prism star in turning rainbow rings.
        for (k = 0; k < 2; k++) {
            var rings = picture(comp, "D:/Documents/ChatGPT/petoken-claude/build/wish_fx_png/hero_xinghai_ring.png");
            rings.threeDLayer = true;
            var rt = rings.property("ADBE Transform Group");
            rt.property("ADBE Position").setValue([128, 128, 0]);
            rt.property("ADBE Scale").setValue([k ? 34 : 46, k ? 34 : 46, 46]);
            rt.property("ADBE Rotate X").setValue(k ? 40 : 64);
            rt.property("ADBE Orientation").setValue([0, 0, k ? 30 : 345]);
            keys(rt.property("ADBE Rotate Z"), [[0, 0], [4, k ? -110 : 90]]);
            if (k) rt.property("ADBE Opacity").setValue(70);
        }
        var prism = picture(comp, "D:/Documents/ChatGPT/petoken-claude/build/wish_fx_png/hero_xinghai.png");
        prism.property("ADBE Transform Group").property("ADBE Position").setValue([128, 128]);
        prism.property("ADBE Transform Group").property("ADBE Scale").setValue([30, 30]);
        keys(prism.property("ADBE Transform Group").property("ADBE Rotate Z"), [[0, 0], [4, 24]]);
        var core = orb(comp, "core", 12, white, 3);
    }
    emitter(comp, "sparkles", {rate: .25 + .15 * c.power, life: 1.4, rx: .12, ry: .12, velocity: .05, type: 2,
                               birth: .07, death: 0, from: white, to: c.colour, seed: 13, glow: [5, 1.1],
                               glowA: c.colour, glowB: c.light});
    vignette(comp, .95);
    var item = render(comp, "emblem_" + name);
    item.timeSpanStart = 1; item.timeSpanDuration = 2;
}

log("pillars");
for (var n = 0; n < NAMES.length; n++) {
    pillar(NAMES[n]);
    pillarLoop(NAMES[n]);
    emblem(NAMES[n]);
}
app.project.renderQueue.render();
log("rendered");
