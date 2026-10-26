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
            visible: !bridge.covered                     // Under a wish show: nothing to draw.

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
                    spacing: 12
                    Mirror {
                        id: mirror
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        portrait: bridge.portrait
                        trying: bridge.trying
                        zoom: bridge.zoom
                        Rectangle {                      // Fitting the chosen piece by hand.
                            radius: Theme.radius
                            border.color: Theme.glassEdge
                            id: fitPanel
                            objectName: "fitPanel"
                            property bool open: false
                            visible: open
                            anchors { horizontalCenter: parent.horizontalCenter; top: parent.top; topMargin: (parent.height - 1000 * mirror.k) / 2 + 180 * mirror.k }
                            width: Math.min(parent.width - 12, 380)
                            height: fitColumn.implicitHeight + 24
                            color: "#E6120D30"
                            Column {
                                id: fitColumn
                                anchors.centerIn: parent
                                spacing: 10
                                Text { anchors.horizontalCenter: parent.horizontalCenter; text: bridge.fitText; color: Theme.inkSoft
                                       font.family: Theme.sans; font.pixelSize: 13 }
                                Row {
                                    anchors.horizontalCenter: parent.horizontalCenter
                                    spacing: 6
                                    enabled: bridge.canAdjust
                                    opacity: enabled ? 1 : 0.4
                                    Repeater {
                                        model: [ { i: "caret-left", a: () => bridge.nudge(-0.01, 0) }, { i: "caret-up", a: () => bridge.nudge(0, -0.01) },
                                                 { i: "caret-down", a: () => bridge.nudge(0, 0.01) }, { i: "caret-right", a: () => bridge.nudge(0.01, 0) },
                                                 { i: "minus", a: () => bridge.growPiece(1 / 1.06) }, { i: "plus", a: () => bridge.growPiece(1.06) },
                                                 { i: "arrow-counter-clockwise", a: () => bridge.turnPiece(-5) }, { i: "arrow-clockwise", a: () => bridge.turnPiece(5) } ]
                                        delegate: GemButton { required property var modelData; kind: "ghost"; height: 34; implicitWidth: 38
                                                              icon: modelData.i; text: ""; autoRepeat: true; onClicked: modelData.a() }
                                    }
                                }
                                GemButton { anchors.horizontalCenter: parent.horizontalCenter; kind: "ghost"; height: 32; fontSize: 13
                                            icon: "arrow-counter-clockwise"; text: bridge.tr("wardrobe_fit_reset"); enabled: bridge.canAdjust
                                            onClicked: bridge.resetFit() }
                            }
                        }
                    }
                    Row {                                // Her size in the mirror, and fitting by hand.
                        Layout.alignment: Qt.AlignHCenter
                        spacing: 8
                        Text { anchors.verticalCenter: parent.verticalCenter; text: bridge.tr("wardrobe_zoom"); color: Theme.inkSoft
                               font.family: Theme.sans; font.pixelSize: 13 }
                        GemButton { kind: "ghost"; height: 32; implicitWidth: 36; icon: "minus"; text: ""; autoRepeat: true
                                    onClicked: bridge.setZoom(bridge.zoom - 0.05) }
                        Text { anchors.verticalCenter: parent.verticalCenter; width: 44; horizontalAlignment: Text.AlignHCenter
                               text: Math.round(bridge.zoom * 100) + "%"; color: Theme.ink; font.family: Theme.sans; font.pixelSize: 13 }
                        GemButton { kind: "ghost"; height: 32; implicitWidth: 36; icon: "plus"; text: ""; autoRepeat: true
                                    onClicked: bridge.setZoom(bridge.zoom + 0.05) }
                        Item { width: 6; height: 1 }
                        GemButton { kind: "ghost"; height: 32; fontSize: 13; icon: "sliders-horizontal"; text: bridge.tr("wardrobe_fit")
                                    checked: fitPanel.open; onClicked: fitPanel.open = !fitPanel.open }
                    }
                    Row {
                        Layout.alignment: Qt.AlignHCenter
                        spacing: 6
                        Repeater {
                            model: bridge.poses
                            delegate: GemButton {
                                kind: "ghost"
                                height: 36
                                fontSize: 14
                                implicitWidth: 72
                                checked: modelData.key === bridge.pose
                                text: modelData.label
                                onClicked: bridge.setPose(modelData.key)
                            }
                        }
                    }
                    Row {
                        Layout.alignment: Qt.AlignHCenter
                        spacing: 6
                        GemButton { kind: "ghost"; height: 38; fontSize: 13; icon: "floppy-disk"; text: bridge.tr("wardrobe_save_outfit"); onClicked: bridge.saveOutfit() }
                        GemButton { kind: "ghost"; height: 38; fontSize: 13; icon: "t-shirt"; text: bridge.tr("wardrobe_wear_outfit"); enabled: bridge.outfits.length > 0; onClicked: bridge.wearOutfit() }
                        GemButton { kind: "ghost"; height: 38; fontSize: 13; icon: "arrow-counter-clockwise"; text: bridge.tr("wardrobe_take_all"); onClicked: bridge.takeAll() }
                    }
                    Text {
                        Layout.fillWidth: true
                        visible: bridge.bonusText !== ""
                        text: bridge.bonusText
                        color: Theme.gold
                        font.family: Theme.sans
                        font.pixelSize: 13
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
    radius: Theme.windowRadius - 1; visible: false; layer.enabled: true }
}
