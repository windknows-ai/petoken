import QtQuick
import QtQuick.Effects

// A Phosphor icon (assets/icons) tinted to any colour.
Item {
    id: root
    property string name: "star"
    property bool filled: false
    property color color: "white"
    property real size: 20
    implicitWidth: size
    implicitHeight: size

    Image {
        id: glyph
        anchors.fill: parent
        source: root.name !== "" ? bridge.iconUrl(root.name, root.filled) : ""
        sourceSize: Qt.size(root.size * 2, root.size * 2)
        visible: false
        smooth: true
    }
    MultiEffect {
        anchors.fill: glyph
        source: glyph
        colorization: 1.0
        colorizationColor: root.color
        brightness: 1.0
    }
}
