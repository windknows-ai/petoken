import QtQuick
import QtQuick.Layouts
import Petoken

// Label and field pairs (a QFormLayout): labels in a quiet column, fields filling the rest.
Item {
    id: form
    property var node: ({})
    property var m: null
    readonly property var cells: {
        const out = []
        const rows = node.rows || []
        for (let i = 0; i < rows.length; i++) {
            const row = rows[i]
            if (row.span) out.push({ n: row.span, r: i, c: 0, cs: 2 })
            else {
                if (row.label) out.push({ n: row.label, r: i, c: 0, cs: 1 })
                if (row.field) out.push({ n: row.field, r: i, c: row.label ? 1 : 0, cs: row.label ? 1 : 2 })
            }
        }
        return out
    }
    implicitWidth: grid.implicitWidth
    implicitHeight: grid.implicitHeight
    GridLayout {
        id: grid
        anchors.fill: parent
        columns: 2
        rowSpacing: Math.max(12, form.node.spacing || 0)
        columnSpacing: 18
        Repeater {
            model: form.cells.length                // By count: a rebuilt tree keeps its pieces
            delegate: Loader {
                id: cell
                required property int index
                readonly property var modelData: form.cells[index] || ({})
                source: "MirrorNode.qml"
                onLoaded: { item.node = Qt.binding(() => cell.modelData.n); item.m = Qt.binding(() => form.m) }
                visible: item ? item.shown : true
                Layout.row: modelData.r
                Layout.column: modelData.c
                Layout.columnSpan: modelData.cs
                Layout.fillWidth: modelData.c === 1 || modelData.cs === 2
                Layout.fillHeight: !!(modelData.n || {}).vx
                Layout.alignment: Qt.AlignLeft | ((modelData.n || {}).vx ? Qt.AlignTop : Qt.AlignVCenter)
            }
        }
    }
}
