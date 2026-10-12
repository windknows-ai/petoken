import QtQuick
import Petoken

// A check box as a sliding gem toggle; a radio button as a round gem. The words beside it are its own.
Item {
    id: c
    property var node: ({})
    property var m: null
    property var val: ({})
    readonly property bool radio: node.t === "radio"
    readonly property bool on: !!val.checked
    readonly property bool usable: val.en !== false
    implicitWidth: track.width + (words.text ? words.implicitWidth + 12 : 0)
    implicitHeight: Math.max(30, words.implicitHeight)
    opacity: usable ? 1 : 0.45

    Image {                                              // Codex's gem switch, when there is one.
        id: switchArt
        visible: Theme.dark && !c.radio && source != ""
        anchors.verticalCenter: parent.verticalCenter
        width: 54; height: 29
        source: c.radio ? "" : bridge.artUrl(c.on ? "toggle_on" : "toggle_off")
        sourceSize: Qt.size(120, 64)
        smooth: true
    }
    Rectangle {                                          // The track (toggle) or the ring (radio).
        id: track
        opacity: switchArt.visible ? 0 : 1
        anchors.verticalCenter: parent.verticalCenter
        width: c.radio ? 22 : (switchArt.visible ? 54 : 46)
        height: c.radio ? 22 : 26
        radius: height / 2
        gradient: Gradient {
            GradientStop { position: 0; color: c.on ? (Theme.dark ? "#A98BFF" : "#8676E4") : Theme.track }
            GradientStop { position: 1; color: c.on ? (Theme.dark ? "#5B78F0" : "#6655C8") : (Theme.dark ? "#1C1748" : "#D8D3E8") }
        }
        border.color: c.on ? (Theme.dark ? "#D9CCFF" : "#5A4BB4") : Theme.fieldEdge
        Behavior on border.color { ColorAnimation { duration: Theme.quick } }
        Rectangle {
            visible: !c.radio
            width: 20; height: 20; radius: 10
            anchors.verticalCenter: parent.verticalCenter
            x: c.on ? parent.width - width - 3 : 3
            color: "#FFFFFF"
            Behavior on x { NumberAnimation { duration: Theme.smooth; easing.type: Easing.OutBack } }
        }
        Rectangle {
            visible: c.radio && c.on
            anchors.centerIn: parent
            width: 9; height: 9; radius: 4.5
            color: "#FFFFFF"
        }
    }
    Text {
        id: words
        anchors { left: track.right; leftMargin: 12; verticalCenter: parent.verticalCenter }
        width: Math.max(0, c.width - track.width - 12)
        text: c.val.text || ""
        color: Theme.ink
        wrapMode: Text.Wrap
        font.family: Theme.sans
        font.pixelSize: 14
    }
    MouseArea {
        anchors.fill: parent
        enabled: c.usable
        cursorShape: Qt.PointingHandCursor
        onClicked: c.m.click(c.node.id)
    }
    Tip { text: c.val.tip || "" }
}
