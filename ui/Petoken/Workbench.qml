import QtQuick
import QtQuick.Effects
import QtQuick.Layouts
import Petoken
import "mirror"

// The workbench (workbench_shell.py): a rail with the pages and the project spaces, a greeting
// banner on the home page, and each page drawn by the widget mirror.
Item {
    id: app
    Component.onCompleted: shell.appear()

    readonly property var ids: bridge.ids
    readonly property var tabsVal: mirror.values[ids.tabs] || ({})
    readonly property int current: tabsVal.current || 0
    readonly property var spacesVal: mirror.values[ids.spaces] || ({})
    readonly property var statusVal: mirror.values[ids.status] || ({})
    readonly property var tabsNode: find(mirror.tree, ids.tabs)
    readonly property var pageNode: tabsNode ? ((tabsNode.pages || [])[current] || null) : null

    function find(n, id) {
        if (!n || typeof n !== "object" || !id) return null
        if (n.id === id) return n
        const lists = [n.items, n.pages, n.kids, n.cells ? n.cells.map(c => c.node) : null,
                       n.rows ? n.rows.flatMap(r => [r.label, r.field, r.span]) : null]
        for (const one of [n.layout, n.child]) { const f = find(one, id); if (f) return f }
        for (const list of lists) {
            if (!list) continue
            for (const c of list) { const f = find(c, id); if (f) return f }
        }
        return null
    }

    WindowShell {
        id: shell
        anchors.fill: parent
        title: bridge.title
        backdrop: bridge.artUrl("bg_workbench")
        onCloseRequested: bridge.close()
        titleExtras: [
            Chip { visible: bridge.summaryText !== ""; icon: "sparkle"; text: bridge.summaryText; accent: Theme.gold }
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
                                color: modelData.sel ? "#352A82" : (spaceHover.hovered ? "#231C5E" : "transparent")
                                border.color: modelData.sel ? "#7E6BE0" : "transparent"
                                Rectangle {
                                    x: 16; anchors.verticalCenter: parent.verticalCenter
                                    width: 7; height: 7; radius: 3.5
                                    color: modelData.sel ? Theme.gold : Theme.muted
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
                        Layout.preferredHeight: 168
                    }
                    RowLayout {                          // Other pages: their name, big.
                        visible: app.current !== 0
                        Layout.fillWidth: true
                        Text {
                            text: (bridge.nav[app.current] || {}).label || ""
                            color: Theme.ink
                            font.family: Theme.serif; font.pixelSize: 26; font.weight: Font.Bold
                        }
                        Item { Layout.fillWidth: true }
                        GemButton { kind: "ghost"; height: 36; fontSize: 13; icon: "graduation-cap"
                                    text: bridge.tutorialText; onClicked: bridge.tutorial() }
                    }
                    MirrorNode {
                        id: page
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        node: app.pageNode || ({})
                        m: mirror
                        opacity: 0
                        Component.onCompleted: opacity = 1
                        Behavior on opacity { NumberAnimation { duration: Theme.smooth } }
                    }
                    Text {
                        visible: app.statusVal.v === true && (app.statusVal.text || "") !== ""
                        Layout.fillWidth: true
                        text: app.statusVal.text || ""
                        color: Theme.readable("#E08AA8")
                        wrapMode: Text.Wrap
                        font.family: Theme.sans; font.pixelSize: 13
                    }
                }
            }
        }
    }
}
