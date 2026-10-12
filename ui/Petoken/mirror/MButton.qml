import QtQuick
import QtQuick.Controls.Basic
import Petoken

// A push button as a gem button; one with a menu opens it as a glass list.
Item {
    id: b
    property var node: ({})
    property var m: null
    property var val: ({})
    readonly property bool hasMenu: (val.menu || []).length > 0
    implicitWidth: gem.implicitWidth
    implicitHeight: b.m && b.m.dense ? 34 : 40
    GemButton {
        id: gem
        anchors.fill: parent
        text: (b.val.text || "") + (b.hasMenu ? "  ▾" : "")
        kind: b.node.danger ? "danger" : (b.node.primary ? "violet" : "ghost")
        checked: !!b.val.checked
        enabled: b.val.en !== false
        imageIcon: b.val.icon || ""
        compact: !!(b.m && b.m.dense)
        onClicked: b.hasMenu ? menuBox.open() : b.m.click(b.node.id)
    }
    Tip { text: b.val.tip || "" }
    Loader {                                             // Made only when it opens.
        id: menuBox
        active: false
        readonly property bool opened: item ? item.opened : false
        function open() { active = true; item.open() }
        function close() { if (item) item.close() }
        sourceComponent: Component {
            Popup {
                id: menu
                onClosed: Qt.callLater(() => menuBox.active = false)
                y: b.height + 6
                padding: 6
                background: Rectangle { radius: 16; color: Theme.popup; border.color: Theme.glassEdge }
                contentItem: Column {
                    spacing: 2
                    Repeater {
                        model: b.val.menu || []
                        delegate: Item {
                            required property var modelData
                            required property int index
                            width: Math.max(200, label.implicitWidth + 40)
                            height: modelData.sep ? 9 : 38
                            Rectangle { visible: modelData.sep; anchors.centerIn: parent; width: parent.width - 16; height: 1
                                        color: Theme.glassEdge }
                            Rectangle {
                                visible: !modelData.sep
                                anchors.fill: parent
                                radius: 11
                                color: hover.hovered && modelData.en ? Theme.rowHover : "transparent"
                            }
                            Text {
                                id: label
                                visible: !modelData.sep
                                anchors { left: parent.left; leftMargin: 16; verticalCenter: parent.verticalCenter }
                                text: modelData.text
                                color: modelData.en ? Theme.ink : Theme.muted
                                font.family: Theme.sans; font.pixelSize: 14
                            }
                            HoverHandler { id: hover }
                            TapHandler { enabled: !modelData.sep && modelData.en
                                         onTapped: { menu.close(); b.m.menu(b.node.id, index) } }
                            Tip { text: modelData.tip || "" }
                        }
                    }
                }
            }
        }
    }
}
