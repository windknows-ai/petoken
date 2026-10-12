import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import Petoken

// A date and time: a glass pill showing it, opening a month calendar and hour/minute spinners.
Item {
    id: d
    property var node: ({})
    property var m: null
    property var val: ({})
    readonly property date when: val.iso ? new Date(val.iso) : new Date()
    readonly property bool hasTime: (node.format || "").indexOf("H") >= 0
    readonly property bool hasDate: (node.format || "yyyy").indexOf("y") >= 0 || (node.format || "").indexOf("d") >= 0
    implicitWidth: Math.max(190, shown.implicitWidth + 60)
    implicitHeight: 40
    opacity: val.en !== false ? 1 : 0.45
    function put(year, month, day, hour, minute) {
        const pad = (n) => (n < 10 ? "0" : "") + n
        d.m.setDate(d.node.id, `${year}-${pad(month + 1)}-${pad(day)}T${pad(hour)}:${pad(minute)}:00`)
    }
    Rectangle { anchors.fill: parent; radius: height / 2; color: area.containsMouse ? Theme.rowHover : Theme.field
                border.color: popBox.opened ? Theme.violet : Theme.fieldEdge }
    Icon { id: cal; anchors { left: parent.left; leftMargin: 14; verticalCenter: parent.verticalCenter }
           name: d.hasDate ? "calendar-blank" : "clock"; size: 16; color: Theme.inkSoft }
    Text { id: shown; anchors { left: cal.right; leftMargin: 10; verticalCenter: parent.verticalCenter }
           text: d.val.text || ""; color: Theme.ink; font.family: Theme.sans; font.pixelSize: 14 }
    MouseArea { id: area; anchors.fill: parent; hoverEnabled: true; enabled: d.val.en !== false
                cursorShape: Qt.PointingHandCursor; onClicked: popBox.open() }
    Loader {                                             // Made only when it opens.
        id: popBox
        active: false
        readonly property bool opened: item ? item.opened : false
        function open() { active = true; item.open() }
        function close() { if (item) item.close() }
        sourceComponent: Component {
            Popup {
                id: pop
                onClosed: Qt.callLater(() => popBox.active = false)
                y: d.height + 6
                padding: 14
                property int year: d.when.getFullYear()
                property int month: d.when.getMonth()
                onAboutToShow: { year = d.when.getFullYear(); month = d.when.getMonth() }
                background: Rectangle { radius: 20; color: Theme.popup; border.color: Theme.glassEdge }
                contentItem: ColumnLayout {
                    spacing: 10
                    RowLayout {
                        visible: d.hasDate
                        Layout.fillWidth: true
                        GemButton { kind: "ghost"; height: 32; implicitWidth: 32; icon: "caret-left"; text: ""
                                    onClicked: { if (pop.month === 0) { pop.month = 11; pop.year-- } else pop.month-- } }
                        Text { Layout.fillWidth: true; horizontalAlignment: Text.AlignHCenter
                               text: pop.year + " · " + (pop.month + 1); color: Theme.ink; font.family: Theme.sans
                               font.pixelSize: 15; font.weight: Font.DemiBold }
                        GemButton { kind: "ghost"; height: 32; implicitWidth: 32; icon: "caret-right"; text: ""
                                    onClicked: { if (pop.month === 11) { pop.month = 0; pop.year++ } else pop.month++ } }
                    }
                    MonthGrid {
                        id: grid
                        visible: d.hasDate
                        year: pop.year
                        month: pop.month
                        Layout.preferredWidth: 280
                        delegate: Rectangle {
                            required property var model
                            implicitWidth: 36; implicitHeight: 32; radius: 10
                            readonly property bool chosen: model.day === d.when.getDate() && model.month === d.when.getMonth()
                                                           && model.year === d.when.getFullYear()
                            color: chosen ? Theme.violet : (cellHover.hovered ? Theme.rowHover : "transparent")
                            opacity: model.month === pop.month ? 1 : 0.35
                            Text { anchors.centerIn: parent; text: model.day; color: Theme.ink; font.family: Theme.sans; font.pixelSize: 13 }
                            HoverHandler { id: cellHover }
                        }
                        onClicked: (date) => d.put(date.getFullYear(), date.getMonth(), date.getDate(), d.when.getHours(), d.when.getMinutes())
                    }
                    RowLayout {
                        visible: d.hasTime
                        spacing: 8
                        Layout.alignment: Qt.AlignHCenter
                        Repeater {
                            model: [{ unit: "h", max: 23 }, { unit: "m", max: 59 }]
                            delegate: Row {
                                required property var modelData
                                required property int index
                                spacing: 4
                                readonly property int now: index === 0 ? d.when.getHours() : d.when.getMinutes()
                                function step(by) {
                                    const v = (now + by + modelData.max + 1) % (modelData.max + 1)
                                    if (index === 0) d.put(d.when.getFullYear(), d.when.getMonth(), d.when.getDate(), v, d.when.getMinutes())
                                    else d.put(d.when.getFullYear(), d.when.getMonth(), d.when.getDate(), d.when.getHours(), v)
                                }
                                GemButton { kind: "ghost"; height: 32; implicitWidth: 32; icon: "minus"; text: ""; onClicked: parent.step(index === 0 ? -1 : -5) }
                                Text { width: 34; horizontalAlignment: Text.AlignHCenter; anchors.verticalCenter: parent.verticalCenter
                                       text: (parent.now < 10 ? "0" : "") + parent.now; color: Theme.ink
                                       font.family: Theme.sans; font.pixelSize: 17; font.weight: Font.DemiBold }
                                GemButton { kind: "ghost"; height: 32; implicitWidth: 32; icon: "plus"; text: ""; onClicked: parent.step(index === 0 ? 1 : 5) }
                            }
                        }
                    }
                }
            }
        }
    }
}
