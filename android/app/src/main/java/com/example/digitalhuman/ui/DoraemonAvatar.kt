package com.example.digitalhuman.ui

import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.blur
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.unit.IntOffset
import androidx.compose.ui.unit.dp
import com.example.digitalhuman.R
import com.example.digitalhuman.network.CompanionInfo
import com.example.digitalhuman.network.ConnectionState
import com.example.digitalhuman.network.RobotEmotion

/** The same Robo illustration responds to listening, thinking and live speech. */
@Composable
fun CompanionAvatar(
    state: ConnectionState,
    amplitude: Float,
    emotion: RobotEmotion = RobotEmotion(),
    companion: CompanionInfo = CompanionInfo(),
    modifier: Modifier = Modifier,
) {
    val motion = companionMotion(state, amplitude)
    val tilt by animateFloatAsState(motion.tiltDegrees, tween(260), label = "robo_tilt")
    val scale by animateFloatAsState(
        motion.scale,
        tween(if (state == ConnectionState.SPEAKING) 85 else 260),
        label = "robo_scale",
    )
    val talk by animateFloatAsState(motion.talkLevel, tween(75), label = "robo_talk")
    val opacity by animateFloatAsState(motion.opacity, tween(350), label = "robo_opacity")
    val infinite = rememberInfiniteTransition(label = "robo_idle")
    val bob by infinite.animateFloat(
        initialValue = -6f,
        targetValue = 6f,
        animationSpec = infiniteRepeatable(tween(2100, easing = FastOutSlowInEasing), RepeatMode.Reverse),
        label = "robo_bob",
    )
    val halo by infinite.animateFloat(
        initialValue = 0.92f,
        targetValue = 1.08f,
        animationSpec = infiniteRepeatable(tween(1300, easing = FastOutSlowInEasing), RepeatMode.Reverse),
        label = "robo_halo",
    )

    val accent = parseHexColor(companion.palette.firstOrNull()) ?: Color(0xFF18DCE9)
    val auraColor = when (state) {
        ConnectionState.LISTENING -> Color(0xFF36D6B1)
        ConnectionState.THINKING -> Color(0xFFFFC46B)
        ConnectionState.SPEAKING -> accent
        ConnectionState.SLEEPING -> Color.Transparent
        else -> when (emotion.emotion) {
            "excited", "proud" -> Color(0xFFFFC46B)
            "sad" -> Color(0xFF8FA7BB)
            else -> accent
        }
    }

    Box(modifier = modifier.size(280.dp), contentAlignment = Alignment.Center) {
        Box(
            modifier = Modifier
                .align(Alignment.BottomCenter)
                .offset(y = (-4).dp)
                .size(width = 150.dp, height = 20.dp)
                .clip(CircleShape)
                .background(Color.Black.copy(alpha = 0.12f)),
        )

        if (state != ConnectionState.SLEEPING) {
            Box(
                modifier = Modifier
                    .size(210.dp * halo)
                    .blur(30.dp)
                    .clip(CircleShape)
                    .background(
                        Brush.radialGradient(
                            listOf(auraColor.copy(alpha = 0.42f + talk * 0.24f), Color.Transparent),
                        ),
                    ),
            )
        }

        if (state == ConnectionState.SPEAKING) {
            Box(
                modifier = Modifier
                    .size(252.dp)
                    .drawBehind {
                        drawCircle(
                            color = auraColor.copy(alpha = 0.16f + talk * 0.34f),
                            radius = size.minDimension * (0.40f + talk * 0.08f),
                            center = Offset(size.width / 2, size.height / 2),
                            style = Stroke(width = 2.dp.toPx()),
                        )
                    },
            )
        }

        Box(
            modifier = Modifier
                .fillMaxSize()
                .offset { IntOffset(0, (bob * if (state == ConnectionState.SLEEPING) 0.25f else 1f).toInt()) }
                .graphicsLayer {
                    rotationZ = tilt
                    scaleX = scale
                    scaleY = scale
                    alpha = opacity
                },
            contentAlignment = Alignment.Center,
        ) {
            Image(
                painter = painterResource(R.drawable.robo_avatar),
                contentDescription = "${companion.name} đang ${stateLabel(state)}",
                contentScale = ContentScale.Fit,
                modifier = Modifier.fillMaxSize(),
            )
            if (state == ConnectionState.SPEAKING && talk > 0.08f) {
                Box(
                    modifier = Modifier
                        .offset(y = (-14).dp)
                        .size(width = (16 + talk * 8).dp, height = (2 + talk * 7).dp)
                        .clip(RoundedCornerShape(50))
                        .background(Color(0xFF2FF6F9).copy(alpha = 0.6f + talk * 0.4f)),
                )
            }
        }
    }
}

private fun stateLabel(state: ConnectionState): String = when (state) {
    ConnectionState.LISTENING -> "lắng nghe"
    ConnectionState.THINKING -> "suy nghĩ"
    ConnectionState.SPEAKING -> "nói chuyện"
    ConnectionState.SLEEPING -> "ngủ"
    else -> "ở đây"
}

private fun parseHexColor(hex: String?): Color? {
    if (hex.isNullOrBlank()) return null
    return try {
        val clean = hex.trim().removePrefix("#")
        when (clean.length) {
            6 -> Color(0xFF000000L or clean.toLong(16))
            8 -> Color(clean.toLong(16))
            else -> null
        }
    } catch (_: NumberFormatException) {
        null
    }
}
