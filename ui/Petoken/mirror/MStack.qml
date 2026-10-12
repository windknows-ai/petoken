import QtQuick
import Petoken

// A stack of pages (QStackedWidget or a stacked layout): only the current one shows.
Item {
    id: s
    property var node: ({})
    property var m: null
    readonly property var owner: m ? (m.values[node.owner || node.id] || ({})) : ({})
    readonly property int current: owner.current !== undefined ? owner.current : 0
    readonly property var page: (node.pages || [])[current] || null
    implicitWidth: holder.item ? holder.item.implicitWidth : 0
    implicitHeight: holder.item ? holder.item.implicitHeight : 0
    Loader {
        id: holder
        anchors.fill: parent
        active: s.page !== null
        source: "MirrorNode.qml"
        onLoaded: { item.node = Qt.binding(() => s.page); item.m = Qt.binding(() => s.m) }
    }
}
