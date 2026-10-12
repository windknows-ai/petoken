import QtQuick
import QtQuick.Effects
import QtQuick.Particles
import Petoken

// The standing mirror (Codex's frame and dais): the night sky in the glass, her inside wearing
// what is tried, a sheen passing over the glass, a burst of stars when something is put on.
Item {
    id: root
    property string portrait: ""                          // image://petoken/mirror/... (her and her pieces)
    property bool trying: false
    readonly property real k: Math.min(width / 760, height / 1000)
    readonly property real fw: 760 * k
    readonly property real fh: 1000 * k
    function sparkle(gold) { burst.color = gold ? Theme.gold : Theme.silver; burst.burst(gold ? 70 : 34) }

    Item {
        id: frameBox
        width: root.fw
        height: root.fh
        anchors.centerIn: parent

        Item {                                           // The glass: sky, light, her.
            id: glass
            x: 132 * root.k; y: 170 * root.k
            width: 496 * root.k; height: 730 * root.k
            clip: true
            Image {
                anchors.fill: parent
                source: bridge.fxUrl("sky_far")
                fillMode: Image.PreserveAspectCrop
                sourceSize: Qt.size(width * 2, height * 2)
                opacity: 0.95
            }
            Rectangle {
                anchors.fill: parent
                gradient: Gradient {
                    GradientStop { position: 0; color: "#22080616" }
                    GradientStop { position: 1; color: "#AA080616" }
                }
            }
            StarField { anchors.fill: parent; density: 0.7 }
            Rectangle {                                  // A pool of light where she stands.
                width: parent.width * 0.9; height: width * 0.3
                anchors.horizontalCenter: parent.horizontalCenter
                y: parent.height * 0.78
                radius: width / 2
                color: "#B6A2FF"
                opacity: 0.35
                layer.enabled: true
                layer.effect: MultiEffect { blurEnabled: true; blur: 1; blurMax: 48 }
            }
            Image {                                      // Her.
                id: her
                anchors.horizontalCenter: parent.horizontalCenter
                y: parent.height * 0.12
                width: parent.width * 1.0
                height: parent.height * 0.86
                fillMode: Image.PreserveAspectFit
                source: root.portrait
                sourceSize: Qt.size(width * Screen.devicePixelRatio, height * Screen.devicePixelRatio)
                smooth: true
                cache: false
                SequentialAnimation on y {
                    loops: Animation.Infinite
                    running: true
                    NumberAnimation { from: glass.height * 0.06; to: glass.height * 0.06 - 5; duration: 1700; easing.type: Easing.InOutSine }
                    NumberAnimation { from: glass.height * 0.06 - 5; to: glass.height * 0.06; duration: 1700; easing.type: Easing.InOutSine }
                }
                Behavior on source { SequentialAnimation {
                    NumberAnimation { target: her; property: "opacity"; to: 0.25; duration: 90 }
                    PropertyAction {}
                    NumberAnimation { target: her; property: "opacity"; to: 1; duration: 260; easing.type: Easing.OutCubic }
                } }
            }
            Rectangle {                                  // A sheen across the glass now and then.
                width: parent.width * 0.35
                height: parent.height * 1.6
                rotation: 24
                y: -parent.height * 0.3
                gradient: Gradient {
                    orientation: Gradient.Horizontal
                    GradientStop { position: 0; color: "#00FFFFFF" }
                    GradientStop { position: 0.5; color: "#2EFFFFFF" }
                    GradientStop { position: 1; color: "#00FFFFFF" }
                }
                SequentialAnimation on x {
                    loops: Animation.Infinite
                    NumberAnimation { from: -glass.width * 0.6; to: glass.width * 1.3; duration: 1400; easing.type: Easing.InOutQuad }
                    PauseAnimation { duration: 5200 }
                }
            }
            ParticleSystem { id: stars }
            ImageParticle {
                system: stars
                source: bridge.fxUrl("sparkle_champagne")
                color: Theme.gold
                colorVariation: 0.2
                alpha: 0.9
                entryEffect: ImageParticle.Scale
            }
            Emitter {
                id: burst
                property color color: Theme.gold
                system: stars
                x: glass.width / 2; y: glass.height * 0.5
                width: 2; height: 2
                enabled: false
                lifeSpan: 1100
                lifeSpanVariation: 400
                size: 22
                sizeVariation: 14
                endSize: 4
                velocity: AngleDirection { angleVariation: 360; magnitude: 220; magnitudeVariation: 120 }
                acceleration: PointDirection { y: 60 }
            }
        }
        Image {                                          // Codex's ornate frame with its dais.
            anchors.fill: parent
            source: bridge.wardrobeUrl("frame_mirror")
            sourceSize: Qt.size(width * Screen.devicePixelRatio, height * Screen.devicePixelRatio)
            smooth: true
        }
        Rectangle {                                      // "Trying on": click to go back to what she wears.
            visible: root.trying
            anchors { bottom: glass.bottom; horizontalCenter: glass.horizontalCenter; bottomMargin: 14 }
            height: 30; width: tryRow.implicitWidth + 24; radius: 15
            scale: tryMouse.pressed ? 0.95 : (tryMouse.containsMouse ? 1.04 : 1)
            Behavior on scale { NumberAnimation { duration: Theme.quick; easing.type: Easing.OutBack } }
            gradient: Gradient {
                GradientStop { position: 0; color: "#FFE7AA" }
                GradientStop { position: 1; color: "#D9922F" }
            }
            Row {
                id: tryRow
                anchors.centerIn: parent
                spacing: 6
                Text { text: bridge.tr("wardrobe_trying"); color: "#2B1806"; anchors.verticalCenter: parent.verticalCenter
                       font.family: Theme.sans; font.pixelSize: 13; font.weight: Font.Bold }
                Icon { name: "x"; size: 13; color: "#2B1806"; anchors.verticalCenter: parent.verticalCenter }
            }
            MouseArea { id: tryMouse; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                        onClicked: bridge.clearFitting() }
        }
    }
}
