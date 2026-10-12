import QtQuick
import QtQuick.Effects
import QtQuick.Layouts
import Petoken

// Milestones: earned stardust and what it unlocks (ring skins, the Starsea form), the book.
Page {
    ColumnLayout {
        anchors.fill: parent
        anchors.topMargin: 8
        spacing: 14

        SectionTitle { key: "stardust_section" }
        GlassPanel {
            Layout.fillWidth: true
            Layout.preferredHeight: 92
            Column {
                anchors { fill: parent; margins: 16 }
                spacing: 10
                Row {
                    width: parent.width
                    Text { id: total; text: bridge.milestone.totalText || ""; color: Theme.gold; font.family: Theme.serif; font.pixelSize: 22; font.weight: Font.Bold }
                    Item { width: parent.width - total.width - next.width; height: 1 }
                    Text { id: next; text: bridge.milestone.nextText || ""; color: Theme.inkSoft; font.family: Theme.sans; font.pixelSize: 13; anchors.baseline: total.baseline }
                }
                Rectangle {                              // The road to the next unlock.
                    width: parent.width; height: 10; radius: 5
                    color: "#2A2266"
                    Rectangle {
                        width: parent.width * (bridge.milestone.fraction || 0)
                        height: parent.height; radius: 5
                        gradient: Gradient {
                            orientation: Gradient.Horizontal
                            GradientStop { position: 0; color: Theme.violet }
                            GradientStop { position: 1; color: Theme.gold }
                        }
                        Behavior on width { NumberAnimation { duration: Theme.slow; easing.type: Easing.OutCubic } }
                    }
                }
            }
        }
        Flow {                                           // How stardust is earned: one chip per way.
            Layout.fillWidth: true
            spacing: 8
            Text { text: bridge.milestone.earnTitle || ""; color: Theme.muted; font.family: Theme.sans; font.pixelSize: 14
                   height: 30; verticalAlignment: Text.AlignVCenter }
            Repeater {
                model: bridge.milestone.earnWays || []
                delegate: Rectangle {
                    height: 30; radius: 15
                    width: way.implicitWidth + 24
                    color: "#2A1F66"
                    border.color: Theme.glassEdge
                    Text { id: way; anchors.centerIn: parent; text: modelData; color: Theme.inkSoft
                           font.family: Theme.sans; font.pixelSize: 13 }
                }
            }
        }
        Row {
            id: skinRow
            Layout.fillWidth: true
            Layout.topMargin: 4
            spacing: 16
            readonly property real cardWidth: Math.min(204, (width - 3 * spacing) / 4)
            Repeater {
                model: bridge.skins
                delegate: Item {
                    width: skinRow.cardWidth; height: width * 0.76 + 58
                    GlassPanel {
                        id: card
                        width: parent.width; height: width * 0.76
                        radius: Theme.radius
                        border.color: modelData.current ? Theme.gold : Theme.glassEdge
                        border.width: modelData.current ? 2 : 1
                        scale: hover.containsMouse && modelData.unlocked ? 1.04 : 1
                        Behavior on scale { NumberAnimation { duration: Theme.quick; easing.type: Easing.OutBack } }
                        Image {                          // The night behind her, in the card's round corners.
                            anchors { fill: parent; margins: 1 }
                            source: bridge.fxUrl("sky_far")
                            fillMode: Image.PreserveAspectCrop
                            opacity: 0.5
                            layer.enabled: true
                            layer.effect: MultiEffect {
                                maskEnabled: true
                                maskSource: ShaderEffectSource { sourceItem: skyMask; hideSource: true }
                            }
                        }
                        Rectangle { id: skyMask; anchors.fill: parent; anchors.margins: 1; radius: card.radius - 1
                                    visible: false; layer.enabled: true }
                        Image {
                            id: scene
                            anchors { fill: parent; margins: 4 }
                            source: modelData.image
                            sourceSize: Qt.size(width * Screen.devicePixelRatio, height * Screen.devicePixelRatio)
                            fillMode: Image.PreserveAspectFit
                            smooth: true                 // Not asynchronous: the picture is drawn in Python,
                                                         // and a loader thread waiting on it can deadlock.
                            opacity: modelData.unlocked ? 1 : 0.4
                        }
                        Rectangle {
                            visible: !modelData.unlocked
                            anchors.centerIn: parent
                            width: 44; height: 44; radius: 22
                            color: "#B0140F36"
                            border.color: Theme.glassEdge
                            Icon { anchors.centerIn: parent; name: "lock-simple"; filled: true; size: 22; color: Theme.inkSoft }
                        }
                    }
                    Text { id: skinName; anchors { top: card.bottom; topMargin: 10; horizontalCenter: parent.horizontalCenter }
                           text: modelData.name; color: Theme.ink; font.family: Theme.sans; font.pixelSize: 15; font.weight: Font.DemiBold }
                    Text { anchors { top: skinName.bottom; topMargin: 4; horizontalCenter: parent.horizontalCenter }
                           text: modelData.caption; color: modelData.current ? Theme.gold : Theme.muted; font.family: Theme.sans; font.pixelSize: 13 }
                    MouseArea { id: hover; anchors.fill: parent; hoverEnabled: true
                                cursorShape: modelData.unlocked ? Qt.PointingHandCursor : Qt.ArrowCursor
                                onClicked: if (modelData.unlocked) bridge.chooseSkin(modelData.key) }
                }
            }
        }
        SectionTitle { key: "shop_book" }
        Repeater {
            model: bridge.book
            delegate: Row {
                spacing: 12
                Text { width: 250; text: modelData.label; color: Theme.inkSoft; font.family: Theme.sans; font.pixelSize: 14 }
                Rectangle {
                    width: 360; height: 8; radius: 4; color: "#2A2266"; anchors.verticalCenter: parent.verticalCenter
                    Rectangle { width: parent.width * modelData.fraction; height: parent.height; radius: 4
                                gradient: Gradient { orientation: Gradient.Horizontal
                                    GradientStop { position: 0; color: Theme.violet } GradientStop { position: 1; color: Theme.gold } } }
                }
            }
        }
        Item { Layout.fillHeight: true }
    }
}
