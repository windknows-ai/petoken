import QtQuick
import QtQuick.Effects
import QtQuick.Layouts
import Petoken

// The Stardust Wardrobe (2.5). Data and actions come from `bridge` (ui/wardrobe_bridge.py).
Item {
    id: app
    width: 1260
    height: 840

    Connections {
        target: bridge
        function onOpened() { shell.appear(); doors.open() }
        function onSparkle(gold) { mirror.sparkle(gold) }
    }

    WindowShell {
        id: shell
        anchors.fill: parent
        title: bridge.tr("wardrobe_title_plain")
        onCloseRequested: bridge.close()
        titleExtras: [
            Chip { icon: "star-four"; text: bridge.balanceText; accent: Theme.gold },
            Chip { icon: "chart-line-up"; text: bridge.earnedText; accent: Theme.ice }
        ]
        content: Item {
            anchors.fill: parent

            GemButton {                                  // Sign-in, top right of the content.
                anchors { right: parent.right; rightMargin: 104; top: parent.top; topMargin: -52 }
                kind: bridge.signedIn ? "ghost" : "gold"
                icon: bridge.signedIn ? "check-circle" : "calendar-star"
                text: bridge.signText
                enabled: !bridge.signedIn
                onClicked: bridge.signIn()
            }

            RowLayout {
                anchors { fill: parent; leftMargin: 18; rightMargin: 18; bottomMargin: 16 }
                spacing: 18

                ColumnLayout {                           // Left: the mirror.
                    Layout.preferredWidth: Math.min(430, app.width * 0.33)
                    Layout.maximumWidth: Math.min(430, app.width * 0.33)
                    Layout.fillWidth: false
                    Layout.fillHeight: true
                    spacing: 10
                    Mirror {
                        id: mirror
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        portrait: bridge.portrait
                        trying: bridge.trying
                    }
                    Row {
                        Layout.alignment: Qt.AlignHCenter
                        spacing: 6
                        Repeater {
                            model: bridge.poses
                            delegate: GemButton {
                                kind: "ghost"
                                height: 32
                                fontSize: 12
                                implicitWidth: 64
                                checked: modelData.key === bridge.pose
                                text: modelData.label
                                onClicked: bridge.setPose(modelData.key)
                            }
                        }
                    }
                    Row {
                        Layout.alignment: Qt.AlignHCenter
                        spacing: 6
                        GemButton { kind: "ghost"; height: 34; fontSize: 12; icon: "floppy-disk"; text: bridge.tr("wardrobe_save_outfit"); onClicked: bridge.saveOutfit() }
                        GemButton { kind: "ghost"; height: 34; fontSize: 12; icon: "t-shirt"; text: bridge.tr("wardrobe_wear_outfit"); enabled: bridge.outfits.length > 0; onClicked: bridge.wearOutfit() }
                        GemButton { kind: "ghost"; height: 34; fontSize: 12; icon: "arrow-counter-clockwise"; text: bridge.tr("wardrobe_take_all"); onClicked: bridge.takeAll() }
                    }
                    Text {
                        Layout.fillWidth: true
                        visible: bridge.bonusText !== ""
                        text: bridge.bonusText
                        color: Theme.gold
                        font.family: Theme.sans
                        font.pixelSize: 12
                        horizontalAlignment: Text.AlignHCenter
                        wrapMode: Text.WordWrap
                    }
                }

                ColumnLayout {                           // Right: the pages.
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    spacing: 8
                    TabStrip {
                        id: tabs
                        labels: [bridge.tr("wardrobe_tab_closet"), bridge.tr("wardrobe_tab_shop"), bridge.tr("wardrobe_tab_milestones")]
                        current: bridge.page
                        onPicked: (index) => bridge.setPage(index)
                    }
                    Item {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        ClosetPage { anchors.fill: parent; shown: bridge.page === 0 }
                        ShopPage { anchors.fill: parent; shown: bridge.page === 1 }
                        MilestonePage { anchors.fill: parent; shown: bridge.page === 2 }
                    }
                }
            }
        }
    }
    Doors {                                              // Over everything, inside the rounded body.
        id: doors
        anchors { fill: parent; margins: shell.margin + 1 }
        layer.enabled: true
        layer.effect: MultiEffect {
            maskEnabled: true
            maskSource: ShaderEffectSource { sourceItem: doorMask; hideSource: true }
        }
    }
    Rectangle { id: doorMask; anchors { fill: parent; margins: shell.margin + 1 }
    radius: Theme.radius + 5; visible: false; layer.enabled: true }
}
