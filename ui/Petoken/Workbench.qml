import QtQuick
import QtQuick.Effects
import QtQuick.Layouts
import Petoken
import "mirror"

// The workbench (workbench_shell.py): a rail with the pages and the project spaces, a greeting
// banner on the home page, and each page drawn by the widget mirror.
Item {
    id: app
    Component.onCompleted: { Theme.dark = false; reshape(); refresh(); shell.appear() }      // Calm paper for work.

    readonly property var ids: bridge.ids
    property var tabsVal: ({})
    property var spacesVal: ({})
    property var statusVal: ({})
    readonly property int current: tabsVal.current || 0
    function refresh() {
        tabsVal = mirror.value(ids.tabs); spacesVal = mirror.value(ids.spaces); statusVal = mirror.value(ids.status)
    }
    onIdsChanged: { reshape(); refresh() }
    Connections { target: mirror; function onUpdated() { app.refresh() } }
    property var tabsNode: ({})
    function reshape() { tabsNode = mirror.nodeOf(ids.tabs) }
    Connections { target: mirror; function onReshaped() { if (mirror.isReshaped(app.ids.tabs)) app.reshape() } }

    WindowShell {
        id: shell
        anchors.fill: parent
        title: bridge.title
        onCloseRequested: bridge.close()
        titleExtras: [
            Chip { visible: bridge.summaryText !== ""; icon: "sparkle"; text: bridge.summaryText; accent: Theme.violet }
        ]
        content: Item {
            anchors.fill: parent
            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 18
                anchors.rightMargin: 22
                anchors.bottomMargin: 18
                spacing: 20

                Flickable {                              // The rail.
                    Layout.preferredWidth: 216
                    Layout.fillHeight: true
                    contentHeight: rail.implicitHeight
                    clip: contentHeight > height
                    boundsBehavior: Flickable.StopAtBounds
                    Column {
                        id: rail
                        width: parent.width
                        spacing: 6
                        Repeater {
                            model: bridge.nav
                            delegate: NavPill {
                                required property var modelData
                                required property int index
                                width: rail.width
                                label: modelData.label
                                art: modelData.art
                                icon: modelData.icon
                                tip: modelData.tip
                                chosen: index === app.current
                                onPicked: mirror.setIndex(app.ids.tabs, index)
                            }
                        }
                        Item { width: 1; height: 10 }
                        Text {
                            x: 16
                            text: bridge.spacesTitle
                            color: Theme.muted
                            font.family: Theme.sans; font.pixelSize: 12; font.weight: Font.DemiBold
                            font.letterSpacing: 1
                        }
                        Repeater {                       // The project spaces: everything, the inbox, each project.
                            model: app.spacesVal.rows || []
                            delegate: Rectangle {
                                required property var modelData
                                width: rail.width
                                height: 36
                                radius: 18
                                color: modelData.sel ? Theme.rowSelected : (spaceHover.hovered ? Theme.rowHover : "transparent")
                                border.color: modelData.sel ? Theme.rowSelectedEdge : "transparent"
                                Rectangle {
                                    x: 16; anchors.verticalCenter: parent.verticalCenter
                                    width: 7; height: 7; radius: 3.5
                                    color: modelData.sel ? Theme.violet : Theme.muted
                                }
                                Text {
                                    anchors { left: parent.left; leftMargin: 32; right: parent.right; rightMargin: 12
                                              verticalCenter: parent.verticalCenter }
                                    text: modelData.text
                                    elide: Text.ElideRight
                                    color: modelData.sel ? Theme.ink : Theme.inkSoft
                                    font.family: Theme.sans; font.pixelSize: 14
                                    font.weight: modelData.sel ? Font.DemiBold : Font.Normal
                                }
                                HoverHandler { id: spaceHover; cursorShape: Qt.PointingHandCursor }
                                TapHandler { onTapped: mirror.listSelect(app.ids.spaces, modelData.row) }
                            }
                        }
                        Item { width: 1; height: 10 }
                        Repeater {
                            model: bridge.extras
                            delegate: NavPill {
                                required property var modelData
                                width: rail.width
                                label: modelData.label
                                art: modelData.art
                                icon: modelData.icon
                                subtle: true
                                onPicked: bridge.extra(modelData.key)
                            }
                        }
                    }
                }

                ColumnLayout {                           // The page.
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    spacing: 14

                    HomeBanner {
                        visible: app.current === 0
                        Layout.fillWidth: true
                        Layout.preferredHeight: 132
                    }
                    RowLayout {                          // Other pages: their name, big.
                        visible: app.current !== 0
                        Layout.fillWidth: true
                        Text {
                            text: (bridge.nav[app.current] || {}).label || ""
                            color: Theme.ink
                            font.family: Theme.serif; font.pixelSize: 24; font.weight: Font.Bold
                        }
                        Item { Layout.fillWidth: true }
                        GemButton { kind: "ghost"; height: 36; fontSize: 13; icon: "graduation-cap"
                                    text: bridge.tutorialText; onClicked: bridge.tutorial() }
                    }
                    Item {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        Repeater {                                           // Each page built the first time it is shown, then kept.
                                model: ((app.tabsNode || ({})).pages || []).length
                                delegate: Loader {
                                    required property int index
                                    readonly property var pageNode: ((app.tabsNode || ({})).pages || [])[index] || null
                                    property bool seen: false
                                    readonly property bool current: index === app.current
                                    onCurrentChanged: if (current) seen = true
                                    Component.onCompleted: if (current) seen = true
                                    anchors.fill: parent
                                    visible: current
                                    active: seen && pageNode !== null
                                    asynchronous: true
                                    source: "mirror/MirrorNode.qml"
                                    onLoaded: { item.node = Qt.binding(() => pageNode); item.m = Qt.binding(() => mirror) }
                                }
                            }
                    }
                    Text {
                        visible: app.statusVal.v === true && (app.statusVal.text || "") !== ""
                        Layout.fillWidth: true
                        text: app.statusVal.text || ""
                        color: Theme.danger
                        wrapMode: Text.Wrap
                        font.family: Theme.sans; font.pixelSize: 13
                    }
                }
            }
        }
    }
}
