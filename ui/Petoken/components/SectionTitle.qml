import QtQuick
import Petoken

// A section heading, with its bracketed aside (if any) set apart in a quieter voice.
Row {
    property string key: ""
    spacing: 12
    Text {
        id: title
        text: bridge.tr(parent.key + "@title")
        color: Theme.ink
        font.family: Theme.serif
        font.pixelSize: 18
        font.weight: Font.Bold
    }
    Text {
        anchors.baseline: title.baseline
        text: bridge.tr(parent.key + "@note")
        color: Theme.muted
        font.family: Theme.sans
        font.pixelSize: 13
    }
}
