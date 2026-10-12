import QtQuick
import Petoken

// A frosted night-glass panel with a fine silver rim and a soft inner light.
Rectangle {
    radius: Theme.radius
    gradient: Gradient {
        GradientStop { position: 0; color: "#661C1550" }
        GradientStop { position: 1; color: "#80100C30" }
    }
    border.color: Theme.glassEdge
    border.width: 1
    Rectangle {
        anchors { fill: parent; margins: 1 }
        radius: parent.radius - 1
        color: "transparent"
        border.color: "#14FFFFFF"
        border.width: 1
    }
}
