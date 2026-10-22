package com.example.digitalhuman.ui

import com.example.digitalhuman.network.ConnectionState

internal data class CompanionMotion(
    val leftArmDegrees: Float,
    val rightArmDegrees: Float,
    val gazeX: Float,
    val gazeY: Float,
    val eyeOpen: Float,
    val talkLevel: Float,
    val opacity: Float,
    val leftElbowDegrees: Float = 0f,
    val rightElbowDegrees: Float = 0f,
)

/** Deterministic visual response to the live conversation, independent of frame timing. */
internal fun companionMotion(state: ConnectionState, amplitude: Float, gesturePhase: Float = 0f): CompanionMotion {
    val level = if (amplitude.isFinite()) amplitude.coerceIn(0f, 1f) else 0f
    val phase = if (gesturePhase.isFinite()) gesturePhase.coerceIn(0f, 1f) else 0f
    return when (state) {
        ConnectionState.SLEEPING -> CompanionMotion(0f, 0f, 0f, 0f, 0f, 0f, 0.7f)
        ConnectionState.LISTENING -> CompanionMotion(3f, -3f, -3f, 0f, 1f, 0f, 1f)
        ConnectionState.THINKING -> CompanionMotion(0f, -3f, 2f, -3f, 1f, 0f, 1f)
        ConnectionState.SPEAKING -> {
            val restingAngle = 0.5f + level * 0.5f
            val liftRange = if (level > 0.005f) 1.5f + level * 1.5f else 0.5f
            val bendRange = if (level > 0.005f) 5f + level * 5f else 0f
            val smoothPhase = phase * phase * (3f - 2f * phase)
            CompanionMotion(
                restingAngle + smoothPhase * liftRange,
                -restingAngle - (1f - smoothPhase) * liftRange,
                0f, 0f, 1f, level, 1f,
                // The sprite already has a slight elbow bend, so a small extra rotation gives ~140–150° inside.
                leftElbowDegrees = -18f - smoothPhase * bendRange,
                rightElbowDegrees = 18f + (1f - smoothPhase) * bendRange,
            )
        }
        else -> CompanionMotion(0f, 0f, 0f, 0f, 1f, 0f, 1f)
    }
}
