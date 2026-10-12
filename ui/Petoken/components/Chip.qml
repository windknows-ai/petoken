import QtQuick
import Petoken

// A small glass label: an icon and a value (stardust, a count).
Rectangle {
    id: root
    property string icon: ""
    property string text: ""
    property color accent: Theme.gold
    implicitHeight: 32
    implicitWidth: row.implicitWidth + 26
    radius: height / 2
    color: Theme.dark ? "#30140F3A" : "#F1EEFA"
    border.color: Theme.glassEdge
    border.width: 1
    Row {
        id: row
        anchors.centerIn: parent
        spacing: 7
        Icon { visible: root.icon !== ""; name: root.icon; filled: true; size: 15; color: root.accent; anchors.verticalCenter: parent.verticalCenter }
        Text {
            id: value
            text: root.text
            color: Theme.ink
            font.family: Theme.sans
            font.pixelSize: 14
            font.weight: Font.Medium
            anchors.verticalCenter: parent.verticalCenter
            Behavior on text { SequentialAnimation {
                NumberAnimation { target: value; property: "scale"; to: 1.18; duration: 90 }
                PropertyAction {}
                NumberAnimation { target: value; property: "scale"; to: 1.0; duration: 220; easing.type: Easing.OutBack }
            } }
        }
    }
}
