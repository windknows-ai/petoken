pragma Singleton
import QtQuick

// One look for every Petoken window, in two moods. Each window has its own engine, so its own
// Theme: the wardrobe keeps the night (dark: true, the default); the work windows (workbench,
// Settings, dialogs, the usage panel, the cards beside her) set dark: false for calm paper that
// is easy to read for hours.
QtObject {
    property bool dark: true
    readonly property bool light: !dark

    // Colours of the night (the wardrobe, the shows)
    readonly property color night: "#0E0B26"
    readonly property color nightDeep: "#080616"
    readonly property color nightHigh: "#231A4F"
    readonly property color silver: "#DDE3FF"
    readonly property color ice: dark ? "#8EC8FF" : "#2F6DB5"
    readonly property color good: dark ? "#7BE0B0" : "#2E8A5E"

    // Words
    readonly property color ink: dark ? "#F1EEFF" : "#25213F"
    readonly property color inkSoft: dark ? "#C9C2EC" : "#4B4668"
    readonly property color muted: dark ? "#9289C4" : "#76708F"
    readonly property color gold: dark ? "#F3C96B" : "#A86F12"
    readonly property color goldDeep: "#C88A2E"
    readonly property color violet: dark ? "#9C7BFF" : "#6655C8"
    readonly property color violetSoft: dark ? "#B9A6FF" : "#5A4BB4"
    readonly property color danger: dark ? "#FF8FAB" : "#B23A5C"

    // Surfaces
    readonly property color windowTop: dark ? "#16113A" : "#FBFAFE"
    readonly property color windowBottom: dark ? "#1D1246" : "#F2F0F9"
    readonly property color windowEdge: dark ? "#4A3E8C" : "#D9D4EA"
    readonly property color card: dark ? "#3A221A5C" : "#FFFFFF"
    readonly property color cardEdge: dark ? "#33E8DEFF" : "#E2DDF0"
    readonly property color field: dark ? "#1E1850" : "#F5F3FB"
    readonly property color fieldFocus: dark ? "#2A2268" : "#FFFFFF"
    readonly property color fieldEdge: dark ? "#33E8DEFF" : "#D6D0E8"
    readonly property color rowHover: dark ? "#2A2270" : "#F0EDF9"
    readonly property color rowSelected: dark ? "#46389E" : "#E6E0F9"
    readonly property color rowSelectedEdge: dark ? "#9C8BFF" : "#B3A6EC"
    readonly property color popup: dark ? "#F6181240" : "#FFFFFF"
    readonly property color track: dark ? "#2A2266" : "#E4E0F0"
    readonly property color chosenTop: dark ? "#6A52D6" : "#7464D8"
    readonly property color chosenBottom: dark ? "#4636A6" : "#6050C4"
    readonly property color chosenEdge: dark ? "#B9A8FF" : "#5A4BB4"
    readonly property color chosenInk: dark ? ink : "#FFFFFF"
    readonly property color glass: "#1AFFFFFF"
    readonly property color glassEdge: dark ? "#33E8DEFF" : "#D6D0E8"
    readonly property color line: dark ? "#3A2F72" : "#E4E0F0"
    readonly property real shadow: dark ? 0.55 : 0.18

    // A colour chosen for the old light windows, kept readable on this mood's surface.
    function readable(c) {
        const k = Qt.color(c)
        if (dark)
            return k.hslLightness >= 0.62 ? k : Qt.hsla(k.hslHue, Math.min(0.85, k.hslSaturation), 0.72, 1)
        return k.hslLightness <= 0.45 ? k : Qt.hsla(k.hslHue, Math.min(0.8, k.hslSaturation), 0.38, 1)
    }

    function rarity(name) {
        return ({ fanxing: "#5C82FF", mingyue: "#F4F6FF", haori: "#F6BE48",
                  yinhe: "#A9B9F0", xinghai: "#D6A6FF" })[name] || silver
    }

    // Type: Microsoft YaHei UI is hinted for the screen (crisp at small sizes); Noto Serif SC
    // (bundled) for titles in the night.
    readonly property string sans: "Microsoft YaHei UI"
    readonly property string serif: dark ? "Noto Serif SC" : "Microsoft YaHei UI"

    // Shape and motion
    readonly property int radius: 22                       // Panels and cards: soft, app-like corners.
    readonly property int windowRadius: 30
    readonly property int quick: 160
    readonly property int smooth: 320
    readonly property int slow: 620
}
