import QtQuick
import QtQuick.Effects
import Petoken

// The one button: a lacquered pill with a gem-like gradient that lifts and glows under the
// pointer and presses in with a spring. Kinds: "violet" (default), "gold", "ghost".
Item {
    id: root
    property string text: ""
    property string icon: ""
    property string kind: "violet"
    property bool checked: false
    property real fontSize: 14
    signal clicked()

    implicitHeight: 40
    implicitWidth: Math.max(96, label.implicitWidth + (icon ? 30 : 0) + 34)
    opacity: enabled ? 1 : 0.42

    readonly property color topColour: kind === "gold" ? "#FFE7AA" : kind === "ghost" ? "#26FFFFFF" : "#A98BFF"
    readonly property color bottomColour: kind === "gold" ? "#D9922F" : kind === "ghost" ? "#10FFFFFF" : "#5B78F0"
    readonly property color textColour: kind === "gold" ? "#2B1806" : Theme.ink
    readonly property bool hot: mouse.containsMouse && enabled

    Item {
        id: body
        anchors.fill: parent
        scale: mouse.pressed && root.enabled ? 0.95 : (root.hot ? 1.03 : 1.0)
        Behavior on scale { SpringAnimation { spring: 5; damping: 0.32; epsilon: 0.002 } }

        Rectangle {                                      // Its glow.
            id: glowShape
            anchors.fill: pill
            radius: pill.radius
            color: root.kind === "gold" ? Theme.gold : Theme.violet
            visible: false
        }
        MultiEffect {
            anchors.fill: glowShape
            source: glowShape
            blurEnabled: true
            blur: 1.0
            blurMax: 32
            opacity: (root.hot ? 0.75 : 0.0) + (root.checked ? 0.5 : 0) * (root.kind === "ghost" ? 1 : 0)
            visible: root.kind !== "ghost" || root.checked
            Behavior on opacity { NumberAnimation { duration: Theme.smooth } }
        }
        Rectangle {
            id: pill
            anchors.fill: parent
            radius: height / 2
            gradient: Gradient {
                GradientStop { position: 0; color: root.checked && root.kind === "ghost" ? "#4A3A9C" : root.topColour }
                GradientStop { position: 1; color: root.checked && root.kind === "ghost" ? "#2C2470" : root.bottomColour }
            }
            border.width: 1.2
            border.color: root.kind === "gold" ? "#FFF3D2" : (root.checked ? Theme.gold : Theme.glassEdge)
            Rectangle {                                  // Light across the top half: lacquer.
                anchors { left: parent.left; right: parent.right; top: parent.top; margins: 2 }
                height: parent.height * 0.45
                radius: height / 2
                gradient: Gradient {
                    GradientStop { position: 0; color: "#55FFFFFF" }
                    GradientStop { position: 1; color: "#00FFFFFF" }
                }
                opacity: root.kind === "ghost" ? 0.4 : 1
            }
        }
        Row {
            anchors.centerIn: parent
            spacing: 7
            Icon {
                visible: root.icon !== ""
                name: root.icon
                size: 17
                color: root.textColour
                anchors.verticalCenter: parent.verticalCenter
            }
            Text {
                id: label
                text: root.text
                color: root.textColour
                font.family: Theme.sans
                font.pixelSize: root.fontSize
                font.weight: Font.DemiBold
                anchors.verticalCenter: parent.verticalCenter
            }
        }
    }
    MouseArea {
        id: mouse
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: root.enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
        onClicked: if (root.enabled) root.clicked()
    }
}
