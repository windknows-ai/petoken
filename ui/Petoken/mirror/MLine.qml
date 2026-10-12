import QtQuick
import QtQuick.Controls.Basic
import Petoken

// A one-line text field in rounded night glass.
TextField {
    id: f
    property var node: ({})
    property var m: null
    property var val: ({})
    implicitWidth: 240
    implicitHeight: 40
    text: val.text || ""
    placeholderText: val.hint || ""
    placeholderTextColor: Theme.muted
    readOnly: !!val.ro
    enabled: val.en !== false
    echoMode: val.secret ? TextInput.Password : TextInput.Normal
    maximumLength: val.max && val.max > 0 ? val.max : 32767
    color: Theme.ink
    selectionColor: Theme.violet
    selectedTextColor: "#FFFFFF"
    font.family: Theme.sans
    font.pixelSize: 14
    leftPadding: 16
    rightPadding: 16
    opacity: enabled ? 1 : 0.45
    background: Rectangle {
        radius: 14
        color: f.activeFocus ? Theme.fieldFocus : Theme.field
        border.color: f.activeFocus ? Theme.violet : Theme.fieldEdge
        border.width: f.activeFocus ? 1.5 : 1
        Behavior on border.color { ColorAnimation { duration: Theme.quick } }
    }
    onTextEdited: m.setText(node.id, text)
    onEditingFinished: m.finish(node.id)
    Tip { text: f.val.tip || "" }
}
