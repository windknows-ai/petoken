import QtQuick
import Petoken
import "mirror"

// A window of the app that is not a dialog (the usage panel), in Petoken's glass: no title bar of
// its own (its page has one), its contents drawn by the mirror, gently scaled down if they run long.
Item {
    id: app
    Component.onCompleted: shell.appear()
    WindowShell {
        id: shell
        anchors.fill: parent
        bare: true
        content: Item {
            id: area
            anchors.fill: parent
            readonly property real fit: page.implicitHeight > 0 ? Math.min(1, height / page.implicitHeight) : 1
            MirrorNode {
                id: page
                width: area.width / area.fit
                height: Math.max(implicitHeight, area.height / area.fit)
                scale: area.fit
                transformOrigin: Item.TopLeft
                node: mirror.tree
                m: mirror
            }
        }
    }
}
