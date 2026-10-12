import QtQuick
import QtQuick.Controls.Basic
import Petoken

// A tooltip for whatever it is laid over: shown after a short hover, in Petoken's glass.
Item {
    id: tip
    property string text: ""
    anchors.fill: parent
    HoverHandler { id: hover }
    ToolTip {
        visible: hover.hovered && tip.text !== ""
        delay: 650
        timeout: 8000
        text: tip.text
        contentItem: Text {
            text: tip.text
            color: Theme.ink
            font.family: Theme.sans
            font.pixelSize: 13
            wrapMode: Text.Wrap
            lineHeight: 1.2
        }
        background: Rectangle { radius: 12; color: "#F21A1446"; border.color: Theme.glassEdge }
        padding: 10
    }
}
