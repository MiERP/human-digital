package com.example.digitalhuman.ui

import androidx.compose.animation.Crossfade
import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.blur
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.unit.IntOffset
import androidx.compose.ui.unit.dp
import com.example.digitalhuman.R
import com.example.digitalhuman.network.ConnectionState
import com.example.digitalhuman.network.RobotEmotion

/**
 * Avatar Doraemon 2D hoạt hình nguyên bản (Chuẩn tỷ lệ Fujiko F. Fujio).
 * - Hiển thị bộ tạo hình 2D sắc nét chuẩn anime theo từng trạng thái và cảm xúc.
 * - Hiệu ứng chuyển cảnh Crossfade mượt mà khi đổi cảm xúc / trạng thái.
 * - Lơ lửng bồng bềnh tự nhiên (Floating 60 FPS).
 * - Hào quang tỏa sáng (Aura Glow) phản hồi theo nhịp đàm thoại.
 * - Khẩu hình Lip-sync chuyển động trực tiếp theo biên độ âm thanh Gemini Live.
 */
@Composable
fun DoraemonAvatar(
    state: ConnectionState,
    amplitude: Float, // 0.0f -> 1.0f
    emotion: RobotEmotion = RobotEmotion(),
    modifier: Modifier = Modifier
) {
    val isSleeping = state == ConnectionState.SLEEPING
    val isSpeaking = state == ConnectionState.SPEAKING || amplitude > 0.05f
    val infiniteTransition = rememberInfiniteTransition(label = "doraemon_anim")

    // 1. Hiệu ứng lơ lửng bồng bềnh
    val floatOffset by infiniteTransition.animateFloat(
        initialValue = -8f,
        targetValue = 8f,
        animationSpec = infiniteRepeatable(
            animation = tween(if (isSleeping) 2800 else 2000, easing = FastOutSlowInEasing),
            repeatMode = RepeatMode.Reverse
        ),
        label = "floating"
    )

    // 2. Hiệu ứng nhấp nháy hào quang (Aura Pulse)
    val auraPulse by infiniteTransition.animateFloat(
        initialValue = 0.85f,
        targetValue = 1.15f,
        animationSpec = infiniteRepeatable(
            animation = tween(1200, easing = FastOutSlowInEasing),
            repeatMode = RepeatMode.Reverse
        ),
        label = "aura_pulse"
    )

    // 3. Chọn Drawable phù hợp theo trạng thái, cảm xúc và khẩu hình âm thanh (Sprite Keyframes)
    val baseDrawableRes = getDoraemonDrawable(state, emotion)
    val currentDrawableRes = if (isSpeaking && !isSleeping && baseDrawableRes == R.drawable.doraemon_idle) {
        when {
            amplitude < 0.05f -> R.drawable.doraemon_idle
            amplitude < 0.35f -> R.drawable.doraemon_speaking_half
            else -> R.drawable.doraemon_speaking
        }
    } else {
        baseDrawableRes
    }

    // 4. Màu sắc hào quang theo trạng thái
    val auraColor = getAuraColor(state, emotion)

    Box(
        modifier = modifier
            .size(300.dp)
            .offset { IntOffset(0, floatOffset.toInt()) },
        contentAlignment = Alignment.Center
    ) {
        // Hào quang tỏa sáng phía sau Doraemon
        if (auraColor != null) {
            Box(
                modifier = Modifier
                    .size(240.dp * auraPulse)
                    .clip(CircleShape)
                    .blur(36.dp)
                    .drawBehind {
                        drawCircle(
                            brush = Brush.radialGradient(
                                colors = listOf(
                                    auraColor.copy(alpha = if (isSpeaking) 0.45f else 0.25f),
                                    Color.Transparent
                                )
                            )
                        )
                    }
            )
        }

        // Hình ảnh Doraemon 2D Anime sắc nét chuẩn Sprite Animation
        Crossfade(
            targetState = currentDrawableRes,
            animationSpec = tween(durationMillis = if (isSpeaking) 80 else 300),
            label = "doraemon_crossfade"
        ) { drawableId ->
            Image(
                painter = painterResource(id = drawableId),
                contentDescription = "Doraemon Avatar",
                contentScale = ContentScale.Fit,
                modifier = Modifier.fillMaxSize()
            )
        }
    }
}

/**
 * Lựa chọn Drawable resource phù hợp nhất cho Doraemon.
 */
private fun getDoraemonDrawable(state: ConnectionState, emotion: RobotEmotion): Int {
    if (state == ConnectionState.SLEEPING) {
        return R.drawable.doraemon_sleeping
    }

    // Ưu tiên trạng thái kết nối đặc thù
    return when (state) {
        ConnectionState.LISTENING -> R.drawable.doraemon_listening
        ConnectionState.THINKING -> R.drawable.doraemon_thinking
        else -> {
            // Lựa chọn theo cảm xúc nội tâm của Emotion Engine
            when (emotion.emotion) {
                "excited" -> R.drawable.doraemon_excited
                "proud" -> R.drawable.doraemon_proud
                "surprised" -> R.drawable.doraemon_surprised
                "displeased" -> R.drawable.doraemon_pout
                "sad" -> R.drawable.doraemon_sad
                "strict" -> R.drawable.doraemon_thinking
                "happy" -> if (emotion.energy == "excited") R.drawable.doraemon_excited else R.drawable.doraemon_idle
                else -> {
                    if (emotion.energy == "sleepy" || emotion.energy == "drowsy") {
                        R.drawable.doraemon_sleeping
                    } else {
                        R.drawable.doraemon_idle
                    }
                }
            }
        }
    }
}

/**
 * Màu hào quang ánh sáng tỏa ra từ Doraemon.
 */
private fun getAuraColor(state: ConnectionState, emotion: RobotEmotion): Color? {
    if (state == ConnectionState.SLEEPING) return null

    return when {
        state == ConnectionState.LISTENING -> Color(0xFF10B981) // Emerald
        state == ConnectionState.THINKING -> Color(0xFFF59E0B) // Amber
        state == ConnectionState.SPEAKING -> Color(0xFF06B6D4) // Cyan
        emotion.emotion == "excited" -> Color(0xFFEC4899) // Pink
        emotion.emotion == "proud" -> Color(0xFF6366F1) // Indigo
        emotion.emotion == "surprised" -> Color(0xFFA855F7) // Purple
        emotion.emotion == "displeased" -> Color(0xFFFB7185) // Rose
        emotion.emotion == "sad" -> Color(0xFF94A3B8) // Slate
        else -> Color(0xFF0288D1) // Doraemon Blue
    }
}
