import QtQuick
import QtQuick.Controls.Basic
import Petoken

// A slider: a glowing violet-to-gold groove with a pearl handle.
Slider {
    id: s
    property var node: ({})
    property var m: null
    property var val: ({})
    implicitWidth: 220
    implicitHeight: 32
    from: val.min || 0
    to: val.max !== undefined ? val.max : 100
    stepSize: val.step || 1
    snapMode: Slider.SnapAlways
    value: val.value || 0
    enabled: val.en !== false
    opacity: enabled ? 1 : 0.45
    onMoved: m.setValue(node.id, value)
    background: Rectangle {
        x: s.leftPadding
        y: s.topPadding + s.availableHeight / 2 - height / 2
        width: s.availableWidth
        height: 8
        radius: 4
        color: Theme.track
        Rectangle {
            width: s.visualPosition * parent.width
            height: parent.height
            radius: 4
            gradient: Gradient {
                orientation: Gradient.Horizontal
                GradientStop { position: 0; color: Theme.violet }
                GradientStop { position: 1; color: Theme.dark ? Theme.gold : "#A497F2" }
            }
        }
    }
    handle: Rectangle {
        x: s.leftPadding + s.visualPosition * (s.availableWidth - width)
        y: s.topPadding + s.availableHeight / 2 - height / 2
        width: 22; height: 22; radius: 11
        color: "#FFFFFF"
        border.color: Theme.violet
        border.width: 2
        scale: s.pressed ? 1.15 : 1
        Behavior on scale { NumberAnimation { duration: Theme.quick } }
    }
    Tip { text: s.val.tip || "" }
}
