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
    z: hot ? 6 : (chosen ? 5 : 0)
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
        y: root.hot || root.chosen ? -6 : 0
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
        Rectangle {                                      // Its price (or "worn") on the dome's base.
            visible: (root.item.badge || "") !== ""
            anchors { horizontalCenter: parent.horizontalCenter; bottom: parent.bottom; bottomMargin: parent.height * 0.075 }
            height: 22
            width: badge.implicitWidth + 20
            radius: 11
            color: root.item.worn ? "#E85BC99A" : "#E6140F36"
            border.color: root.item.worn ? "#B0FFFFFF" : "#80F3C96B"
            Text {
                id: badge
                anchors.centerIn: parent
                text: root.item.badge || ""
                color: root.item.worn ? "#0B2418" : Theme.gold
                font.family: Theme.sans
                font.pixelSize: 12
                font.weight: Font.Bold
            }
        }
    }
    Rectangle {                                          // Its name, floating up under the pointer.
        id: nameTag
        anchors { horizontalCenter: parent.horizontalCenter; bottom: parent.top; bottomMargin: root.hot || root.chosen ? 2 : -6 }
        z: 10
        height: 28
        width: nameText.implicitWidth + 26
        radius: 14
        color: "#F2201848"
        border.color: Qt.lighter(root.tone, 1.1)
        opacity: root.hot || root.chosen ? 1 : 0
        visible: opacity > 0
        Behavior on opacity { NumberAnimation { duration: Theme.quick } }
        Behavior on anchors.bottomMargin { NumberAnimation { duration: Theme.quick; easing.type: Easing.OutCubic } }
        Text {
            id: nameText
            anchors.centerIn: parent
            text: root.item.name || ""
            color: Theme.ink
            font.family: Theme.sans
            font.pixelSize: 13
            font.weight: Font.DemiBold
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
