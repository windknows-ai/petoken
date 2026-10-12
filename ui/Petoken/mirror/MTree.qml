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
        color: "#26140F3C"
        border.color: Theme.glassEdge
    }
    Image {                                              // Her little scene while the list is empty.
        visible: t.rows.length === 0 && (t.node.empty || "") !== "" && t.height > 160
        anchors.centerIn: parent
        height: Math.min(parent.height - 40, 300)
        width: height * 412 / 292
        source: t.node.empty || ""
        sourceClipRect: Qt.rect(34, 34, 412, 292)               // Inside its own drawn frame.
        fillMode: Image.PreserveAspectFit
        smooth: true
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
                color: row.modelData.sel ? "#46389E" : (hover.hovered ? "#2A2270" : "transparent")
                border.color: row.modelData.sel ? "#9C8BFF" : "transparent"
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
