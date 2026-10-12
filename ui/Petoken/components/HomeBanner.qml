import QtQuick
import QtQuick.Effects
import Petoken

// The home page's greeting: night sky (Codex's banner when there is one), her waving, the hour's greeting.
Item {
    id: banner
    Rectangle {
        id: shape
        anchors.fill: parent
        radius: Theme.radius + 4
        gradient: Gradient {
            orientation: Gradient.Horizontal
            GradientStop { position: 0; color: "#2A1D68" }
            GradientStop { position: 1; color: "#130E38" }
        }
        border.color: "#5A4BA8"
        visible: !card.visible
    }
    BorderImage {                                        // Codex's banner frame: moon, filigree and clouds.
        id: card
        anchors.fill: parent
        anchors.margins: -6
        source: bridge.artUrl("hero_home")
        visible: source != ""
        border { left: 150; right: 150; top: 70; bottom: 90 }
        horizontalTileMode: BorderImage.Stretch
        verticalTileMode: BorderImage.Stretch
    }
    Item {
        anchors.fill: parent
        layer.enabled: true
        layer.effect: MultiEffect {
            maskEnabled: true
            maskSource: ShaderEffectSource { sourceItem: roundMask; hideSource: true }
        }
        Image {
            visible: !card.visible
            anchors.fill: parent
            source: bridge.fxUrl("sky_far")
            fillMode: Image.PreserveAspectCrop
            opacity: 0.5
            sourceSize: Qt.size(width * 2, height * 2)
        }
        StarField { anchors.fill: parent; density: 0.8 }
        Image {                                          // Her, peeking up from the left.
            id: her
            x: 12
            y: parent.height * 0.08
            width: parent.height * 1.08
            height: parent.height * 1.08
            source: bridge.herUrl
            fillMode: Image.PreserveAspectFit
            sourceSize: Qt.size(width * 2, height * 2)
            smooth: true
            SequentialAnimation on y {
                loops: Animation.Infinite
                NumberAnimation { from: banner.height * 0.08; to: banner.height * 0.05; duration: 1800; easing.type: Easing.InOutSine }
                NumberAnimation { from: banner.height * 0.05; to: banner.height * 0.08; duration: 1800; easing.type: Easing.InOutSine }
            }
        }
    }
    Rectangle { id: roundMask; anchors.fill: parent; radius: shape.radius; visible: false; layer.enabled: true }
    Column {
        anchors { left: parent.left; leftMargin: banner.height * 1.12 + 10; right: tutorial.left; rightMargin: 16
                  verticalCenter: parent.verticalCenter }
        spacing: 6
        Text { text: bridge.greeting; color: Theme.gold; font.family: Theme.sans; font.pixelSize: 15; font.weight: Font.DemiBold }
        Text { text: bridge.heading; color: Theme.ink; font.family: Theme.serif; font.pixelSize: 30; font.weight: Font.Black }
        Text { width: parent.width; text: bridge.subtitle; color: Theme.inkSoft; wrapMode: Text.Wrap
               font.family: Theme.sans; font.pixelSize: 14; lineHeight: 1.2 }
    }
    GemButton {
        id: tutorial
        anchors { right: parent.right; rightMargin: 22; verticalCenter: parent.verticalCenter }
        kind: "ghost"
        height: 40
        icon: "graduation-cap"
        text: bridge.tutorialText
        onClicked: bridge.tutorial()
    }
}
