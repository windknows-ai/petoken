import QtQuick
import QtQuick.Effects
import Petoken

// A piece in its glass dome (Codex's art), standing on a shelf. Rises in when shown, lifts and
// glows under the pointer, a gold ring when chosen.
Item {
    id: root
    property var item: ({})
    property bool chosen: false
    property int order: 0
    signal picked()
    width: 118
    height: 144

    readonly property bool hot: mouse.containsMouse
    readonly property color tone: Theme.rarity(item.rarity || "")

    opacity: 0
    transform: Translate { id: rise; y: 18 }
    Component.onCompleted: appear.start()
    SequentialAnimation {
        id: appear
        PauseAnimation { duration: root.order * 35 }
        ParallelAnimation {
            NumberAnimation { target: root; property: "opacity"; to: 1; duration: 280; easing.type: Easing.OutCubic }
            NumberAnimation { target: rise; property: "y"; to: 0; duration: 380; easing.type: Easing.OutBack }
        }
    }

    Item {
        id: body
        anchors.fill: parent
        y: root.hot ? -6 : 0
        Behavior on y { NumberAnimation { duration: Theme.quick; easing.type: Easing.OutCubic } }

        Rectangle {                                      // Light pooled on the shelf under it.
            anchors.horizontalCenter: parent.horizontalCenter
            y: parent.height - 14
            width: parent.width * 0.86
            height: 14
            radius: 7
            color: root.chosen ? Theme.gold : root.tone
            opacity: root.chosen ? 0.55 : (root.hot ? 0.42 : 0.16)
            layer.enabled: true
            layer.effect: MultiEffect { blurEnabled: true; blur: 1; blurMax: 24 }
            Behavior on opacity { NumberAnimation { duration: Theme.quick } }
        }
        Image {                                          // The piece, inside the glass.
            id: art
            anchors.horizontalCenter: parent.horizontalCenter
            y: parent.height * 0.17
            width: parent.width * 0.62
            height: parent.height * 0.6
            fillMode: Image.PreserveAspectFit
            source: root.item.art || ""
            sourceSize: Qt.size(width * 2, height * 2)
            asynchronous: true
            opacity: root.item.owned ? 1 : 0.62
            scale: root.hot ? 1.06 : 1
            Behavior on scale { NumberAnimation { duration: Theme.smooth; easing.type: Easing.OutBack } }
        }
        Image {                                          // Codex's glass dome in its rarity's metal.
            anchors.fill: parent
            source: bridge.wardrobeUrl("tile_" + (root.item.rarity || "fanxing"))
            sourceSize: Qt.size(width * 2, height * 2)
            smooth: true
        }
        Rectangle {
            visible: root.chosen
            anchors { fill: parent; margins: -3 }
            radius: 16
            color: "transparent"
            border.width: 2
            border.color: Theme.gold
            opacity: 0.9
        }
        Text {                                           // Name on the dome's base.
            anchors { horizontalCenter: parent.horizontalCenter; bottom: parent.bottom; bottomMargin: 18 }
            width: parent.width - 12
            horizontalAlignment: Text.AlignHCenter
            elide: Text.ElideRight
            text: root.item.name || ""
            color: root.item.owned ? Theme.ink : Theme.inkSoft
            font.family: Theme.sans
            font.pixelSize: 11
            font.weight: Font.DemiBold
            style: Text.Outline
            styleColor: "#C0080616"
        }
        Rectangle {                                      // Worn / price / wish only.
            visible: (root.item.badge || "") !== ""
            anchors { top: parent.top; topMargin: 2; horizontalCenter: parent.horizontalCenter }
            height: 18
            width: badge.implicitWidth + 14
            radius: 9
            color: root.item.worn ? "#E07BE0B0" : "#D0110C2E"
            border.color: root.item.worn ? "#B0FFFFFF" : "#66F3C96B"
            Text {
                id: badge
                anchors.centerIn: parent
                text: root.item.badge || ""
                color: root.item.worn ? "#0E2A1C" : Theme.gold
                font.family: Theme.sans
                font.pixelSize: 10
                font.weight: Font.Bold
            }
        }
    }
    MouseArea {
        id: mouse
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: root.picked()
    }
}
