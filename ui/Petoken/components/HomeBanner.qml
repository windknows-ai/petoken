import QtQuick
import Petoken

// The home page's greeting: a calm card with her, the hour's greeting and the tutorial button.
Rectangle {
    id: banner
    radius: Theme.radius
    gradient: Gradient {
        orientation: Gradient.Horizontal
        GradientStop { position: 0; color: Theme.dark ? "#2A1D68" : "#EEEAFB" }
        GradientStop { position: 1; color: Theme.dark ? "#130E38" : "#F8F7FD" }
    }
    border.color: Theme.cardEdge
    clip: true
    Image {                                              // Her, waving from the left.
        id: her
        x: 8
        anchors.bottom: parent.bottom
        height: parent.height * 1.05
        width: height
        source: bridge.herUrl
        fillMode: Image.PreserveAspectFit
        sourceSize: Qt.size(width * 2, height * 2)
        smooth: true
    }
    Column {
        anchors { left: her.right; leftMargin: 8; right: tutorial.left; rightMargin: 16
                  verticalCenter: parent.verticalCenter }
        spacing: 6
        Text { text: bridge.greeting; color: Theme.violet; font.family: Theme.sans; font.pixelSize: 14; font.weight: Font.DemiBold }
        Text { text: bridge.heading; color: Theme.ink; font.family: Theme.serif; font.pixelSize: 24; font.weight: Font.Bold }
        Text { width: parent.width; text: bridge.subtitle; color: Theme.inkSoft; wrapMode: Text.Wrap
               font.family: Theme.sans; font.pixelSize: 14; lineHeight: 1.25 }
    }
    GemButton {
        id: tutorial
        anchors { right: parent.right; rightMargin: 20; verticalCenter: parent.verticalCenter }
        kind: "ghost"
        height: 38
        icon: "graduation-cap"
        text: bridge.tutorialText
        onClicked: bridge.tutorial()
    }
}
