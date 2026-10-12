import QtQuick
import QtQuick.Particles

// Slow twinkling motes drifting up: the air of the night room (GPU particles).
Item {
    id: root
    property real density: 1.0
    property color tint: "#E6DCFF"
    ParticleSystem { id: sky }
    ImageParticle {
        system: sky
        source: bridge.fxUrl("sparkle_lavender")
        color: root.tint
        colorVariation: 0.25
        alpha: 0.85
        alphaVariation: 0.4
        entryEffect: ImageParticle.Fade
        rotationVariation: 30
    }
    Emitter {
        system: sky
        anchors.fill: parent
        emitRate: 9 * root.density
        lifeSpan: 6000
        lifeSpanVariation: 2500
        size: 14
        sizeVariation: 10
        velocity: AngleDirection { angle: 270; angleVariation: 25; magnitude: 10; magnitudeVariation: 8 }
    }
}
