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
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.drawscope.clipPath
import androidx.compose.ui.graphics.drawscope.withTransform
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

/** Robo is drawn in layers: stable shell, independently moving arms and screen face. */
@Composable
fun CompanionAvatar(
    state: ConnectionState,
    amplitude: Float,
    emotion: RobotEmotion = RobotEmotion(),
    companion: CompanionInfo = CompanionInfo(),
    modifier: Modifier = Modifier,
) {
    val sprite = ImageBitmap.imageResource(R.drawable.robo_avatar)
    val loop = rememberInfiniteTransition(label = "robo_face")
    val blink by loop.animateFloat(
        initialValue = 1f,
        targetValue = 1f,
        animationSpec = infiniteRepeatable(keyframes {
            durationMillis = 3700
            1f at 0
            1f at 3300
            0.08f at 3410
            1f at 3540
        }),
        label = "blink",
    )
    val gesture by loop.animateFloat(
        initialValue = 0f,
        targetValue = 1f,
        animationSpec = infiniteRepeatable(tween(650), RepeatMode.Reverse),
        label = "hand_gesture",
    )
    val pose = companionMotion(state, amplitude, gesture)
    val leftArm by animateFloatAsState(pose.leftArmDegrees, tween(90), label = "left_arm")
    val rightArm by animateFloatAsState(pose.rightArmDegrees, tween(90), label = "right_arm")
    val gazeX by animateFloatAsState(pose.gazeX, tween(220), label = "gaze_x")
    val gazeY by animateFloatAsState(pose.gazeY, tween(220), label = "gaze_y")
    val eyeOpen by animateFloatAsState(pose.eyeOpen, tween(120), label = "eye_open")
    val mouth by animateFloatAsState(pose.talkLevel, tween(75), label = "mouth")
    val opacity by animateFloatAsState(pose.opacity, tween(300), label = "robo_opacity")

    Box(modifier = modifier.size(280.dp), contentAlignment = Alignment.Center) {
        Canvas(
            modifier = Modifier.fillMaxSize().semantics {
                contentDescription = "${companion.name} đang ${stateLabel(state)}"
            },
        ) {
            val imageScale = size.height / sprite.height
            val imageLeft = (size.width - sprite.width * imageScale) / 2f
            fun point(x: Float, y: Float) = Offset(imageLeft + x * imageScale, y * imageScale)
            fun region(x: Int, y: Int, width: Int, height: Int) {
                drawImage(
                    image = sprite,
                    srcOffset = IntOffset(x, y),
                    srcSize = IntSize(width, height),
                    dstOffset = IntOffset(point(x.toFloat(), y.toFloat()).x.toInt(), point(x.toFloat(), y.toFloat()).y.toInt()),
                    dstSize = IntSize((width * imageScale).toInt(), (height * imageScale).toInt()),
                    alpha = opacity,
                )
            }

            // Draw the moving arms behind the fixed head and torso.
            fun armOutline(vararg corners: Pair<Float, Float>) = Path().apply {
                corners.forEachIndexed { index, (x, y) ->
                    val corner = point(x, y)
                    if (index == 0) moveTo(corner.x, corner.y) else lineTo(corner.x, corner.y)
                }
                close()
            }
            val leftArmOutline = armOutline(
                0f to 765f, 305f to 765f, 305f to 955f,
                240f to 1030f, 245f to 1370f, 0f to 1370f,
            )
            val rightArmOutline = armOutline(
                800f to 765f, 1105f to 765f, 1105f to 1370f,
                860f to 1370f, 865f to 1030f, 800f to 955f,
            )
            withTransform({ rotate(leftArm, point(310f, 805f)) }) {
                clipPath(leftArmOutline) { region(0, 765, 340, 600) }
            }
            withTransform({ rotate(rightArm, point(795f, 805f)) }) {
                clipPath(rightArmOutline) { region(765, 765, 340, 600) }
            }
            region(290, 755, 525, 530)
            region(0, 0, sprite.width, 770)

            drawRobotFace(::point, imageScale, eyeOpen * blink, gazeX, gazeY, mouth, state, emotion)
        }
    }
}

private fun DrawScope.drawRobotFace(
    point: (Float, Float) -> Offset,
    scale: Float,
    eyeOpen: Float,
    gazeX: Float,
    gazeY: Float,
    mouth: Float,
    state: ConnectionState,
    emotion: RobotEmotion,
) {
    val cyan = when (emotion.emotion) {
        "excited", "surprised", "proud" -> Color(0xFFFFD76A)
        "sad" -> Color(0xFF91C9E8)
        "strict", "displeased" -> Color(0xFFFFA96B)
        else -> Color(0xFF20F3F5)
    }
    // Repaint only the dark display interior so the printed eyes do not remain visible.
    drawRoundRect(
        brush = Brush.verticalGradient(listOf(Color(0xFF34393D), Color(0xFF171B1E))),
        topLeft = point(355f, 415f),
        size = Size(395f * scale, 246f * scale),
        cornerRadius = CornerRadius(38f * scale),
    )
    for (eyeX in listOf(445f, 662f)) {
        val center = point(eyeX + gazeX, 516f + gazeY)
        if (eyeOpen < 0.16f) {
            drawLine(cyan, center.copy(x = center.x - 29f * scale), center.copy(x = center.x + 29f * scale), 6f * scale)
        } else {
            drawOval(
                cyan.copy(alpha = 0.20f),
                topLeft = Offset(center.x - 44f * scale, center.y - 44f * eyeOpen * scale),
                size = Size(88f * scale, 88f * eyeOpen * scale),
            )
            drawOval(
                cyan,
                topLeft = Offset(center.x - 31f * scale, center.y - 31f * eyeOpen * scale),
                size = Size(62f * scale, 62f * eyeOpen * scale),
            )
        }
    }
    if (state == ConnectionState.SPEAKING && mouth > 0.04f) {
        drawRoundRect(
            color = cyan,
            topLeft = point(529f, 604f - mouth * 12f),
            size = Size(52f * scale, (5f + mouth * 29f) * scale),
            cornerRadius = CornerRadius(17f * scale),
        )
    } else if (state != ConnectionState.SLEEPING) {
        drawArc(
            color = cyan.copy(alpha = 0.8f),
            startAngle = 20f,
            sweepAngle = 140f,
            useCenter = false,
            topLeft = point(522f, 586f),
            size = Size(66f * scale, 37f * scale),
            style = Stroke(width = 4f * scale),
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
