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
    height: subtle ? 42 : 46
    radius: height / 2
    color: pill.chosen ? Theme.rowSelected : (hover.hovered ? Theme.rowHover : "transparent")
    border.color: pill.chosen ? Theme.rowSelectedEdge : "transparent"
    Rectangle {                                          // A bar marks where you are.
        visible: pill.chosen
        x: 4; anchors.verticalCenter: parent.verticalCenter
        width: 4; height: parent.height - 18; radius: 2
        color: Theme.violet
    }
    Item {
        id: badge
        x: 14; anchors.verticalCenter: parent.verticalCenter
        width: pill.art ? 30 : 26; height: width
        Image {
            visible: pill.art !== ""
            anchors.fill: parent
            source: pill.art
            sourceSize: Qt.size(64, 64)
            smooth: true
        }
        Icon {
            visible: pill.art === ""
            anchors.centerIn: parent
            name: pill.icon; filled: pill.chosen; size: 18
            color: pill.chosen ? Theme.violet : Theme.inkSoft
        }
    }
    Text {
        anchors { left: badge.right; leftMargin: 12; right: parent.right; rightMargin: 12; verticalCenter: parent.verticalCenter }
        text: pill.label
        elide: Text.ElideRight
        color: pill.chosen ? Theme.violetSoft : Theme.ink
        font.family: Theme.sans
        font.pixelSize: 14
        font.weight: pill.chosen ? Font.Bold : Font.Normal
    }
    HoverHandler { id: hover; cursorShape: Qt.PointingHandCursor }
    TapHandler { id: tap; onTapped: pill.picked() }
    Tip { text: pill.tip }
}
