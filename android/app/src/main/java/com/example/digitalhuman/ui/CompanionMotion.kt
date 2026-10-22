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
)

/** Deterministic visual response to the live conversation, independent of frame timing. */
internal fun companionMotion(state: ConnectionState, amplitude: Float, gesturePhase: Float = 0f): CompanionMotion {
    val level = if (amplitude.isFinite()) amplitude.coerceIn(0f, 1f) else 0f
    val phase = if (gesturePhase.isFinite()) gesturePhase.coerceIn(0f, 1f) else 0f
    return when (state) {
        ConnectionState.SLEEPING -> CompanionMotion(0f, 0f, 0f, 0f, 0f, 0f, 0.7f)
        ConnectionState.LISTENING -> CompanionMotion(8f, -8f, -3f, 0f, 1f, 0f, 1f)
        ConnectionState.THINKING -> CompanionMotion(0f, -16f, 2f, -3f, 1f, 0f, 1f)
        ConnectionState.SPEAKING -> {
            val restingAngle = 8f + level * 4f
            val liftRange = if (level > 0.005f) 98f + level * 10f else 35f
            CompanionMotion(
                restingAngle + phase * liftRange,
                -restingAngle - (1f - phase) * liftRange,
                0f, 0f, 1f, level, 1f,
            )
        }
        else -> CompanionMotion(0f, 0f, 0f, 0f, 1f, 0f, 1f)
    }
}
