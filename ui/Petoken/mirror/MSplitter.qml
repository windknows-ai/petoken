import QtQuick
import QtQuick.Layouts
import Petoken

// A splitter's panes side by side (or stacked), the first one narrower like the original.
Item {
    id: sp
    property var node: ({})
    property var m: null
    readonly property bool across: node.dir === "h"
    readonly property var kids: (node.kids || []).filter(k => k !== null)
    implicitWidth: grid.implicitWidth
    implicitHeight: grid.implicitHeight
    GridLayout {
        id: grid
        anchors.fill: parent
        flow: sp.across ? GridLayout.LeftToRight : GridLayout.TopToBottom
        rows: sp.across ? 1 : Math.max(1, sp.kids.length)
        columns: sp.across ? Math.max(1, sp.kids.length) : 1
        rowSpacing: 16
        columnSpacing: 16
        Repeater {
            model: sp.kids
            delegate: Loader {
                id: pane
                required property var modelData
                required property int index
                source: "MirrorNode.qml"
                onLoaded: { item.node = Qt.binding(() => pane.modelData); item.m = Qt.binding(() => sp.m) }
                visible: item ? item.shown : true
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.horizontalStretchFactor: sp.across && sp.kids.length > 1 && index === 0 ? 2 : 5
                Layout.preferredWidth: sp.across ? (index === 0 && sp.kids.length > 1 ? 220 : 480) : -1
            }
        }
    }
}
