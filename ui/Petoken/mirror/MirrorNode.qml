import QtQuick
import Petoken

// One mirrored widget or layout (widget_mirror.Mirror): picks how to draw it from its kind.
// A widget arrives as its spec ({ref: true, id, t, sizing}); its whole node (its layout, its
// children's specs) is asked for by id, again only when that widget's own structure changed,
// and what it shows is asked for only when that changed. So a page that rebuilds one part
// redraws only that part.
Item {
    id: root
    property var node: ({})                              // What the parent hands over.
    property var m: null
    property var full: ({})                              // The whole node, for the piece itself.
    property var val: ({})
    property string _spec: ""
    readonly property string ident: node && node.id ? node.id : ""

    function resolve() {
        full = node && node.ref && m ? m.nodeOf(node.id) : (node || ({}))
    }
    function refresh() { val = (m && ident) ? m.value(ident) : ({}) }
    onNodeChanged: {
        const spec = JSON.stringify(node)
        if (spec === _spec) return                       // Same piece, handed over again.
        _spec = spec
        resolve()
        refresh()
    }
    onMChanged: { resolve(); refresh() }
    Connections {
        target: root.m
        function onUpdated() { if (root.ident && root.m.isUpdated(root.ident)) root.refresh() }
        function onReshaped() { if (root.ident && root.m.isReshaped(root.ident)) root.resolve() }
    }
    readonly property bool shown: !ident || val.v !== false
    visible: shown
    implicitWidth: body.item ? body.item.implicitWidth : 0
    implicitHeight: body.item ? body.item.implicitHeight : 0

    Loader {
        id: body
        anchors.fill: parent
        asynchronous: true                               // Big pages build over a few frames, never freezing.
        source: root.full ? (({ box: "MBox.qml", form: "MForm.qml", grid: "MGrid.qml", stack: "MStack.qml",
                   label: "MLabel.qml", button: "MButton.qml", check: "MCheck.qml", radio: "MCheck.qml",
                   combo: "MCombo.qml", line: "MLine.qml", text: "MTextArea.qml", spin: "MSpin.qml",
                   slider: "MSlider.qml", date: "MDate.qml", progress: "MProgress.qml", list: "MList.qml",
                   tree: "MTree.qml", tabs: "MTabs.qml", stacked: "MStack.qml", scroll: "MScroll.qml",
                   splitter: "MSplitter.qml", canvas: "MCanvas.qml", container: "MContainer.qml",
                   space: "MSpace.qml" })[root.full.t] || "") : ""
        onLoaded: {
            item.node = Qt.binding(() => root.full)
            item.m = Qt.binding(() => root.m)
            if ("val" in item) item.val = Qt.binding(() => root.val)
        }
    }
}
