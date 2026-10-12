import QtQuick
import QtQuick.Controls.Basic
import Petoken

// A list as soft glass rows: click chooses, double click opens, a round check ticks.
Item {
    id: l
    property var node: ({})
    property var m: null
    property var val: ({})
    readonly property var rows: val.rows || []
    implicitWidth: 260
    implicitHeight: node.fh !== undefined ? node.fh : Math.min(320, Math.max(80, rows.length * 48 + 12))
    Rectangle {
        anchors.fill: parent
        radius: 18
        color: Theme.dark ? "#26140F3C" : Theme.card
        border.color: Theme.glassEdge
    }
    ListView {
        id: view
        anchors.fill: parent
        anchors.margins: 6
        clip: true
        spacing: 3
        model: l.rows
        boundsBehavior: Flickable.StopAtBounds
        ScrollBar.vertical: ScrollBar { policy: view.contentHeight > view.height ? ScrollBar.AsNeeded : ScrollBar.AlwaysOff }
        delegate: Item {
            id: row
            required property var modelData
            readonly property var r: modelData
            width: view.width - (view.contentHeight > view.height ? 10 : 0)
            height: Math.max(44, words.implicitHeight + 20)
            Rectangle {
                anchors.fill: parent
                radius: 13
                color: row.r.sel ? Theme.rowSelected : (hover.hovered && row.r.en ? Theme.rowHover : "transparent")
                border.color: row.r.sel ? Theme.rowSelectedEdge : "transparent"
                Behavior on color { ColorAnimation { duration: Theme.quick } }
            }
            Rectangle {                                  // The check: a round gem that fills with violet.
                id: tick
                visible: row.r.check
                anchors { left: parent.left; leftMargin: 12; verticalCenter: parent.verticalCenter }
                width: 22; height: 22; radius: 11
                color: row.r.on ? Theme.violet : "transparent"
                border.color: row.r.on ? Theme.violet : Theme.muted
                border.width: 1.5
                Icon { visible: row.r.on; anchors.centerIn: parent; name: "check"; size: 13; color: "#FFFFFF" }
                MouseArea { anchors.fill: parent; anchors.margins: -6; cursorShape: Qt.PointingHandCursor
                            onClicked: l.m.listCheck(l.node.id, row.r.row, !row.r.on) }
            }
            Image {
                id: pic
                visible: (row.r.icon || "") !== ""
                anchors { left: tick.visible ? tick.right : parent.left; leftMargin: 12; verticalCenter: parent.verticalCenter }
                width: visible ? 12 : 0; height: 12
                source: row.r.icon || ""
                smooth: true
            }
            Text {
                id: words
                anchors { left: pic.visible ? pic.right : (tick.visible ? tick.right : parent.left)
                          leftMargin: 12; right: parent.right; rightMargin: 12; verticalCenter: parent.verticalCenter }
                text: row.r.text
                color: !row.r.en ? Theme.muted : row.r.color ? Theme.readable(row.r.color) : Theme.ink
                font.family: Theme.sans
                font.pixelSize: 14
                font.weight: row.r.bold ? Font.Bold : Font.Normal
                font.strikeout: row.r.check && row.r.on
                opacity: row.r.check && row.r.on ? 0.6 : 1
                elide: Text.ElideRight
                maximumLineCount: 2
                wrapMode: Text.Wrap
            }
            HoverHandler { id: hover }
            TapHandler {
                enabled: row.r.en
                onTapped: l.m.listSelect(l.node.id, row.r.row)
                onDoubleTapped: l.m.listActivate(l.node.id, row.r.row)
            }
            Tip { text: row.r.tip || "" }
        }
    }
}
