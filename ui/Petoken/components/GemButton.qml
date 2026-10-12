import QtQuick
import QtQuick.Effects
import Petoken

// The one button: a lacquered pill with a gem-like gradient that lifts and glows under the
// pointer and presses in with a spring. Kinds: "violet" (default), "gold", "ghost", "danger".
Item {
    id: root
    property string text: ""
    property string icon: ""
    property string imageIcon: ""                        // A picture instead of a Phosphor icon.
    property string kind: "violet"
    property bool checked: false
    property real fontSize: 14
    signal clicked()

    implicitHeight: 40
    implicitWidth: text === "" ? Math.max(44, implicitHeight) : Math.max(88, label.implicitWidth + (icon || imageIcon ? 30 : 0) + 36)
    opacity: enabled ? 1 : 0.42

    readonly property bool ghostly: kind === "ghost" || kind === "danger"
    readonly property color topColour: kind === "gold" ? "#FFE7AA"
        : kind === "ghost" ? (Theme.dark ? "#26FFFFFF" : "#FFFFFF")
        : kind === "danger" ? (Theme.dark ? "#40FF7A9C" : "#FFFFFF")
        : (Theme.dark ? "#A98BFF" : "#8676E4")
    readonly property color bottomColour: kind === "gold" ? "#D9922F"
        : kind === "ghost" ? (Theme.dark ? "#10FFFFFF" : "#F3F0FA")
        : kind === "danger" ? (Theme.dark ? "#20FF7A9C" : "#FBF1F4")
        : (Theme.dark ? "#5B78F0" : "#6655C8")
    readonly property color textColour: kind === "gold" ? "#2B1806" : kind === "danger" ? Theme.danger
        : kind === "ghost" || Theme.dark ? Theme.ink : "#FFFFFF"
    readonly property bool hot: mouse.containsMouse && enabled

    Item {
        id: body
        anchors.fill: parent
        scale: mouse.pressed && root.enabled ? 0.96 : (root.hot && Theme.dark ? 1.03 : 1.0)
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
            visible: Theme.dark && (!root.ghostly || root.checked)
            Behavior on opacity { NumberAnimation { duration: Theme.smooth } }
        }
        Rectangle {
            id: pill
            anchors.fill: parent
            radius: height / 2
            gradient: Gradient {
                GradientStop { position: 0; color: root.checked && root.kind === "ghost" ? (Theme.dark ? "#4A3A9C" : "#ECE7FB") : (root.hot && Theme.light && root.ghostly ? Theme.rowHover : root.topColour) }
                GradientStop { position: 1; color: root.checked && root.kind === "ghost" ? (Theme.dark ? "#2C2470" : "#E0D8F7") : root.bottomColour }
            }
            border.width: 1.2
            border.color: root.kind === "gold" ? "#FFF3D2" : root.kind === "danger" ? (Theme.dark ? "#80FF8FAB" : "#E3B5C3")
                          : root.checked ? (Theme.dark ? Theme.gold : Theme.violet) : (root.ghostly ? Theme.fieldEdge : (Theme.dark ? Theme.glassEdge : "#5A4BB4"))
            Rectangle {                                  // Light across the top half: lacquer.
                anchors { left: parent.left; right: parent.right; top: parent.top; margins: 2 }
                height: parent.height * 0.45
                radius: height / 2
                gradient: Gradient {
                    GradientStop { position: 0; color: "#55FFFFFF" }
                    GradientStop { position: 1; color: "#00FFFFFF" }
                }
                opacity: Theme.light ? (root.ghostly ? 0 : 0.35) : (root.kind === "ghost" ? 0.4 : 1)
            }
        }
        Row {
            anchors.centerIn: parent
            spacing: 7
            Image {
                visible: root.imageIcon !== "" && root.icon === ""
                source: root.imageIcon
                width: 18; height: 18
                sourceSize: Qt.size(36, 36)
                anchors.verticalCenter: parent.verticalCenter
            }
            Icon {
                visible: root.icon !== ""
                name: root.icon
                size: 17
                color: root.textColour
                anchors.verticalCenter: parent.verticalCenter
            }
            Text {
                id: label
                visible: root.text !== ""
                text: root.text
                color: root.textColour
                font.family: Theme.sans
                font.pixelSize: root.fontSize
                font.weight: root.ghostly && Theme.light ? Font.Normal : Font.DemiBold
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
