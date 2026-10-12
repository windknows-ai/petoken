import QtQuick
import QtQuick.Controls.Basic
import Petoken

// Tabs: Petoken's gliding tab strip over the page; with many tabs, a rail of pills down the left.
Item {
    id: t
    property var node: ({})
    property var m: null
    property var val: ({})
    readonly property int current: val.current || 0
    readonly property var labels: val.labels || []
    readonly property bool rail: labels.length > 5
    readonly property int railWidth: rail ? 196 : 0
    readonly property Item shownPage: {
        const box = pagesRep.count > t.current ? pagesRep.itemAt(t.current) : null
        return box ? box.item : null
    }
    implicitWidth: (rail ? railWidth + 18 : 0) + Math.max(rail ? 0 : strip.implicitWidth, shownPage ? shownPage.implicitWidth : 0)
    implicitHeight: rail ? Math.max(railColumn.implicitHeight, shownPage ? shownPage.implicitHeight : 0)
                         : strip.height + 12 + (shownPage ? shownPage.implicitHeight : 0)
    TabStrip {
        id: strip
        visible: !t.rail
        width: parent.width
        labels: t.rail ? [] : t.labels
        current: t.current
        onPicked: (index) => t.m.setIndex(t.node.id, index)
    }
    Column {
        id: railColumn
        visible: t.rail
        width: t.railWidth
        spacing: 6
        Repeater {
            model: t.rail ? t.labels : []
            delegate: Rectangle {
                required property var modelData
                required property int index
                readonly property bool chosen: index === t.current
                visible: (t.val.shown || [])[index] !== false
                width: t.railWidth
                height: 44
                radius: 22
                gradient: Gradient {
                    orientation: Gradient.Horizontal
                    GradientStop { position: 0; color: chosen ? Theme.rowSelected : (hover.hovered ? Theme.rowHover : "#00000000") }
                    GradientStop { position: 1; color: chosen ? Theme.rowSelected : (hover.hovered ? Theme.rowHover : "#00000000") }
                }
                border.color: chosen ? Theme.rowSelectedEdge : "transparent"
                Image {
                    id: railIcon
                    x: 14; anchors.verticalCenter: parent.verticalCenter
                    width: visible ? 22 : 0; height: 22
                    source: (t.val.icons || [])[index] || ""
                    visible: source != ""
                    smooth: true
                }
                Text {
                    anchors { left: railIcon.right; leftMargin: railIcon.visible ? 10 : 18; right: parent.right; rightMargin: 12
                              verticalCenter: parent.verticalCenter }
                    text: modelData
                    elide: Text.ElideRight
                    color: chosen ? Theme.violetSoft : Theme.ink
                    font.family: Theme.sans
                    font.pixelSize: 14
                    font.weight: chosen ? Font.Bold : Font.Medium
                }
                HoverHandler { id: hover; cursorShape: Qt.PointingHandCursor }
                TapHandler { onTapped: t.m.setIndex(t.node.id, index) }
                Tip { text: (t.val.tips || [])[index] || "" }
            }
        }
    }
    Repeater {                                           // Each page built the first time it is shown, then kept.
        id: pagesRep
        model: (t.node.pages || []).length
        delegate: Loader {
            required property int index
            readonly property var pageNode: (t.node.pages || [])[index] || null
            property bool seen: false
            readonly property bool current: index === t.current
            onCurrentChanged: if (current) seen = true
            Component.onCompleted: if (current) seen = true
            anchors.left: parent.left
            anchors.leftMargin: t.rail ? t.railWidth + 18 : 0
            anchors.right: parent.right
            anchors.top: t.rail ? parent.top : strip.bottom
            anchors.topMargin: t.rail ? 0 : 12
            anchors.bottom: parent.bottom
            visible: current
            active: seen && pageNode !== null
            asynchronous: true                               // A big page builds without freezing the window.
            source: "MirrorNode.qml"
            onLoaded: { item.node = Qt.binding(() => pageNode); item.m = Qt.binding(() => t.m) }
        }
    }
}
