import QtQuick
import Petoken
import "mirror"

// A window of the app that is not a dialog (the usage panel), in Petoken's glass: no title bar of
// its own (its page has one), its contents drawn by the mirror at their own size (never scaled:
// scaled words blur). wantHeight tells the window how tall that needs it to be.
Item {
    id: app
    readonly property real wantHeight: page.implicitHeight + 2 * shell.margin
    readonly property real wantWidth: page.implicitWidth + 2 * shell.margin
    Component.onCompleted: { Theme.dark = false; shell.appear() }
    WindowShell {
        id: shell
        anchors.fill: parent
        bare: true
        content: Item {
            anchors.fill: parent
            MirrorNode {
                id: page
                anchors.fill: parent
                node: mirror.tree
                m: mirror
            }
        }
    }
}
