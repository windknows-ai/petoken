import QtQuick

// Room a layout leaves (a spacing or a stretch).
Item {
    property var node: ({})
    property var m: null
    implicitWidth: node.hx ? 0 : (node.w || 0)
    implicitHeight: node.vx ? 0 : (node.h || 0)
}
