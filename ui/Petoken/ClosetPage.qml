import QtQuick
import QtQuick.Effects
import QtQuick.Layouts
import Petoken

// The closet: kinds down the left, the star cabinet (Codex's art) with the pieces standing on its
// shelves, turned page by page, and the chosen piece's details below.
Page {
    id: page
    RowLayout {
        anchors.fill: parent
        spacing: 14

        Column {                                         // Kinds.
            Layout.alignment: Qt.AlignTop
            Layout.topMargin: 8
            spacing: 8
            Repeater {
                model: bridge.kinds
                delegate: Rectangle {
                    width: 156; height: 46; radius: 23
                    readonly property bool current: modelData.key === bridge.kind
                    gradient: Gradient {
                        orientation: Gradient.Horizontal
                        GradientStop { position: 0; color: current ? "#6A52D6" : (hover.containsMouse ? "#2C2472" : "#1B1548") }
                        GradientStop { position: 1; color: current ? "#4636A6" : (hover.containsMouse ? "#241D60" : "#161140") }
                    }
                    border.color: current ? "#B9A8FF" : Theme.glassEdge
                    border.width: 1
                    Image {
                        id: kindIcon
                        x: 14; anchors.verticalCenter: parent.verticalCenter
                        width: 26; height: 26
                        source: bridge.wardrobeUrl("icon_" + modelData.key)
                        sourceSize: Qt.size(52, 52)
                        opacity: current ? 1 : 0.8
                    }
                    Text {
                        anchors { left: kindIcon.right; leftMargin: 9; verticalCenter: parent.verticalCenter }
                        text: modelData.label
                        color: current ? Theme.ink : Theme.inkSoft
                        font.family: Theme.sans; font.pixelSize: 14; font.weight: current ? Font.Bold : Font.Medium
                    }
                    Text {
                        anchors { right: parent.right; rightMargin: 12; verticalCenter: parent.verticalCenter }
                        text: modelData.have + "/" + modelData.total
                        color: current ? Theme.gold : Theme.muted
                        font.family: Theme.sans; font.pixelSize: 13
                    }
                    MouseArea { id: hover; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                                onClicked: bridge.setKind(modelData.key) }
                }
            }
        }

        ColumnLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 8

            Item {                                       // The cabinet.
                id: cabinetBox
                Layout.fillWidth: true
                Layout.fillHeight: true
                readonly property real k: Math.min(width / 1200, height / 1400)
                Image {
                    id: cabinet
                    width: 1200 * cabinetBox.k
                    height: 1400 * cabinetBox.k
                    anchors.centerIn: parent
                    source: bridge.wardrobeUrl("backdrop_closet")
                    sourceSize: Qt.size(width * Screen.devicePixelRatio, height * Screen.devicePixelRatio)
                    smooth: true
                }
                Item {
                    id: shelves
                    anchors.fill: cabinet
                    readonly property var floors: [466, 715, 972, 1215]      // Shelf tops, in the art's pixels.
                    readonly property real k: cabinetBox.k
                    Repeater {
                        model: bridge.pageItems
                        delegate: Dome {
                            readonly property int row: Math.floor(index / 4)
                            readonly property int col: index % 4
                            width: 160 * shelves.k
                            height: 196 * shelves.k
                            x: (150 + col * 225) * shelves.k + (225 * shelves.k - width) / 2 - 24 * shelves.k
                            y: shelves.floors[row] * shelves.k - height + 8 * shelves.k
                            item: modelData
                            order: index
                            chosen: bridge.chosenId === modelData.id
                            onPicked: bridge.choose(modelData.id)
                        }
                    }
                }
                Row {                                    // Turning the pages.
                    anchors { horizontalCenter: cabinet.horizontalCenter; bottom: cabinet.bottom; bottomMargin: 22 * cabinetBox.k }
                    spacing: 14
                    visible: bridge.pageCount > 1
                    GemButton { kind: "ghost"; height: 30; implicitWidth: 44; icon: "caret-left"; text: ""; enabled: bridge.shelfPage > 0; onClicked: bridge.turn(-1) }
                    Row {
                        anchors.verticalCenter: parent.verticalCenter
                        spacing: 6
                        Repeater {
                            model: bridge.pageCount
                            delegate: Rectangle {
                                width: index === bridge.shelfPage ? 18 : 7; height: 7; radius: 3.5
                                color: index === bridge.shelfPage ? Theme.gold : "#6A60A8"
                                Behavior on width { NumberAnimation { duration: Theme.quick } }
                            }
                        }
                    }
                    GemButton { kind: "ghost"; height: 30; implicitWidth: 44; icon: "caret-right"; text: ""; enabled: bridge.shelfPage < bridge.pageCount - 1; onClicked: bridge.turn(1) }
                }
            }

            GlassPanel {                                 // What is chosen.
                Layout.fillWidth: true
                Layout.preferredHeight: 78
                Text {
                    visible: bridge.chosenId === ""
                    anchors.centerIn: parent
                    text: bridge.tr("wardrobe_pick_hint")
                    color: Theme.muted
                    font.family: Theme.sans; font.pixelSize: 14
                }
                Column {
                    visible: bridge.chosenId !== ""
                    anchors { left: parent.left; leftMargin: 22; verticalCenter: parent.verticalCenter }
                    spacing: 5
                    Row {
                        spacing: 10
                        Text { text: bridge.chosen.name || ""; color: Theme.ink; font.family: Theme.serif; font.pixelSize: 18; font.weight: Font.Bold }
                        Text { text: bridge.chosen.rarityLabel || ""; color: Theme.rarity(bridge.chosen.rarity || ""); font.family: Theme.sans
                               font.pixelSize: 13; font.weight: Font.DemiBold; anchors.baseline: parent.children[0].baseline }
                    }
                    Text { text: bridge.chosen.detail || ""; color: Theme.muted; font.family: Theme.sans; font.pixelSize: 13 }
                }
                GemButton {
                    visible: bridge.chosenId !== ""
                    anchors { right: parent.right; rightMargin: 18; verticalCenter: parent.verticalCenter }
                    height: 44
                    fontSize: 15
                    kind: bridge.chosen.actionKind || "violet"
                    icon: bridge.chosen.actionIcon || ""
                    text: bridge.chosen.actionText || ""
                    enabled: bridge.chosen.actionEnabled === true
                    onClicked: bridge.act()
                }
            }
        }
    }
}
