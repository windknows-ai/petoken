import QtQuick
import Petoken

// Page tabs with a gold bar that glides to the chosen one.
Item {
    id: root
    property var labels: []
    property int current: 0
    signal picked(int index)
    implicitHeight: 46
    implicitWidth: row.implicitWidth

    Row {
        id: row
        spacing: 6
        Repeater {
            id: tabs
            model: root.labels
            delegate: Item {
                width: label.implicitWidth + 36
                height: root.height
                Text {
                    id: label
                    anchors.centerIn: parent
                    text: modelData
                    font.family: Theme.serif
                    font.pixelSize: 18
                    font.weight: index === root.current ? Font.Bold : Font.Medium
                    color: index === root.current ? Theme.ink : (hover.containsMouse ? Theme.inkSoft : Theme.muted)
                    Behavior on color { ColorAnimation { duration: Theme.quick } }
                }
                MouseArea {
                    id: hover
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: root.picked(index)
                }
            }
        }
    }
    Rectangle {                                          // The gliding bar, with a star at its centre.
        id: bar
        readonly property Item target: tabs.count > root.current ? tabs.itemAt(root.current) : null
        x: target ? target.x + 14 : 0
        width: target ? target.width - 28 : 0
        y: root.height - 4
        height: 3
        radius: 1.5
        gradient: Gradient {
            orientation: Gradient.Horizontal
            GradientStop { position: 0; color: "#00F3C96B" }
            GradientStop { position: 0.5; color: Theme.gold }
            GradientStop { position: 1; color: "#00F3C96B" }
        }
        Behavior on x { NumberAnimation { duration: Theme.smooth; easing.type: Easing.OutCubic } }
        Behavior on width { NumberAnimation { duration: Theme.smooth; easing.type: Easing.OutCubic } }
        Icon { anchors.centerIn: parent; name: "sparkle"; filled: true; size: 12; color: Theme.gold }
    }
}
