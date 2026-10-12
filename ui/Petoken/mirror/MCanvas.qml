import QtQuick
import Petoken

// A widget that draws itself (charts, portraits, badges): its own picture, with the pointer passed on.
Item {
    id: c
    property var node: ({})
    property var m: null
    property var val: ({})
    implicitWidth: val.hw > 0 ? val.hw : (val.w || 100)
    implicitHeight: val.hh > 0 ? val.hh : (val.h || 80)
    onWidthChanged: sizer.restart()
    onHeightChanged: sizer.restart()
    Timer { id: sizer; interval: 60; onTriggered: if (c.m && c.width > 0 && c.height > 0)
                                                     c.m.resizeTo(c.node.id, Math.round(c.width), Math.round(c.height)) }
    Image {
        anchors.fill: parent
        source: c.val.img || ""
        fillMode: Image.PreserveAspectFit                // Never squeezed out of shape.
        smooth: true
        cache: false
    }
    MouseArea {
        anchors.fill: parent
        hoverEnabled: true
        onPressed: (e) => c.m.canvasMouse(c.node.id, "press", e.x, e.y)
        onReleased: (e) => c.m.canvasMouse(c.node.id, "release", e.x, e.y)
        onDoubleClicked: (e) => c.m.canvasMouse(c.node.id, "double", e.x, e.y)
        onPositionChanged: (e) => c.m.canvasMouse(c.node.id, "move", e.x, e.y)
        onWheel: (e) => c.m.canvasMouse(c.node.id, e.angleDelta.y > 0 ? "wheel+" : "wheel-", e.x, e.y)
    }
    Tip { text: c.val.tip || "" }
}
