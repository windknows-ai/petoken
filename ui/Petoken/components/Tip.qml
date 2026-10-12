import QtQuick
import QtQuick.Controls.Basic
import Petoken

// A tooltip for whatever it is laid over: shown after a short hover, in Petoken's style. The
// tooltip itself is made only while the pointer is there (hundreds of pieces carry one).
Item {
    id: tip
    property string text: ""
    anchors.fill: parent
    HoverHandler { id: hover; enabled: tip.text !== "" }
    Loader {
        active: hover.hovered && tip.text !== ""
        sourceComponent: ToolTip {
            visible: true
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
            background: Rectangle { radius: 12; color: Theme.dark ? "#F21A1446" : "#FFFFFF"; border.color: Theme.glassEdge }
            padding: 10
        }
    }
}
