import QtQuick
import QtQuick.Controls.Basic
import Petoken

// A scroll area: its content as wide as the view, scrolling up and down with a slim bar.
Item {
    id: s
    property var node: ({})
    property var m: null
    property var val: ({})
    implicitWidth: holder.item ? holder.item.implicitWidth : 200
    implicitHeight: Math.min(holder.item ? holder.item.implicitHeight : 200, 520)
    Flickable {
        id: flick
        anchors.fill: parent
        clip: true
        contentWidth: width
        contentHeight: holder.item ? holder.item.implicitHeight : 0
        boundsBehavior: Flickable.StopAtBounds
        ScrollBar.vertical: ScrollBar { policy: flick.contentHeight > flick.height ? ScrollBar.AsNeeded : ScrollBar.AlwaysOff }
        Loader {
            id: holder
            width: flick.width - (flick.contentHeight > flick.height ? 12 : 0)
            height: item ? Math.max(item.implicitHeight, flick.height) : 0
            active: !!s.node.child
            source: "MirrorNode.qml"
            onLoaded: { item.node = Qt.binding(() => s.node.child); item.m = Qt.binding(() => s.m) }
        }
    }
}
