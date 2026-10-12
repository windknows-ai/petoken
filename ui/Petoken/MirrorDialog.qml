import QtQuick
import Petoken
import "mirror"

// Any dialog of the app, in Petoken's own window: its title, its contents drawn by the mirror.
Item {
    id: app
    // How tall the window wants to be for all of the dialog to show (read by widget_mirror).
    readonly property real wantHeight: page.implicitHeight + (shell.compact ? 56 : 64) + 20 + 2 * shell.margin + 8
    onWantHeightChanged: bridge.fit(wantHeight)
    // ...and wide enough for its widest row (fields are never squeezed below a usable width).
    readonly property real wantWidth: page.implicitWidth + 48 + 2 * shell.margin
    onWantWidthChanged: bridge.fitWidth(wantWidth)
    Component.onCompleted: { Theme.dark = false; shell.appear() }

    WindowShell {
        id: shell
        anchors.fill: parent
        title: bridge.title
        compact: true
        onCloseRequested: bridge.close()
        content: Item {
            id: area
            anchors.fill: parent
            anchors.leftMargin: 24
            anchors.rightMargin: 24
            anchors.bottomMargin: 20
            onWidthChanged: sizer.restart()
            onHeightChanged: sizer.restart()
            Timer { id: sizer; interval: 30
                    onTriggered: mirror.resizeTo("", Math.round(area.width), Math.round(area.height)) }
            Flickable {
                id: flick
                anchors.fill: parent
                clip: contentHeight > height
                contentWidth: width
                contentHeight: Math.max(height, page.implicitHeight)
                boundsBehavior: Flickable.StopAtBounds
                MirrorNode {
                    id: page
                    width: flick.width
                    height: Math.max(flick.height, implicitHeight)
                    node: mirror.tree
                    m: mirror
                }
            }
        }
    }
}
