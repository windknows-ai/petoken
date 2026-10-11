// Shared helpers for the wishing-show After Effects builds (run with AfterFX.exe -noui -r).
// After Effects here is localised, so every property is found by its match name.

var ROOT = "D:/Documents/ChatGPT/petoken-claude/build/ae_out";

function log(s) {
    var f = new File(ROOT + "/log.txt");
    f.encoding = "UTF-8";
    f.open("a");
    f.writeln(s);
    f.close();
}

function findProp(group, match) {
    for (var i = 1; i <= group.numProperties; i++) {
        var p = group.property(i);
        if (p.matchName === match) return p;
        if (p.propertyType !== PropertyType.PROPERTY) {
            var inner = findProp(p, match);
            if (inner) return inner;
        }
    }
    return null;
}

// set(effect, "CC Particle World-0004", 30) or a list of [time, value] keys.
function set(effect, match, value) {
    var p = findProp(effect, match);
    if (!p) { log("  missing " + match + " on " + effect.matchName); return null; }
    try {
        if (value instanceof Array && value.length && value[0] instanceof Array) {
            for (var k = 0; k < value.length; k++) p.setValueAtTime(value[k][0], value[k][1]);
        } else {
            p.setValue(value);
        }
    } catch (e) { log("  cannot set " + match + ": " + e.toString()); }
    return p;
}

// By position, for effects whose inner match names are unknown: setAt(effect, 1, value or keys).
function setAt(fx, index, value) {
    var p = fx.property(index);
    if (!p) { log("  no property " + index + " on " + fx.matchName); return null; }
    try {
        if (value instanceof Array && value.length && value[0] instanceof Array) {
            for (var k = 0; k < value.length; k++) p.setValueAtTime(value[k][0], value[k][1]);
        } else {
            p.setValue(value);
        }
    } catch (e) { log("  cannot set " + index + " on " + fx.matchName + ": " + e.toString()); }
    return p;
}

function effect(layer, match) {
    return layer.property("ADBE Effect Parade").addProperty(match);
}

function keys(prop, list, ease) {
    for (var k = 0; k < list.length; k++) prop.setValueAtTime(list[k][0], list[k][1]);
    if (ease) {
        for (var n = 1; n <= prop.numKeys; n++) {
            try {
                var e = new KeyframeEase(0, ease);
                var dims = prop.value instanceof Array ? prop.value.length : 1;
                var arr = [];
                for (var d = 0; d < (prop.propertyValueType === PropertyValueType.TwoD_SPATIAL ||
                                     prop.propertyValueType === PropertyValueType.ThreeD_SPATIAL ? 1 : dims); d++) arr.push(e);
                prop.setTemporalEaseAtKey(n, arr, arr);
            } catch (err) {}
        }
    }
}

function solid(comp, name, colour) {
    var l = comp.layers.addSolid(colour || [0, 0, 0], name, comp.width, comp.height, 1);
    return l;
}

function addMode(layer) {
    layer.blendingMode = BlendingMode.ADD;
    return layer;
}

// A soft round light: a frame-sized solid with a feathered round mask (never clipped square).
function orb(comp, name, size, colour, blur) {
    var l = comp.layers.addSolid(colour, name, comp.width, comp.height, 1);
    var mask = l.property("ADBE Mask Parade").addProperty("ADBE Mask Atom");
    var shape = new Shape();
    var r = size / 2, cx = comp.width / 2, cy = comp.height / 2, k = .5523 * r;
    shape.vertices = [[cx, cy - r], [cx + r, cy], [cx, cy + r], [cx - r, cy]];
    shape.inTangents = [[-k, 0], [0, -k], [k, 0], [0, k]];
    shape.outTangents = [[k, 0], [0, k], [-k, 0], [0, -k]];
    shape.closed = true;
    mask.property("ADBE Mask Shape").setValue(shape);
    var feather = Math.max(1, (blur || 0) * 2.2);
    mask.property("ADBE Mask Feather").setValue([feather, feather]);
    addMode(l);
    return l;
}

// A ring: an ellipse stroke.
function ring(comp, name, size, colour, width, blur) {
    var l = comp.layers.addShape();
    l.name = name;
    var group = l.property("ADBE Root Vectors Group").addProperty("ADBE Vector Group");
    var vectors = group.property("ADBE Vectors Group");
    var ellipse = vectors.addProperty("ADBE Vector Shape - Ellipse");
    ellipse.property("ADBE Vector Ellipse Size").setValue([size, size]);
    var stroke = vectors.addProperty("ADBE Vector Graphic - Stroke");
    stroke.property("ADBE Vector Stroke Color").setValue(colour);
    stroke.property("ADBE Vector Stroke Width").setValue(width);
    if (blur) set(effect(l, "ADBE Gaussian Blur 2"), "ADBE Gaussian Blur 2-0001", blur);
    l.property("ADBE Transform Group").property("ADBE Position").setValue([comp.width / 2, comp.height / 2]);
    addMode(l);
    return l;
}

// A thin bar of light (lens streaks, star spikes).
function bar(comp, name, w, h, colour, blur, angle) {
    var l = comp.layers.addShape();
    l.name = name;
    var group = l.property("ADBE Root Vectors Group").addProperty("ADBE Vector Group");
    var vectors = group.property("ADBE Vectors Group");
    var rect = vectors.addProperty("ADBE Vector Shape - Ellipse");
    rect.property("ADBE Vector Ellipse Size").setValue([w, h]);
    var fill = vectors.addProperty("ADBE Vector Graphic - Fill");
    fill.property("ADBE Vector Fill Color").setValue(colour);
    if (blur) set(effect(l, "ADBE Gaussian Blur 2"), "ADBE Gaussian Blur 2-0001", blur);
    var tr = l.property("ADBE Transform Group");
    tr.property("ADBE Position").setValue([comp.width / 2, comp.height / 2]);
    if (angle) tr.property("ADBE Rotate Z").setValue(angle);
    addMode(l);
    return l;
}

function glow(layer, radius, intensity, threshold, a, b) {
    var g = effect(layer, "ADBE Glo2");
    set(g, "ADBE Glo2-0002", threshold === undefined ? 40 : threshold);
    set(g, "ADBE Glo2-0003", radius);
    set(g, "ADBE Glo2-0004", intensity);
    if (a) {                                    // Tinted glow: colours A and B instead of the layer's own.
        set(g, "ADBE Glo2-0007", 2);
        set(g, "ADBE Glo2-0012", a);
        set(g, "ADBE Glo2-0013", b || a);
    }
    return g;
}

// Darken everything towards the edges so the light ends in pure black well inside the frame.
function vignette(comp, inner) {
    var l = comp.layers.addSolid([0, 0, 0], "edge", comp.width, comp.height, 1);
    var mask = l.property("ADBE Mask Parade").addProperty("ADBE Mask Atom");
    var shape = new Shape();
    var r = comp.width * inner / 2, cx = comp.width / 2, cy = comp.height / 2, k = .5523 * r;
    shape.vertices = [[cx, cy - r], [cx + r, cy], [cx, cy + r], [cx - r, cy]];
    shape.inTangents = [[-k, 0], [0, -k], [k, 0], [0, k]];
    shape.outTangents = [[k, 0], [0, k], [-k, 0], [0, -k]];
    shape.closed = true;
    mask.property("ADBE Mask Shape").setValue(shape);
    mask.inverted = true;
    mask.property("ADBE Mask Feather").setValue([comp.width * .22, comp.width * .22]);
    return l;
}

function opacity(layer, list) {
    keys(layer.property("ADBE Transform Group").property("ADBE Opacity"), list);
}

function scale(layer, list) {
    keys(layer.property("ADBE Transform Group").property("ADBE Scale"), list);
}

function rotate(layer, list) {
    keys(layer.property("ADBE Transform Group").property("ADBE Rotate Z"), list);
}

// Render a comp to a TIFF sequence: <ROOT>/<name>/<name>_00000.tif
function render(comp, name) {
    var folder = new Folder(ROOT + "/" + name);
    if (!folder.exists) folder.create();
    var item = app.project.renderQueue.items.add(comp);
    try { item.applyTemplate("最佳设置"); } catch (e) {}
    var om = item.outputModule(1);
    var templates = om.templates;
    for (var i = 0; i < templates.length; i++) {
        if (templates[i].indexOf("TIFF") >= 0) { om.applyTemplate(templates[i]); break; }
    }
    om.file = new File(ROOT + "/" + name + "/" + name + "_[#####].tif");
    return item;
}
