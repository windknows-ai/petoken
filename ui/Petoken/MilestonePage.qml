import QtQuick
import QtQuick.Layouts
import Petoken

// Milestones: earned stardust and what it unlocks (ring skins, the Starsea form), the book.
Page {
    ColumnLayout {
        anchors.fill: parent
        anchors.topMargin: 8
        spacing: 12

        Text { text: bridge.tr("stardust_section"); color: Theme.ink; font.family: Theme.serif; font.pixelSize: 17; font.weight: Font.Bold }
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
        Text { Layout.fillWidth: true; text: bridge.milestone.earnText || ""; color: Theme.muted; font.family: Theme.sans; font.pixelSize: 12; wrapMode: Text.WordWrap }
        Flow {
            Layout.fillWidth: true
            spacing: 14
            Repeater {
                model: bridge.skins
                delegate: Item {
                    width: 176; height: 168
                    GlassPanel {
                        id: card
                        width: parent.width; height: 120
                        border.color: modelData.current ? Theme.gold : Theme.glassEdge
                        border.width: modelData.current ? 1.6 : 1
                        scale: hover.containsMouse && modelData.unlocked ? 1.04 : 1
                        Behavior on scale { NumberAnimation { duration: Theme.quick; easing.type: Easing.OutBack } }
                        Image {
                            anchors { fill: parent; margins: 6 }
                            source: modelData.image
                            fillMode: Image.PreserveAspectFit
                            opacity: modelData.unlocked ? 1 : 0.45
                        }
                        Icon { visible: !modelData.unlocked; anchors.centerIn: parent; name: "lock-simple"; filled: true; size: 26; color: Theme.inkSoft }
                    }
                    Text { anchors { top: card.bottom; topMargin: 8; horizontalCenter: parent.horizontalCenter }
                           text: modelData.name; color: Theme.ink; font.family: Theme.sans; font.pixelSize: 13; font.weight: Font.DemiBold }
                    Text { anchors { top: card.bottom; topMargin: 28; horizontalCenter: parent.horizontalCenter }
                           text: modelData.caption; color: modelData.current ? Theme.gold : Theme.muted; font.family: Theme.sans; font.pixelSize: 11 }
                    MouseArea { id: hover; anchors.fill: parent; hoverEnabled: true
                                cursorShape: modelData.unlocked ? Qt.PointingHandCursor : Qt.ArrowCursor
                                onClicked: if (modelData.unlocked) bridge.chooseSkin(modelData.key) }
                }
            }
        }
        Text { text: bridge.tr("shop_book"); color: Theme.ink; font.family: Theme.serif; font.pixelSize: 17; font.weight: Font.Bold }
        Repeater {
            model: bridge.book
            delegate: Row {
                spacing: 12
                Text { width: 230; text: modelData.label; color: Theme.inkSoft; font.family: Theme.sans; font.pixelSize: 13 }
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
