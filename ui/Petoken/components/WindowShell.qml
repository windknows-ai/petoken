import QtQuick
import QtQuick.Effects
import Petoken

// Every Petoken window's body: rounded night glass with a soft shadow, a title bar you drag,
// window buttons, edges you resize, and a gentle rise when it opens.
Item {
    id: root
    property string title: ""
    property alias content: holder.data
    property alias titleExtras: extras.data
    property int margin: 14                               // Room for the shadow.
    signal closeRequested()

    function appear() { opener.restart() }

    Rectangle {
        id: shadowShape
        anchors { fill: body; margins: 6 }
        radius: Theme.radius + 6
        color: "#000000"
        visible: false
    }
    MultiEffect {
        anchors.fill: shadowShape
        source: shadowShape
        blurEnabled: true
        blur: 1.0
        blurMax: 40
        opacity: 0.55
    }
    Item {
        id: body
        anchors { fill: parent; margins: root.margin }
        opacity: 0
        scale: 0.965
        ParallelAnimation {
            id: opener
            NumberAnimation { target: body; property: "opacity"; from: 0; to: 1; duration: 260; easing.type: Easing.OutCubic }
            NumberAnimation { target: body; property: "scale"; from: 0.965; to: 1; duration: 420; easing.type: Easing.OutBack; easing.overshoot: 1.2 }
        }
        Rectangle {
            id: surface
            anchors.fill: parent
            radius: Theme.radius + 6
            gradient: Gradient {
                GradientStop { position: 0; color: "#16113A" }
                GradientStop { position: 0.55; color: "#120D30" }
                GradientStop { position: 1; color: "#1D1246" }
            }
            border.color: "#4A3E8C"
            border.width: 1
            Image {                                      // The night outside, faint.
                anchors.fill: parent
                source: bridge.fxUrl("sky_far")
                fillMode: Image.PreserveAspectCrop
                opacity: 0.22
                layer.enabled: true
                layer.effect: MultiEffect {
                    maskEnabled: true
                    maskSource: ShaderEffectSource { sourceItem: roundMask; hideSource: true }
                }
            }
            Rectangle { id: roundMask; anchors.fill: parent; radius: parent.radius; visible: false; layer.enabled: true }
            Rectangle {                                  // Inner rim light.
                anchors { fill: parent; margins: 1 }
                radius: parent.radius - 1
                color: "transparent"
                border.color: "#12FFFFFF"
            }
        }
        Item {                                           // Title bar: drag it to move the window.
            id: bar
            anchors { left: parent.left; right: parent.right; top: parent.top }
            height: 64
            MouseArea {
                anchors.fill: parent
                onPressed: bridge.startMove()
                onDoubleClicked: bridge.toggleMaximized()
            }
            Image {
                id: plaque
                x: 14; anchors.verticalCenter: parent.verticalCenter
                height: 52; width: height * 640 / 110
                source: bridge.wardrobeUrl("header_plaque")
                sourceSize: Qt.size(width * 2, height * 2)
            }
            Text {
                anchors.centerIn: plaque
                text: root.title
                color: Theme.ink
                font.family: Theme.serif
                font.pixelSize: 20
                font.weight: Font.Bold
                style: Text.Raised
                styleColor: "#80080616"
            }
            Row {
                id: extras
                anchors { left: plaque.right; leftMargin: 14; verticalCenter: parent.verticalCenter }
                spacing: 10
            }
            Row {
                anchors { right: parent.right; rightMargin: 14; verticalCenter: parent.verticalCenter }
                spacing: 4
                Repeater {
                    model: [ { icon: "minus", act: "min" }, { icon: "x", act: "close" } ]
                    delegate: Rectangle {
                        width: 36; height: 32; radius: 10
                        color: hover.containsMouse ? (modelData.act === "close" ? "#C0E0507A" : "#26FFFFFF") : "transparent"
                        Behavior on color { ColorAnimation { duration: Theme.quick } }
                        Icon { anchors.centerIn: parent; name: modelData.icon; size: 16; color: Theme.inkSoft }
                        MouseArea {
                            id: hover
                            anchors.fill: parent
                            hoverEnabled: true
                            onClicked: modelData.act === "close" ? root.closeRequested() : bridge.minimize()
                        }
                    }
                }
            }
        }
        Item {
            id: holder
            anchors { left: parent.left; right: parent.right; top: bar.bottom; bottom: parent.bottom }
        }
        MouseArea {                                      // Resize from the bottom-right corner.
            anchors { right: parent.right; bottom: parent.bottom }
            width: 22; height: 22
            cursorShape: Qt.SizeFDiagCursor
            onPressed: bridge.startResize()
        }
    }
}
