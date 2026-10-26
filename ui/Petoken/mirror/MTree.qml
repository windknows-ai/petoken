import QtQuick
import QtQuick.Controls.Basic
import Petoken

// A table (QTreeWidget without branches): a quiet header and glass rows.
Item {
    id: t
    property var node: ({})
    property var m: null
    property var val: ({})
    readonly property var heads: val.heads || []
    readonly property var widths: val.widths || []
    readonly property var rows: val.rows || []
    // The original column widths, shrunk together when they would not fit; the last takes what is left.
    function columnWidth(c, total) {
        let given = 0
        for (let i = 0; i < heads.length - 1; i++) given += Math.max(60, widths[i] || 140)
        const room = Math.max(1, total - 90)
        const k = given > room ? room / given : 1
        if (c === heads.length - 1) return Math.max(80, total - given * k)
        return Math.max(50, (widths[c] || 140) * k)
    }
    implicitWidth: 420
    implicitHeight: Math.min(360, Math.max(100, rows.length * 46 + 56))
    Rectangle {
        anchors.fill: parent
        radius: 18
        color: Theme.dark ? "#26140F3C" : Theme.card
        border.color: Theme.glassEdge
    }
    Text {                                               // Nothing here yet: said inside the box.
        visible: t.rows.length === 0 && (t.val.empty || "") !== ""
        anchors.centerIn: parent
        width: parent.width - 48
        horizontalAlignment: Text.AlignHCenter
        wrapMode: Text.Wrap
        text: t.val.empty || ""
        color: Theme.muted
        font.family: Theme.sans
        font.pixelSize: 14
        lineHeight: 1.3
    }
    Row {
        id: header
        visible: t.val.header !== false && t.heads.length > 0
        x: 18; y: 10
        height: visible ? 26 : 0
        Repeater {
            model: t.heads
            delegate: Text {
                required property var modelData
                required property int index
                width: t.columnWidth(index, t.width - 36)
                text: modelData
                color: Theme.muted
                font.family: Theme.sans; font.pixelSize: 12; font.weight: Font.DemiBold
                elide: Text.ElideRight
            }
        }
    }
    ListView {
        id: view
        anchors { fill: parent; margins: 6; topMargin: header.visible ? 40 : 6 }
        clip: true
        spacing: 3
        model: t.rows
        boundsBehavior: Flickable.StopAtBounds
        ScrollBar.vertical: ScrollBar { policy: view.contentHeight > view.height ? ScrollBar.AsNeeded : ScrollBar.AlwaysOff }
        delegate: Item {
            id: row
            required property var modelData
            width: view.width
            height: 44
            Rectangle {
                anchors.fill: parent; radius: 13
                color: row.modelData.sel ? Theme.rowSelected : (hover.hovered ? Theme.rowHover : "transparent")
                border.color: row.modelData.sel ? Theme.rowSelectedEdge : "transparent"
            }
            Row {
                x: 12
                anchors.verticalCenter: parent.verticalCenter
                Repeater {
                    model: row.modelData.cells
                    delegate: Text {
                        required property var modelData
                        required property int index
                        width: t.columnWidth(index, t.width - 36)
                        text: modelData
                        color: index === 0 ? Theme.ink : Theme.inkSoft
                        font.family: Theme.sans; font.pixelSize: 14
                        font.weight: index === 0 ? Font.DemiBold : Font.Normal
                        elide: Text.ElideMiddle
                        rightPadding: 12
                    }
                }
            }
            HoverHandler { id: hover }
            TapHandler { onTapped: t.m.listSelect(t.node.id, row.modelData.row)
                         onDoubleTapped: t.m.listActivate(t.node.id, row.modelData.row) }
            Tip { text: row.modelData.tip || "" }
        }
    }
}
