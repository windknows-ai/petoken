pragma Singleton
import QtQuick

// One look for every Petoken window: night sky, silver and champagne gold, star light.
QtObject {
    // Colours
    readonly property color night: "#0E0B26"
    readonly property color nightDeep: "#080616"
    readonly property color nightHigh: "#231A4F"
    readonly property color ink: "#F1EEFF"
    readonly property color inkSoft: "#C9C2EC"
    readonly property color muted: "#9289C4"
    readonly property color gold: "#F3C96B"
    readonly property color goldDeep: "#C88A2E"
    readonly property color silver: "#DDE3FF"
    readonly property color violet: "#9C7BFF"
    readonly property color ice: "#8EC8FF"
    readonly property color line: "#3A2F72"
    readonly property color glass: "#1AFFFFFF"
    readonly property color glassEdge: "#33E8DEFF"
    readonly property color good: "#7BE0B0"

    function rarity(name) {
        return ({ fanxing: "#5C82FF", mingyue: "#F4F6FF", haori: "#F6BE48",
                  yinhe: "#A9B9F0", xinghai: "#D6A6FF" })[name] || silver
    }

    // Type
    readonly property string sans: "Noto Sans SC"
    readonly property string serif: "Noto Serif SC"

    // Shape and motion
    readonly property int radius: 22                       // Panels and cards: soft, app-like corners.
    readonly property int windowRadius: 30
    readonly property int quick: 160
    readonly property int smooth: 320
    readonly property int slow: 620
}
