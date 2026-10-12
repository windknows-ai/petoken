import QtQuick
import QtQuick.Effects
import QtQuick.Layouts
import Petoken

// The shop: today's four featured pieces (with the discount card draw) and the wishing banner.
Page {
    ColumnLayout {
        anchors.fill: parent
        anchors.topMargin: 8
        spacing: 14

        Text { text: bridge.tr("shop_featured"); color: Theme.ink; font.family: Theme.serif; font.pixelSize: 17; font.weight: Font.Bold }
        Row {
            spacing: 16
            Repeater {
                model: bridge.featured
                delegate: GlassPanel {
                    width: 168; height: 250
                    Dome {
                        anchors { horizontalCenter: parent.horizontalCenter; top: parent.top; topMargin: 10 }
                        width: 128; height: 158
                        item: modelData
                        order: index
                        chosen: false
                        onPicked: bridge.tryOn(modelData.id)
                    }
                    Text {
                        visible: modelData.priceText !== ""
                        anchors { horizontalCenter: parent.horizontalCenter; bottom: buy.top; bottomMargin: 8 }
                        text: modelData.priceText
                        textFormat: Text.RichText
                        color: Theme.gold
                        font.family: Theme.sans; font.pixelSize: 13; font.weight: Font.DemiBold
                    }
                    GemButton {
                        id: buy
                        anchors { horizontalCenter: parent.horizontalCenter; bottom: parent.bottom; bottomMargin: 14 }
                        implicitWidth: 140
                        height: 36
                        kind: modelData.mode === "draw" ? "gold" : (modelData.mode === "owned" ? "ghost" : "violet")
                        icon: modelData.mode === "draw" ? "cards" : (modelData.mode === "owned" ? "check" : "shopping-bag")
                        text: modelData.buttonText
                        enabled: modelData.enabled
                        onClicked: modelData.mode === "draw" ? bridge.drawDiscount(modelData.id) : bridge.buyFeatured(modelData.id)
                    }
                }
            }
        }

        Text { text: bridge.tr("shop_wish"); color: Theme.ink; font.family: Theme.serif; font.pixelSize: 17; font.weight: Font.Bold }
        Item {                                           // The wishing banner.
            Layout.fillWidth: true
            Layout.preferredHeight: 210
            Rectangle {
                id: bannerShape
                anchors.fill: parent
                radius: Theme.radius
                clip: true
                gradient: Gradient {
                    orientation: Gradient.Horizontal
                    GradientStop { position: 0; color: "#24185C" }
                    GradientStop { position: 1; color: "#120C34" }
                }
                border.color: "#5A4BA8"
                Image {
                    anchors.fill: parent
                    source: bridge.fxUrl("sky_far")
                    fillMode: Image.PreserveAspectCrop
                    opacity: 0.55
                }
                StarField { anchors.fill: parent; density: 1.4 }
                Image {                                  // The Starsea star turning on the banner.
                    id: star
                    anchors { right: parent.right; rightMargin: 40; verticalCenter: parent.verticalCenter }
                    width: 190; height: 190
                    source: bridge.fxUrl("hero_xinghai")
                    RotationAnimation on rotation { from: 0; to: 360; duration: 26000; loops: Animation.Infinite }
                    layer.enabled: true
                    layer.effect: MultiEffect { brightness: 0.05 }
                }
                Column {
                    anchors { left: parent.left; leftMargin: 28; verticalCenter: parent.verticalCenter }
                    spacing: 14
                    Text { text: bridge.tr("wardrobe_wish_title"); color: Theme.ink; font.family: Theme.serif; font.pixelSize: 26; font.weight: Font.Black
                           style: Text.Raised; styleColor: "#80080616" }
                    Text { text: bridge.pityText; color: Theme.inkSoft; font.family: Theme.sans; font.pixelSize: 13 }
                    Row {
                        spacing: 12
                        GemButton { height: 44; fontSize: 15; icon: "sparkle"; text: bridge.wishOneText; enabled: bridge.canWishOne; onClicked: bridge.wish(1) }
                        GemButton { height: 44; fontSize: 15; kind: "gold"; icon: "shooting-star"; text: bridge.wishTenText; enabled: bridge.canWishTen; onClicked: bridge.wish(10) }
                    }
                }
            }
        }
        Item { Layout.fillHeight: true }
    }
}
