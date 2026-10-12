import QtQuick
import QtQuick.Effects
import QtQuick.Layouts
import Petoken

// The shop: today's four featured pieces (with the discount card draw) and the wishing banner.
Page {
    ColumnLayout {
        anchors.fill: parent
        anchors.topMargin: 8
        spacing: 16

        SectionTitle { key: "shop_featured" }
        Row {
            id: cards
            spacing: 18
            readonly property real cardWidth: Math.min(200, (parent.width - 3 * spacing) / 4)
            Repeater {
                model: bridge.featured
                delegate: GlassPanel {
                    width: cards.cardWidth; height: 300
                    Dome {
                        id: dome
                        anchors { horizontalCenter: parent.horizontalCenter; top: parent.top; topMargin: 14 }
                        width: Math.min(132, parent.width - 36); height: width * 1.23
                        item: modelData
                        order: index
                        chosen: false
                        onPicked: bridge.tryOn(modelData.id)
                    }
                    Rectangle {                          // Today's discount, once drawn.
                        visible: modelData.offText !== ""
                        anchors { left: parent.left; top: parent.top; margins: 12 }
                        height: 26; width: offLabel.implicitWidth + 22; radius: 13
                        gradient: Gradient {
                            GradientStop { position: 0; color: "#FFE7AA" }
                            GradientStop { position: 1; color: "#D9922F" }
                        }
                        Text { id: offLabel; anchors.centerIn: parent; text: modelData.offText; color: "#2B1806"
                               font.family: Theme.sans; font.pixelSize: 13; font.weight: Font.Bold }
                    }
                    Text {
                        id: cardName
                        anchors { horizontalCenter: parent.horizontalCenter; top: dome.bottom; topMargin: 10 }
                        width: parent.width - 24
                        horizontalAlignment: Text.AlignHCenter
                        elide: Text.ElideRight
                        text: modelData.name
                        color: Theme.ink
                        font.family: Theme.sans; font.pixelSize: 15; font.weight: Font.DemiBold
                    }
                    Text {
                        anchors { horizontalCenter: parent.horizontalCenter; top: cardName.bottom; topMargin: 4 }
                        text: modelData.priceText !== "" ? modelData.priceText : " "
                        textFormat: Text.RichText
                        color: Theme.gold
                        font.family: Theme.sans; font.pixelSize: 14; font.weight: Font.DemiBold
                    }
                    GemButton {
                        id: buy
                        anchors { horizontalCenter: parent.horizontalCenter; bottom: parent.bottom; bottomMargin: 16 }
                        implicitWidth: parent.width - 36
                        height: 40
                        kind: modelData.mode === "draw" ? "gold" : (modelData.mode === "owned" ? "ghost" : "violet")
                        icon: modelData.mode === "draw" ? "cards" : (modelData.mode === "owned" ? "check" : "shopping-bag")
                        text: modelData.buttonText
                        enabled: modelData.enabled
                        onClicked: modelData.mode === "draw" ? bridge.drawDiscount(modelData.id) : bridge.buyFeatured(modelData.id)
                    }
                }
            }
        }

        SectionTitle { key: "shop_wish" }
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
                    Text { text: bridge.pityText; color: Theme.inkSoft; font.family: Theme.sans; font.pixelSize: 14 }
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
