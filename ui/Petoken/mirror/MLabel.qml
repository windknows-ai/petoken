import QtQuick
import Petoken

// A label: words (plain or rich, links work) or a picture. Petoken's label roles pick the voice.
Item {
    id: l
    property var node: ({})
    property var m: null
    property var val: ({})
    readonly property string role: node.role || ""
    readonly property bool picture: (val.img || "") !== "" && (val.text || "") === ""
    readonly property bool pill: role === "summary"
    readonly property int size: (l.m && l.m.dense) ? (val.size ? Math.max(13, val.size) : 13) : val.size ? Math.max(13, val.size + 1)
                                : role === "heading" ? 22 : role === "section" ? 15 : role === "muted" ? 13 : 14
    readonly property real wrapAt: val.wrap ? 560 : 100000
    implicitWidth: picture ? (val.imgw || 64) : Math.min(words.implicitWidth, wrapAt) + (pill ? 28 : 0)
    implicitHeight: picture ? (val.imgh || 64) : words.implicitHeight + (pill ? 12 : 0)
    Image {
        visible: l.picture
        anchors.centerIn: parent
        width: l.val.imgw || 64
        height: l.val.imgh || 64
        source: l.val.img || ""
        fillMode: Image.PreserveAspectFit
        smooth: true
    }
    Rectangle {                                          // The workbench's summary pill.
        visible: l.pill
        anchors.fill: parent
        radius: Math.min(height / 2, 14)                 // A pill on one line, a soft box on several.
        color: Theme.dark ? "#2A2070" : "#EEEAFB"
        border.color: Theme.glassEdge
    }
    Text {
        id: words
        visible: !l.picture
        x: l.pill ? 14 : 0
        width: l.width - (l.pill ? 28 : 0)
        anchors.verticalCenter: parent.verticalCenter
        text: l.val.text || ""
        textFormat: l.val.rich ? Text.RichText : Text.PlainText
        wrapMode: l.val.wrap ? Text.Wrap : Text.NoWrap
        elide: l.val.wrap ? Text.ElideNone : Text.ElideRight
        horizontalAlignment: ((l.val.align || 0) & Qt.AlignHCenter) ? Text.AlignHCenter
                             : ((l.val.align || 0) & Qt.AlignRight) ? Text.AlignRight : Text.AlignLeft
        color: l.val.color && !l.pill ? Theme.readable(l.val.color)
               : l.role === "muted" ? Theme.muted : l.role === "section" ? Theme.violetSoft
               : l.pill ? (Theme.dark ? Theme.gold : Theme.inkSoft) : Theme.ink
        linkColor: Theme.ice
        lineHeight: 1.18
        font.family: l.role === "heading" ? Theme.serif : Theme.sans
        font.pixelSize: l.size
        font.weight: (l.role === "heading" || l.role === "section" || l.val.bold) ? Font.Bold : Font.Normal
        onLinkActivated: (link) => l.m.link(l.node.id, link)
        HoverHandler { cursorShape: words.hoveredLink ? Qt.PointingHandCursor : Qt.ArrowCursor }
    }
    Tip { text: l.val.tip || "" }
}
