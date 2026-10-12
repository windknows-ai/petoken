import QtQuick
import QtQuick.Effects
import Petoken

// The wardrobe's two doors (Codex's art) swinging open in true perspective, light pouring out.
Item {
    id: root
    property real progress: 0                            // 0 shut .. 1 open.
    visible: progress < 1
    function open() { progress = 0; swing.restart() }

    NumberAnimation on progress { id: swing; running: false; from: 0; to: 1; duration: 1150; easing.type: Easing.InOutCubic }

    Rectangle {                                          // The light inside.
        anchors.fill: parent
        gradient: Gradient {
            GradientStop { position: 0; color: "#00FFE9B8" }
            GradientStop { position: 0.5; color: "#FFFFE9B8" }
            GradientStop { position: 1; color: "#00FFE9B8" }
            orientation: Gradient.Horizontal
        }
        opacity: Math.sin(Math.min(1, root.progress * 1.6) * Math.PI) * 0.8
    }
    Image {
        id: left
        width: parent.width / 2
        height: parent.height
        source: bridge.wardrobeUrl("door_left")
        sourceSize: Qt.size(width * 1.5, height * 1.5)
        transform: Rotation {
            origin.x: 0; origin.y: left.height / 2
            axis { x: 0; y: 1; z: 0 }
            angle: -100 * root.progress
        }
    }
    Image {
        id: right
        x: parent.width / 2
        width: parent.width / 2
        height: parent.height
        source: bridge.wardrobeUrl("door_right")
        sourceSize: Qt.size(width * 1.5, height * 1.5)
        transform: Rotation {
            origin.x: right.width; origin.y: right.height / 2
            axis { x: 0; y: 1; z: 0 }
            angle: 100 * root.progress
        }
    }
}
