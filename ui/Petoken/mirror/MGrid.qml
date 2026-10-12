import QtQuick
import QtQuick.Layouts
import Petoken

// A QGridLayout: each cell where it was, spanning what it spanned.
Item {
    id: g
    property var node: ({})
    property var m: null
    implicitWidth: grid.implicitWidth
    implicitHeight: grid.implicitHeight
    GridLayout {
        id: grid
        anchors.fill: parent
        columns: g.node.cols || 1
        rowSpacing: Math.max(10, g.node.spacing || 0)
        columnSpacing: Math.max(12, g.node.spacing || 0)
        Repeater {
            model: g.node.cells || []
            delegate: Loader {
                id: cell
                required property var modelData
                source: "MirrorNode.qml"
                onLoaded: { item.node = Qt.binding(() => cell.modelData.node); item.m = Qt.binding(() => g.m) }
                visible: item ? item.shown : true
                Layout.row: modelData.r
                Layout.column: modelData.c
                Layout.rowSpan: modelData.rs
                Layout.columnSpan: modelData.cs
                Layout.fillWidth: modelData.node.t === "space" ? !!modelData.node.hx : (modelData.node.t === "label" ? !!modelData.node.hg : true)
                Layout.fillHeight: !!modelData.node.vx
            }
        }
    }
}
