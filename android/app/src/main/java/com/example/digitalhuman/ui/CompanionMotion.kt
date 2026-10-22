package com.example.digitalhuman.ui

import com.example.digitalhuman.network.ConnectionState
import com.example.digitalhuman.network.RobotEmotion

internal enum class AvatarExpression { NEUTRAL, HAPPY, SAD, STRICT, THINKING, SLEEPY }

internal data class AvatarVisualState(
    val expression: AvatarExpression,
    val lightEnergy: Float,
    val mouthOpen: Float,
    val leftArmDegrees: Float,
    val rightArmDegrees: Float,
)

/** The live voice and emotion signals become bounded, predictable visual targets. */
internal fun companionVisualState(
    state: ConnectionState,
    emotion: RobotEmotion,
    amplitude: Float,
    gesturePhase: Float,
): AvatarVisualState {
    val level = if (amplitude.isFinite()) amplitude.coerceIn(0f, 1f) else 0f
    val phase = if (gesturePhase.isFinite()) gesturePhase.coerceIn(0f, 1f) else 0f
    val expression = when {
        state == ConnectionState.SLEEPING -> AvatarExpression.SLEEPY
        emotion.energy == "sleepy" || emotion.energy == "drowsy" || emotion.energy == "tired" -> AvatarExpression.SLEEPY
        emotion.emotion == "happy" || emotion.emotion == "excited" || emotion.emotion == "proud" || emotion.emotion == "surprised" -> AvatarExpression.HAPPY
        emotion.emotion == "sad" -> AvatarExpression.SAD
        emotion.emotion == "strict" || emotion.emotion == "displeased" || emotion.emotion == "angry" -> AvatarExpression.STRICT
        state == ConnectionState.THINKING -> AvatarExpression.THINKING
        else -> AvatarExpression.NEUTRAL
    }
    if (state == ConnectionState.SLEEPING) {
        return AvatarVisualState(expression, 0.12f, 0f, 0f, 0f)
    }
    val speaking = state == ConnectionState.SPEAKING
    val emotionBoost = when (expression) {
        AvatarExpression.HAPPY -> 0.15f
        AvatarExpression.SAD, AvatarExpression.SLEEPY -> -0.18f
        AvatarExpression.STRICT -> 0.05f
        else -> 0f
    }
    val light = (0.43f + emotionBoost + if (speaking) 0.15f + level * 0.27f else 0f).coerceIn(0.12f, 0.95f)
    val gesture = if (speaking) 5f + level * 7f else 0f
    return AvatarVisualState(
        expression = expression,
        lightEnergy = light,
        mouthOpen = if (speaking) (0.12f + level * 0.88f) else 0f,
        leftArmDegrees = gesture * (0.3f + phase * 0.7f),
        rightArmDegrees = -gesture * (1f - phase * 0.7f),
    )
}

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

/** Vertical offset in dp for a calm idle hover, with a slightly stronger response while speaking. */
internal fun companionBobOffset(state: ConnectionState, amplitude: Float, phase: Float): Float {
    if (state == ConnectionState.SLEEPING) return 0f

    val level = if (amplitude.isFinite()) amplitude.coerceIn(0f, 1f) else 0f
    val progress = if (phase.isFinite()) phase.coerceIn(0f, 1f) else 0f
    val distance = if (state == ConnectionState.SPEAKING) 7f + level * 3f else 7f
    return (progress * 2f - 1f) * distance
}
