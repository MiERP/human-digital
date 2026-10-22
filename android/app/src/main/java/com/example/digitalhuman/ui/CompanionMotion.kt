package com.example.digitalhuman.ui

import com.example.digitalhuman.network.ConnectionState

internal data class CompanionMotion(
    val tiltDegrees: Float,
    val scale: Float,
    val talkLevel: Float,
    val opacity: Float,
)

/** Deterministic visual response to the live conversation, independent of frame timing. */
internal fun companionMotion(state: ConnectionState, amplitude: Float): CompanionMotion {
    val level = if (amplitude.isFinite()) amplitude.coerceIn(0f, 1f) else 0f
    return when (state) {
        ConnectionState.SLEEPING -> CompanionMotion(0f, 0.97f, 0f, 0.65f)
        ConnectionState.LISTENING -> CompanionMotion(-4f, 1.025f, 0f, 1f)
        ConnectionState.THINKING -> CompanionMotion(5f, 1f, 0f, 1f)
        ConnectionState.SPEAKING -> CompanionMotion(0f, 1f + level * 0.05f, level, 1f)
        else -> CompanionMotion(0f, 1f, 0f, 1f)
    }
}
