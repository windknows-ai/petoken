import QtQuick
import Petoken

// A page that slides and fades in when shown.
Item {
    id: root
    property bool shown: false
    visible: opacity > 0.01
    opacity: shown ? 1 : 0
    transform: Translate { y: root.shown ? 0 : 14; Behavior on y { NumberAnimation { duration: Theme.smooth; easing.type: Easing.OutCubic } } }
    Behavior on opacity { NumberAnimation { duration: Theme.smooth; easing.type: Easing.OutCubic } }
}
