import QtQuick
import QtQuick.Controls.Basic
import Petoken

// A drop-down choice: a glass pill showing the choice, opening a glass list (typing allowed when editable).
Item {
    id: c
    property var node: ({})
    property var m: null
    property var val: ({})
    readonly property var items: val.items || []
    readonly property bool usable: val.en !== false
    implicitWidth: Math.max(180, Math.min(320, shown.implicitWidth + 64))
    implicitHeight: 40
    opacity: usable ? 1 : 0.45

    Rectangle {
        id: pill
        anchors.fill: parent
        radius: height / 2
        color: area.containsMouse && c.usable ? Theme.rowHover : Theme.field
        border.color: listBox.opened ? Theme.violet : Theme.fieldEdge
        Behavior on color { ColorAnimation { duration: Theme.quick } }
    }
    Text {
        id: shown
        visible: !c.val.editable
        anchors { left: parent.left; leftMargin: 18; right: arrow.left; rightMargin: 8; verticalCenter: parent.verticalCenter }
        text: c.items[c.val.current] !== undefined ? c.items[c.val.current] : (c.val.edit || "")
        color: Theme.ink
        elide: Text.ElideRight
        font.family: Theme.sans
        font.pixelSize: 14
    }
    TextInput {
        visible: !!c.val.editable
        anchors { left: parent.left; leftMargin: 18; right: arrow.left; rightMargin: 8; verticalCenter: parent.verticalCenter }
        text: c.val.edit || ""
        color: Theme.ink
        selectionColor: Theme.violet
        clip: true
        font.family: Theme.sans
        font.pixelSize: 14
        onTextEdited: c.m.setText(c.node.id, text)
    }
    Icon {
        id: arrow
        anchors { right: parent.right; rightMargin: 14; verticalCenter: parent.verticalCenter }
        name: "caret-down"; size: 14; color: Theme.inkSoft
        rotation: listBox.opened ? 180 : 0
        Behavior on rotation { NumberAnimation { duration: Theme.quick } }
    }
    MouseArea {
        id: area
        anchors.fill: parent
        anchors.leftMargin: c.val.editable ? parent.width - 40 : 0
        hoverEnabled: true
        enabled: c.usable
        cursorShape: Qt.PointingHandCursor
        onClicked: listBox.opened ? listBox.close() : listBox.open()
    }
    Tip { text: c.val.tip || "" }
    Loader {                                             // Made only when it opens.
        id: listBox
        active: false
        readonly property bool opened: item ? item.opened : false
        function open() { active = true; item.open() }
        function close() { if (item) item.close() }
        sourceComponent: Component {
            Popup {
                id: list
                onClosed: Qt.callLater(() => listBox.active = false)
                y: c.height + 6
                width: Math.max(c.width, 220)
                height: Math.min(view.contentHeight + 12, 320)
                padding: 6
                background: Rectangle { radius: 16; color: Theme.popup; border.color: Theme.glassEdge }
                enter: Transition { NumberAnimation { property: "opacity"; from: 0; to: 1; duration: Theme.quick } }
                contentItem: ListView {
                    id: view
                    clip: true
                    model: c.items
                    boundsBehavior: Flickable.StopAtBounds
                    ScrollBar.vertical: ScrollBar { policy: view.contentHeight > view.height ? ScrollBar.AsNeeded : ScrollBar.AlwaysOff }
                    delegate: Item {
                        required property var modelData
                        required property int index
                        width: view.width
                        height: 38
                        Rectangle {
                            anchors.fill: parent
                            radius: 11
                            color: index === c.val.current ? Theme.rowSelected : (hover.hovered ? Theme.rowHover : "transparent")
                        }
                        Text {
                            anchors { left: parent.left; leftMargin: 14; right: parent.right; rightMargin: 10; verticalCenter: parent.verticalCenter }
                            text: modelData
                            elide: Text.ElideRight
                            color: index === c.val.current ? Theme.ink : Theme.inkSoft
                            font.family: Theme.sans
                            font.pixelSize: 14
                            font.weight: index === c.val.current ? Font.DemiBold : Font.Normal
                        }
                        HoverHandler { id: hover }
                        TapHandler { onTapped: { list.close(); c.m.setIndex(c.node.id, index) } }
                    }
                }
            }
        }
    }
}
