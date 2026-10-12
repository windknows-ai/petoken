import QtQuick

// A Phosphor icon (assets/icons) in any colour, drawn by quick_ui.Icons (no shader per icon).
Image {
    id: root
    property string name: "star"
    property bool filled: false
    property color color: "white"
    property real size: 20
    width: size
    height: size
    sourceSize: Qt.size(Math.ceil(size * Screen.devicePixelRatio), Math.ceil(size * Screen.devicePixelRatio))
    source: name !== "" ? "image://icon/" + name + "/" + (filled ? 1 : 0) + "/" + String(color).slice(1) : ""
    smooth: true
}
