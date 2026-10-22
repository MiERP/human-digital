package com.example.digitalhuman.ui

import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.keyframes
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.size
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.drawscope.withTransform
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.res.imageResource
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.IntOffset
import androidx.compose.ui.unit.IntSize
import androidx.compose.ui.unit.dp
import com.example.digitalhuman.R
import com.example.digitalhuman.network.CompanionInfo
import com.example.digitalhuman.network.ConnectionState
import com.example.digitalhuman.network.RobotEmotion

/** Layered illustration: each arm, face, and light can respond to the conversation independently. */
@Composable
fun CompanionAvatar(
    state: ConnectionState,
    amplitude: Float,
    emotion: RobotEmotion = RobotEmotion(),
    companion: CompanionInfo = CompanionInfo(),
    modifier: Modifier = Modifier,
) {
    val body = ImageBitmap.imageResource(R.drawable.robo_body)
    val arms = ImageBitmap.imageResource(R.drawable.robo_arms)
    val loop = rememberInfiniteTransition(label = "companion_life")
    val phase by loop.animateFloat(
        initialValue = 0f,
        targetValue = 1f,
        animationSpec = infiniteRepeatable(tween(1400), RepeatMode.Reverse),
        label = "hover_and_gesture",
    )
    val blink by loop.animateFloat(
        initialValue = 1f,
        targetValue = 1f,
        animationSpec = infiniteRepeatable(keyframes {
            durationMillis = 3900
            1f at 0
            1f at 3450
            0.08f at 3570
            1f at 3700
        }),
        label = "eye_blink",
    )
    val lightBeat by loop.animateFloat(
        initialValue = 0.82f,
        targetValue = 1f,
        animationSpec = infiniteRepeatable(tween(1100), RepeatMode.Reverse),
        label = "light_breath",
    )
    val visual = companionVisualState(state, emotion, amplitude, phase)
    val motion = companionMotion(state, amplitude)
    val leftArm by animateFloatAsState(visual.leftArmDegrees, tween(180), label = "left_arm")
    val rightArm by animateFloatAsState(visual.rightArmDegrees, tween(180), label = "right_arm")
    val mouth by animateFloatAsState(visual.mouthOpen, tween(90), label = "mouth")
    val light by animateFloatAsState(visual.lightEnergy, tween(240), label = "lights")
    val opacity by animateFloatAsState(motion.opacity, tween(300), label = "body_opacity")
    val bob = companionBobOffset(state, amplitude, phase) * when (visual.expression) {
        AvatarExpression.SLEEPY -> 0.25f
        AvatarExpression.SAD, AvatarExpression.STRICT -> 0.6f
        else -> 1f
    }

    Box(
        modifier = modifier.size(280.dp).semantics {
            contentDescription = "${companion.name} đang ${stateLabel(state)}"
        },
        contentAlignment = Alignment.Center,
    ) {
        Canvas(modifier = Modifier.fillMaxSize().offset(y = bob.dp).graphicsLayer { alpha = opacity }) {
            val scale = size.width / body.width
            fun p(x: Float, y: Float) = Offset(x * scale, y * scale)
            fun drawArm(x: Int, width: Int, angle: Float, pivotX: Float) {
                withTransform({ rotate(angle, p(pivotX, 745f)) }) {
                    drawImage(
                        image = arms,
                        srcOffset = IntOffset(x, 680),
                        srcSize = IntSize(width, 390),
                        dstOffset = IntOffset((x * scale).toInt(), (680 * scale).toInt()),
                        dstSize = IntSize((width * scale).toInt(), (390 * scale).toInt()),
                    )
                }
            }
            drawArm(100, 340, leftArm, 350f)
            drawArm(825, 340, rightArm, 910f)
            drawImage(body, dstSize = IntSize(size.width.toInt(), size.height.toInt()))

            val color = expressionColor(visual.expression)
            drawRobotFace(scale, visual.expression, color, blink, mouth)
            drawRobotLights(scale, color, light * lightBeat)
        }
    }
}

private fun expressionColor(expression: AvatarExpression): Color = when (expression) {
    AvatarExpression.HAPPY -> Color(0xFFFFDA70)
    AvatarExpression.SAD -> Color(0xFF86C8F5)
    AvatarExpression.STRICT -> Color(0xFFFFA36B)
    AvatarExpression.THINKING -> Color(0xFFB8A7FF)
    AvatarExpression.SLEEPY -> Color(0xFF669AB9)
    AvatarExpression.NEUTRAL -> Color(0xFF1CF2EE)
}

private fun DrawScope.drawRobotLights(scale: Float, color: Color, energy: Float) {
    fun glow(x: Float, y: Float, radius: Float) {
        val center = Offset(x * scale, y * scale)
        drawCircle(
            brush = Brush.radialGradient(
                0f to color.copy(alpha = 0.38f * energy),
                0.4f to color.copy(alpha = 0.19f * energy),
                1f to Color.Transparent,
                center = center,
                radius = radius * scale,
            ),
            radius = radius * scale,
            center = center,
        )
    }
    glow(330f, 355f, 90f)
    glow(956f, 355f, 90f)
    glow(645f, 805f, 115f)
    drawCircle(color.copy(alpha = energy * 0.28f), 55f * scale, Offset(645f * scale, 805f * scale))
}

private fun DrawScope.drawRobotFace(
    scale: Float,
    expression: AvatarExpression,
    color: Color,
    blink: Float,
    mouth: Float,
) {
    fun p(x: Float, y: Float) = Offset(x * scale, y * scale)
    // Replace the printed features within the screen, retaining its bezel and glossy outer rim.
    drawRoundRect(
        brush = Brush.verticalGradient(
            listOf(Color(0xFF111319), Color(0xFF03070B)),
            startY = 255f * scale,
            endY = 505f * scale,
        ),
        topLeft = p(433f, 246f),
        size = Size(427f * scale, 256f * scale),
        cornerRadius = CornerRadius(68f * scale),
    )
    val eyeY = if (expression == AvatarExpression.THINKING) 322f else 335f
    val eyeHeight = when (expression) {
        AvatarExpression.SLEEPY -> 0f
        AvatarExpression.STRICT -> 12f * blink
        AvatarExpression.SAD -> 24f * blink
        AvatarExpression.HAPPY -> 38f * blink
        else -> 35f * blink
    }
    for (x in listOf(535f, 755f)) {
        if (expression == AvatarExpression.SLEEPY || blink < 0.16f) {
            drawArc(
                color,
                startAngle = 20f,
                sweepAngle = 140f,
                useCenter = false,
                topLeft = p(x - 34f, eyeY - 10f),
                size = Size(68f * scale, 30f * scale),
                style = Stroke(width = 7f * scale),
            )
        } else {
            drawOval(
                color.copy(alpha = 0.22f),
                topLeft = p(x - 46f, eyeY - eyeHeight - 10f),
                size = Size(92f * scale, (eyeHeight * 2f + 20f) * scale),
            )
            drawOval(
                color,
                topLeft = p(x - 32f, eyeY - eyeHeight),
                size = Size(64f * scale, eyeHeight * 2f * scale),
            )
        }
    }
    if (expression == AvatarExpression.STRICT) {
        drawLine(color, p(493f, 290f), p(560f, 310f), 6f * scale)
        drawLine(color, p(730f, 310f), p(797f, 290f), 6f * scale)
    }
    when {
        expression == AvatarExpression.SLEEPY -> drawLine(color.copy(alpha = 0.45f), p(620f, 435f), p(670f, 435f), 5f * scale)
        mouth > 0.1f -> drawOval(
            color,
            topLeft = p(625f - mouth * 8f, 421f - mouth * 5f),
            size = Size((40f + mouth * 16f) * scale, (12f + mouth * 46f) * scale),
        )
        expression == AvatarExpression.SAD -> drawArc(
            color, 205f, 130f, false,
            p(601f, 425f), Size(88f * scale, 47f * scale), style = Stroke(width = 7f * scale),
        )
        expression == AvatarExpression.STRICT -> drawLine(color, p(614f, 445f), p(676f, 445f), 7f * scale)
        expression == AvatarExpression.THINKING -> drawCircle(color, 10f * scale, p(645f, 440f))
        else -> drawArc(
            color, 12f, 156f, false,
            p(598f, 399f), Size(94f * scale, 65f * scale), style = Stroke(width = 8f * scale),
        )
    }
}

private fun stateLabel(state: ConnectionState): String = when (state) {
    ConnectionState.LISTENING -> "lắng nghe"
    ConnectionState.THINKING -> "suy nghĩ"
    ConnectionState.SPEAKING -> "nói chuyện"
    ConnectionState.SLEEPING -> "ngủ"
    else -> "ở đây"
}
