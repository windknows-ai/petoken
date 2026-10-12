import QtQuick
import QtQuick.Layouts
import Petoken

// A row or a column of widgets (a QBoxLayout), sharing the space the way Qt would.
Item {
    id: box
    property var node: ({})
    property var m: null
    readonly property bool across: node.dir === "h"
    readonly property var items: node.items || []
    // Qt gives extra room to expanding pieces (or those with a stretch); with none, to all that can grow.
    readonly property bool anyStretch: items.some(i => (i.stretch || 0) > 0 || (across ? i.hx : i.vx))
    readonly property var margins: node.margins || [0, 0, 0, 0]
    implicitWidth: grid.implicitWidth + margins[0] + margins[2]
    implicitHeight: grid.implicitHeight + margins[1] + margins[3]

    GridLayout {
        id: grid
        anchors.fill: parent
        anchors.leftMargin: box.margins[0]
        anchors.topMargin: box.margins[1]
        anchors.rightMargin: box.margins[2]
        anchors.bottomMargin: box.margins[3]
        flow: box.across ? GridLayout.LeftToRight : GridLayout.TopToBottom
        rows: box.across ? 1 : Math.max(1, box.items.length)
        columns: box.across ? Math.max(1, box.items.length) : 1
        readonly property real loose: box.m && box.m.dense ? 0.75 : 1.15
        readonly property int gap: box.node.spacing === undefined || box.node.spacing < 0 ? 8 * loose / 1.15 : Math.max(2, box.node.spacing * loose)
        rowSpacing: gap
        columnSpacing: Math.max(8, gap)
        Repeater {
            model: box.items.length                // By count: a rebuilt tree keeps its pieces
            delegate: Loader {
                id: cell
                required property int index
                readonly property var modelData: box.items[index] || ({})
                readonly property var n: modelData
                readonly property int stretch: n.stretch || 0
                readonly property bool alignedH: ((n.align || 0) & (Qt.AlignLeft | Qt.AlignRight | Qt.AlignHCenter)) !== 0
                readonly property bool alignedV: ((n.align || 0) & (Qt.AlignTop | Qt.AlignBottom | Qt.AlignVCenter)) !== 0
                source: "MirrorNode.qml"
                onLoaded: { item.node = Qt.binding(() => cell.n); item.m = Qt.binding(() => box.m) }
                visible: item ? item.shown : true
                readonly property bool fillW: box.across
                    ? (box.anyStretch ? (stretch > 0 || !!n.hx) : (!!n.hg && n.t !== "label" && n.t !== "space"
                                                                    && n.t !== "button" && n.t !== "check"))
                    : (!alignedH && n.t !== "space" && n.hg !== false && n.fw === undefined)
                // Across, Qt stretches every piece that may grow to the row's height (cards side by side line up).
                readonly property bool fillH: box.across ? (!alignedV && (!!n.vx || (n.t === "container" && n.vg !== false))) : (stretch > 0 || !!n.vx)
                Layout.fillWidth: fillW
                Layout.fillHeight: fillH
                Layout.horizontalStretchFactor: fillW && box.across ? Math.max(1, stretch) : -1
                Layout.verticalStretchFactor: fillH && !box.across ? Math.max(1, stretch) : -1
                Layout.preferredWidth: n.fw !== undefined ? n.fw : -1
                Layout.preferredHeight: n.fh !== undefined ? n.fh : -1
                Layout.minimumWidth: n.mw !== undefined ? Math.min(n.mw, 520) : ({ spin: 150, combo: 150, date: 180, line: 120 })[n.t] || 0
                Layout.minimumHeight: n.mh !== undefined ? Math.min(n.mh, 400) : 0
                Layout.maximumWidth: n.xw !== undefined ? n.xw : Number.POSITIVE_INFINITY
                Layout.alignment: {
                    const a = n.align || 0
                    const h = (a & Qt.AlignRight) ? Qt.AlignRight : ((a & Qt.AlignHCenter) ? Qt.AlignHCenter : Qt.AlignLeft)
                    let v = (a & Qt.AlignTop) ? Qt.AlignTop : ((a & Qt.AlignBottom) ? Qt.AlignBottom : Qt.AlignVCenter)
                    if (!box.across && !(a & Qt.AlignVCenter) && !(a & Qt.AlignBottom)) v = Qt.AlignTop
                    return h | v
                }
            }
        }
    }
}
