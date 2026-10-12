import QtQuick
import Petoken

// One mirrored widget or layout (widget_mirror.Mirror): picks how to draw it from its kind.
Item {
    id: root
    property var node: ({})
    property var m: null
    readonly property var val: (m && node && node.id) ? (m.values[node.id] || ({})) : ({})
    readonly property bool shown: node === null || node.id === undefined || val.v !== false
    visible: shown
    implicitWidth: body.item ? body.item.implicitWidth : 0
    implicitHeight: body.item ? body.item.implicitHeight : 0

    Loader {
        id: body
        anchors.fill: parent
        source: root.node ? (({ box: "MBox.qml", form: "MForm.qml", grid: "MGrid.qml", stack: "MStack.qml",
                   label: "MLabel.qml", button: "MButton.qml", check: "MCheck.qml", radio: "MCheck.qml",
                   combo: "MCombo.qml", line: "MLine.qml", text: "MTextArea.qml", spin: "MSpin.qml",
                   slider: "MSlider.qml", date: "MDate.qml", progress: "MProgress.qml", list: "MList.qml",
                   tree: "MTree.qml", tabs: "MTabs.qml", stacked: "MStack.qml", scroll: "MScroll.qml",
                   splitter: "MSplitter.qml", canvas: "MCanvas.qml", container: "MContainer.qml",
                   space: "MSpace.qml" })[root.node.t] || "") : ""
        onLoaded: {
            item.node = Qt.binding(() => root.node)
            item.m = Qt.binding(() => root.m)
            if ("val" in item) item.val = Qt.binding(() => root.val)
        }
    }
}
