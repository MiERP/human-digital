package com.example.digitalhuman.ui

import androidx.compose.animation.Crossfade
import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
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
import androidx.compose.ui.graphics.BlendMode
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.ColorFilter
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.unit.IntOffset
import androidx.compose.ui.unit.dp
import com.example.digitalhuman.R
import com.example.digitalhuman.network.CompanionInfo
import com.example.digitalhuman.network.ConnectionState
import com.example.digitalhuman.network.RobotEmotion

/**
 * Avatar nhân vật đồng hành 2D hoạt hình (Chuẩn tỷ lệ Fujiko F. Fujio).
 * - Hiển thị bộ tạo hình 2D sắc nét chuẩn anime theo từng trạng thái và cảm xúc.
 * - Bản sắc nhân vật (bảng màu) quyết định tông màu: bé trai (xanh/lục) hoặc bé gái (hồng/tím).
 * - Hiệu ứng chuyển cảnh Crossfade mượt mà khi đổi cảm xúc / trạng thái.
 * - Lơ lửng bồng bềnh tự nhiên (Floating 60 FPS).
 * - Hào quang tỏa sáng (Aura Glow) phản hồi theo nhịp đàm thoại.
 * - Khẩu hình Lip-sync chuyển động trực tiếp theo biên độ âm thanh Gemini Live.
 */
@Composable
fun CompanionAvatar(
    state: ConnectionState,
    amplitude: Float, // 0.0f -> 1.0f
    emotion: RobotEmotion = RobotEmotion(),
    companion: CompanionInfo = CompanionInfo(),
    modifier: Modifier = Modifier
) {
    val isSleeping = state == ConnectionState.SLEEPING
    val isSpeaking = state == ConnectionState.SPEAKING || amplitude > 0.05f
    val infiniteTransition = rememberInfiniteTransition(label = "companion_anim")

    // 1. Hiệu ứng lơ lửng bồng bềnh
    val floatOffset by infiniteTransition.animateFloat(
        initialValue = -10f,
        targetValue = 10f,
        animationSpec = infiniteRepeatable(
            animation = tween(if (isSleeping) 2800 else 2000, easing = FastOutSlowInEasing),
            repeatMode = RepeatMode.Reverse
        ),
        label = "floating"
    )

    // 2. Hiệu ứng nhấp nháy hào quang (Aura Pulse)
    val auraPulse by infiniteTransition.animateFloat(
        initialValue = 0.9f,
        targetValue = 1.15f,
        animationSpec = infiniteRepeatable(
            animation = tween(1200, easing = FastOutSlowInEasing),
            repeatMode = RepeatMode.Reverse
        ),
        label = "aura_pulse"
    )

    // 3. Chọn Drawable phù hợp theo trạng thái, cảm xúc và khẩu hình âm thanh (Sprite Keyframes)
    val baseDrawableRes = getCompanionDrawable(state, emotion)
    val currentDrawableRes = if (isSpeaking && !isSleeping) {
        when {
            amplitude < 0.05f -> baseDrawableRes
            amplitude < 0.35f -> R.drawable.doraemon_speaking_half
            else -> R.drawable.doraemon_speaking
        }
    } else {
        baseDrawableRes
    }

    // 4. Tông màu nhân vật: nhuộm màu bộ art gốc theo bảng màu persona (giữ chi tiết/nét).
    val accentColor = parseHexColor(companion.palette.firstOrNull())
    val isDefaultLook = companion.id == "boy_blue"
    val imageColorFilter = if (!isDefaultLook && accentColor != null) {
        ColorFilter.tint(accentColor, BlendMode.Color)
    } else null

    // 5. Màu sắc hào quang theo trạng thái (fallback = màu chủ đạo của nhân vật)
    val auraColor = getAuraColor(state, emotion, accentColor)

    Box(
        modifier = modifier
            .size(280.dp),
        contentAlignment = Alignment.Center
    ) {
        // Bóng đổ mờ hoạt hình dưới chân nhân vật
        Box(
            modifier = Modifier
                .align(Alignment.BottomCenter)
                .offset(y = (-10).dp)
                .size(width = 160.dp, height = 24.dp)
                .clip(CircleShape)
                .background(
                    Brush.radialGradient(
                        colors = listOf(
                            Color.Black.copy(alpha = 0.15f),
                            Color.Transparent
                        )
                    )
                )
        )

        // Hào quang tỏa sáng phía sau nhân vật
        if (auraColor != null) {
            Box(
                modifier = Modifier
                    .size(230.dp * auraPulse)
                    .offset { IntOffset(0, floatOffset.toInt()) }
                    .clip(CircleShape)
                    .blur(32.dp)
                    .drawBehind {
                        drawCircle(
                            brush = Brush.radialGradient(
                                colors = listOf(
                                    auraColor.copy(alpha = if (isSpeaking) 0.5f else 0.3f),
                                    Color.Transparent
                                )
                            )
                        )
                    }
            )
        }

        // Hình ảnh nhân vật 2D Anime sắc nét chuẩn Sprite Animation
        Crossfade(
            targetState = currentDrawableRes,
            animationSpec = tween(durationMillis = if (isSpeaking) 80 else 250),
            modifier = Modifier
                .fillMaxSize()
                .offset { IntOffset(0, floatOffset.toInt()) },
            label = "companion_crossfade"
        ) { drawableId ->
            Image(
                painter = painterResource(id = drawableId),
                contentDescription = "${companion.name} Avatar",
                contentScale = ContentScale.Fit,
                colorFilter = imageColorFilter,
                modifier = Modifier.fillMaxSize()
            )
        }
    }
}

/**
 * Lựa chọn Drawable resource phù hợp nhất cho nhân vật.
 */
private fun getCompanionDrawable(state: ConnectionState, emotion: RobotEmotion): Int {
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
 * Màu hào quang ánh sáng tỏa ra từ nhân vật.
 */
private fun getAuraColor(state: ConnectionState, emotion: RobotEmotion, accent: Color?): Color? {
    if (state == ConnectionState.SLEEPING) return null
    val fallback = accent ?: Color(0xFF0288D1)

    return when {
        state == ConnectionState.LISTENING -> Color(0xFF10B981) // Emerald
        state == ConnectionState.THINKING -> Color(0xFFF59E0B) // Amber
        state == ConnectionState.SPEAKING -> fallback
        emotion.emotion == "excited" -> Color(0xFFEC4899) // Pink
        emotion.emotion == "proud" -> Color(0xFF6366F1) // Indigo
        emotion.emotion == "surprised" -> Color(0xFFA855F7) // Purple
        emotion.emotion == "displeased" -> Color(0xFFFB7185) // Rose
        emotion.emotion == "sad" -> Color(0xFF94A3B8) // Slate
        else -> fallback
    }
}

/** Chuyển "#RRGGBB" hoặc "#AARRGGBB" thành Compose Color. */
private fun parseHexColor(hex: String?): Color? {
    if (hex.isNullOrBlank()) return null
    return try {
        val clean = hex.trim().removePrefix("#")
        val value = clean.toLong(16)
        when (clean.length) {
            6 -> Color(0xFF000000L or value)
            8 -> Color(value)
            else -> null
        }
    } catch (e: Exception) {
        null
    }
}
