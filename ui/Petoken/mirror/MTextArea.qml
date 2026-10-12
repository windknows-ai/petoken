import QtQuick
import QtQuick.Controls.Basic
import Petoken

// A text box of several lines, scrolling inside its glass.
Item {
    id: t
    property var node: ({})
    property var m: null
    property var val: ({})
    implicitWidth: 320
    implicitHeight: node.fh !== undefined ? node.fh : 140
    opacity: val.en !== false ? 1 : 0.45
    Rectangle {
        anchors.fill: parent
        radius: 16
        color: area.activeFocus ? "#2A2268" : "#1E1850"
        border.color: area.activeFocus ? Theme.violet : Theme.glassEdge
        border.width: area.activeFocus ? 1.5 : 1
    }
    ScrollView {
        anchors.fill: parent
        anchors.margins: 4
        TextArea {
            id: area
            text: t.val.text || ""
            placeholderText: t.val.hint || ""
            placeholderTextColor: Theme.muted
            readOnly: !!t.val.ro
            enabled: t.val.en !== false
            wrapMode: TextArea.Wrap
            color: Theme.ink
            selectionColor: Theme.violet
            selectedTextColor: "#FFFFFF"
            font.family: Theme.sans
            font.pixelSize: 14
            padding: 12
            background: null
            onTextChanged: if (activeFocus) t.m.setText(t.node.id, text)
        }
    }
}
