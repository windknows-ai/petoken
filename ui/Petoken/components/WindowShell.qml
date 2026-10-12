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
    property bool compact: false                          // A dialog: a lower title bar, no minimize.
    property bool bare: false                             // No title bar at all (the page has its own).
    property string backdrop: ""                          // A drawn background over the night (Codex's art).
    signal closeRequested()

    function appear() { opener.restart() }

    Rectangle {
        id: shadowShape
        anchors { fill: body; margins: 6 }
        radius: Theme.windowRadius
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
            radius: Theme.windowRadius
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
                sourceSize: Qt.size(1280, 800)
                opacity: 0.22
                layer.enabled: true
                layer.effect: MultiEffect {
                    maskEnabled: true
                    maskSource: ShaderEffectSource { sourceItem: roundMask; hideSource: true }
                }
            }
            Image {                                      // The window's own backdrop, when it has one.
                visible: root.backdrop !== ""
                anchors.fill: parent
                source: root.backdrop
                fillMode: Image.PreserveAspectCrop
                sourceSize: Qt.size(1920, 1200)
                opacity: 0.85
                layer.enabled: visible
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
            height: root.bare ? 0 : (root.compact ? 56 : 64)
            visible: !root.bare
            MouseArea {
                anchors.fill: parent
                onPressed: bridge.startMove()
                onDoubleClicked: bridge.toggleMaximized()
            }
            Row {                                        // Title: a round gem badge and the name.
                id: plaque
                x: 22; anchors.verticalCenter: parent.verticalCenter
                spacing: 12
                Rectangle {
                    width: root.compact ? 32 : 38; height: width; radius: width / 2
                    anchors.verticalCenter: parent.verticalCenter
                    gradient: Gradient {
                        GradientStop { position: 0; color: "#7A63E8" }
                        GradientStop { position: 1; color: "#3B2C8E" }
                    }
                    border.color: "#66FFFFFF"
                    Image { id: badgeArt; anchors.fill: parent; source: bridge.artUrl("app_badge"); visible: source != ""
                            sourceSize: Qt.size(96, 96); smooth: true }
                    Icon { visible: !badgeArt.visible; anchors.centerIn: parent; name: "sparkle"; filled: true; size: root.compact ? 17 : 20; color: Theme.gold }
                }
                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    text: root.title
                    color: Theme.ink
                    font.family: Theme.serif
                    font.pixelSize: root.compact ? 18 : 21
                    font.weight: Font.Bold
                }
            }
            Row {
                id: extras
                anchors { left: plaque.right; leftMargin: 22; verticalCenter: parent.verticalCenter }
                spacing: 10
            }
            Row {
                anchors { right: parent.right; rightMargin: 18; verticalCenter: parent.verticalCenter }
                spacing: 8
                Repeater {
                    model: root.compact ? [ { icon: "x", act: "close" } ] : [ { icon: "minus", act: "min" }, { icon: "x", act: "close" } ]
                    delegate: Rectangle {
                        width: 34; height: 34; radius: 17
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
