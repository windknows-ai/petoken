import QtQuick
import Petoken

// A widget holding a layout: a plain group, a titled group box, or one of Petoken's cards.
Item {
    id: c
    property var node: ({})
    property var m: null
    property var val: ({})
    readonly property bool card: ["settingCard", "card", "projectShelf", "summaryCard", "poseCard", "levelCard"].indexOf(node.role) >= 0
                                  || (node.title || "") !== ""
    readonly property int pad: card ? ((node.layout && node.layout.margins && node.layout.margins[0] > 6) ? 4 : 14) : 0
    readonly property int titleRoom: (node.title || "") !== "" ? 30 : 0
    implicitWidth: (inner.item ? inner.item.implicitWidth : 0) + 2 * pad
    implicitHeight: (inner.item ? inner.item.implicitHeight : 0) + 2 * pad + titleRoom
    Rectangle {
        visible: c.card
        anchors.fill: parent
        radius: 18
        gradient: Gradient {
            GradientStop { position: 0; color: Theme.dark ? "#3A221A5C" : Theme.card }
            GradientStop { position: 1; color: Theme.dark ? "#4A140F3C" : Theme.card }
        }
        border.color: Theme.glassEdge
    }
    Text {
        visible: c.titleRoom > 0
        x: c.pad; y: 10
        text: c.node.title || ""
        color: Theme.ink; font.family: Theme.serif; font.pixelSize: 15; font.weight: Font.Bold
    }
    Loader {                                             // By URL: a file may not name its own includer as a type.
        id: inner
        anchors.fill: parent
        anchors.margins: c.pad
        anchors.topMargin: c.pad + c.titleRoom
        source: "MirrorNode.qml"
        onLoaded: { item.node = Qt.binding(() => c.node.layout || ({})); item.m = Qt.binding(() => c.m) }
    }
}
