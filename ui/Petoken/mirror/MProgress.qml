import QtQuick
import Petoken

// A progress bar: a glowing violet-to-gold capsule.
Item {
    id: p
    property var node: ({})
    property var m: null
    property var val: ({})
    implicitWidth: 200
    implicitHeight: Math.max(8, node.fh !== undefined ? node.fh : 10)
    Rectangle {
        anchors.fill: parent
        radius: height / 2
        color: Theme.track
        Rectangle {
            width: parent.width * Math.max(0, Math.min(1, p.val.fraction || 0))
            height: parent.height
            radius: height / 2
            gradient: Gradient {
                orientation: Gradient.Horizontal
                GradientStop { position: 0; color: Theme.violet }
                GradientStop { position: 1; color: Theme.dark ? Theme.gold : "#A497F2" }
            }
            Behavior on width { NumberAnimation { duration: Theme.smooth; easing.type: Easing.OutCubic } }
        }
    }
}
