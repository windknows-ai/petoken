import QtQuick
import Petoken

// One place in a window's navigation rail: its gem icon (Codex's art, else a line icon) and name.
Rectangle {
    id: pill
    property string label: ""
    property string art: ""
    property string icon: ""
    property string tip: ""
    property bool chosen: false
    property bool subtle: false
    signal picked()
    height: subtle ? 42 : 48
    radius: height / 2
    gradient: Gradient {
        orientation: Gradient.Horizontal
        GradientStop { position: 0; color: pill.chosen ? "#6A52D6" : (hover.hovered ? "#2C2472" : "#00000000") }
        GradientStop { position: 1; color: pill.chosen ? "#4636A6" : (hover.hovered ? "#241D60" : "#00000000") }
    }
    border.color: pill.chosen ? "#B9A8FF" : "transparent"
    scale: tap.pressed ? 0.97 : 1
    Behavior on scale { NumberAnimation { duration: Theme.quick; easing.type: Easing.OutBack } }
    Item {
        id: badge
        x: 10; anchors.verticalCenter: parent.verticalCenter
        width: pill.art ? 34 : 30; height: width
        Image {
            visible: pill.art !== ""
            anchors.fill: parent
            source: pill.art
            sourceSize: Qt.size(96, 96)
            smooth: true
            opacity: pill.chosen || hover.hovered ? 1 : 0.82
        }
        Rectangle {
            visible: pill.art === ""
            anchors.fill: parent
            radius: width / 2
            color: pill.chosen ? "#33FFFFFF" : "#1AFFFFFF"
            Icon { anchors.centerIn: parent; name: pill.icon; filled: pill.chosen; size: 17
                   color: pill.chosen ? Theme.gold : Theme.inkSoft }
        }
    }
    Text {
        anchors { left: badge.right; leftMargin: 12; right: parent.right; rightMargin: 12; verticalCenter: parent.verticalCenter }
        text: pill.label
        elide: Text.ElideRight
        color: pill.chosen ? Theme.ink : (hover.hovered ? Theme.ink : Theme.inkSoft)
        font.family: Theme.sans
        font.pixelSize: pill.subtle ? 14 : 15
        font.weight: pill.chosen ? Font.Bold : Font.Medium
    }
    HoverHandler { id: hover; cursorShape: Qt.PointingHandCursor }
    TapHandler { id: tap; onTapped: pill.picked() }
    Tip { text: pill.tip }
}
