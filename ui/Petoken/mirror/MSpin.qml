import QtQuick
import Petoken

// A number: minus and plus gems around the value (typing works too), with its unit.
Item {
    id: s
    property var node: ({})
    property var m: null
    property var val: ({})
    readonly property real value: val.value || 0
    readonly property real step: val.step || 1
    readonly property int decimals: val.decimals || 0
    implicitWidth: 170
    implicitHeight: 40
    opacity: val.en !== false ? 1 : 0.45
    function shown(v) { return (s.val.prefix || "") + v.toFixed(s.decimals) + (s.val.suffix || "") }
    function put(v) { s.m.setValue(s.node.id, Math.max(s.val.min, Math.min(s.val.max, v))) }
    Rectangle { anchors.fill: parent; radius: height / 2; color: "#1E1850"; border.color: Theme.glassEdge }
    GemButton { id: less; kind: "ghost"; anchors { left: parent.left; verticalCenter: parent.verticalCenter }
                height: 40; implicitWidth: 40; icon: "minus"; text: ""
                enabled: s.val.en !== false && s.value > s.val.min; onClicked: s.put(s.value - s.step) }
    TextInput {
        anchors { left: less.right; right: more.left; verticalCenter: parent.verticalCenter }
        horizontalAlignment: TextInput.AlignHCenter
        text: s.shown(s.value)
        color: Theme.ink
        selectionColor: Theme.violet
        font.family: Theme.sans
        font.pixelSize: 14
        font.weight: Font.DemiBold
        enabled: s.val.en !== false
        onEditingFinished: {
            const n = parseFloat(text.replace(s.val.prefix || "", "").replace(s.val.suffix || "", ""))
            if (!isNaN(n)) s.put(n)
        }
    }
    GemButton { id: more; kind: "ghost"; anchors { right: parent.right; verticalCenter: parent.verticalCenter }
                height: 40; implicitWidth: 40; icon: "plus"; text: ""
                enabled: s.val.en !== false && s.value < s.val.max; onClicked: s.put(s.value + s.step) }
    WheelHandler { onWheel: (e) => s.put(s.value + (e.angleDelta.y > 0 ? s.step : -s.step)) }
    Tip { text: s.val.tip || "" }
}
