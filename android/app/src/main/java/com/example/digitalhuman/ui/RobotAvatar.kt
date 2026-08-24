package com.example.digitalhuman.ui

import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
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
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.unit.dp
import com.example.digitalhuman.network.ConnectionState

/**
 * 2D Robot Avatar vẽ hoàn toàn bằng Jetpack Compose Canvas (Native, 60 FPS, 0% asset nặng).
 * - Cử động miệng mượt mà theo biên độ âm thanh (Lip-sync real-time).
 * - Mắt LED đổi biểu cảm sinh động theo trạng thái (Listening, Thinking, Speaking, Idle).
 * - Hiệu ứng lơ lửng và phát sáng ăng-ten cực kỳ thu hút trẻ em.
 */
@Composable
fun RobotAvatar(
    state: ConnectionState,
    amplitude: Float, // 0.0f -> 1.0f
    modifier: Modifier = Modifier
) {
    val infiniteTransition = rememberInfiniteTransition(label = "robot_anim")

    // Hiệu ứng lơ lửng (Floating)
    val floatOffset by infiniteTransition.animateFloat(
        initialValue = -12f,
        targetValue = 12f,
        animationSpec = infiniteRepeatable(
            animation = tween(2000, easing = FastOutSlowInEasing),
            repeatMode = RepeatMode.Reverse
        ),
        label = "floating"
    )

    // Hiệu ứng chớp mắt (Blinking)
    val eyeBlink by infiniteTransition.animateFloat(
        initialValue = 1f,
        targetValue = 1f,
        animationSpec = infiniteRepeatable(
            animation = keyframes {
                durationMillis = 4000
                1f at 0
                1f at 3700
                0.1f at 3800
                1f at 3900
                1f at 4000
            },
            repeatMode = RepeatMode.Restart
        ), label = "eyeBlink"
    )

    // Hiệu ứng sóng ăng-ten khi lắng nghe
    val antennaPulse by infiniteTransition.animateFloat(
        initialValue = 0.5f,
        targetValue = 1.3f,
        animationSpec = infiniteRepeatable(
            animation = tween(800, easing = FastOutSlowInEasing),
            repeatMode = RepeatMode.Reverse
        ),
        label = "antenna_pulse"
    )

    Box(
        modifier = modifier.size(280.dp),
        contentAlignment = Alignment.Center
    ) {
        Canvas(modifier = Modifier.fillMaxSize()) {
            val center = Offset(size.width / 2f, size.height / 2f + floatOffset)
            val headWidth = 180.dp.toPx()
            val headHeight = 150.dp.toPx()

            // 1. Vẽ Ăng-ten (Antenna)
            val antennaBase = Offset(center.x, center.y - headHeight / 2f)
            val antennaTip = Offset(center.x, center.y - headHeight / 2f - 35.dp.toPx())

            drawLine(
                color = Color(0xFF64748B),
                start = antennaBase,
                end = antennaTip,
                strokeWidth = 6.dp.toPx(),
                cap = StrokeCap.Round
            )

            // Đèn trên đầu ăng-ten
            val antennaColor = when (state) {
                ConnectionState.LISTENING -> Color(0xFF10B981) // Xanh lá khi nghe bé nói
                ConnectionState.THINKING -> Color(0xFFF59E0B)  // Vàng khi suy nghĩ
                ConnectionState.SPEAKING -> Color(0xFF06B6D4)  // Cyan khi đang nói
                else -> Color(0xFF94A3B8)
            }

            // Hào quang ăng-ten
            if (state == ConnectionState.LISTENING || state == ConnectionState.SPEAKING) {
                drawCircle(
                    color = antennaColor.copy(alpha = 0.3f),
                    radius = 16.dp.toPx() * antennaPulse,
                    center = antennaTip
                )
            }
            drawCircle(
                color = antennaColor,
                radius = 10.dp.toPx(),
                center = antennaTip
            )

            // 2. Vẽ Tai Robot (Ears)
            val earWidth = 16.dp.toPx()
            val earHeight = 40.dp.toPx()
            // Tai trái
            drawRoundRect(
                color = Color(0xFF3B82F6),
                topLeft = Offset(center.x - headWidth / 2f - earWidth + 4.dp.toPx(), center.y - earHeight / 2f),
                size = Size(earWidth, earHeight),
                cornerRadius = CornerRadius(8.dp.toPx())
            )
            // Tai phải
            drawRoundRect(
                color = Color(0xFF3B82F6),
                topLeft = Offset(center.x + headWidth / 2f - 4.dp.toPx(), center.y - earHeight / 2f),
                size = Size(earWidth, earHeight),
                cornerRadius = CornerRadius(8.dp.toPx())
            )

            // 3. Vẽ Đầu Robot (Head Outer Shell)
            val headGradient = Brush.verticalGradient(
                colors = listOf(Color(0xFFF8FAFC), Color(0xFFE2E8F0))
            )
            drawRoundRect(
                brush = headGradient,
                topLeft = Offset(center.x - headWidth / 2f, center.y - headHeight / 2f),
                size = Size(headWidth, headHeight),
                cornerRadius = CornerRadius(40.dp.toPx())
            )

            // Viền đầu (Outline)
            drawRoundRect(
                color = Color(0xFFCBD5E1),
                topLeft = Offset(center.x - headWidth / 2f, center.y - headHeight / 2f),
                size = Size(headWidth, headHeight),
                cornerRadius = CornerRadius(40.dp.toPx()),
                style = Stroke(width = 4.dp.toPx())
            )

            // 4. Màn hình mặt Robot (Face Screen - Dark visor)
            val screenWidth = 140.dp.toPx()
            val screenHeight = 100.dp.toPx()
            drawRoundRect(
                color = Color(0xFF0F172A),
                topLeft = Offset(center.x - screenWidth / 2f, center.y - screenHeight / 2f + 4.dp.toPx()),
                size = Size(screenWidth, screenHeight),
                cornerRadius = CornerRadius(26.dp.toPx())
            )

            // 5. Má hồng dễ thương cho trẻ em (Blush)
            drawCircle(
                color = Color(0xFFFB7185).copy(alpha = 0.5f),
                radius = 8.dp.toPx(),
                center = Offset(center.x - screenWidth / 2f + 16.dp.toPx(), center.y + 16.dp.toPx())
            )
            drawCircle(
                color = Color(0xFFFB7185).copy(alpha = 0.5f),
                radius = 8.dp.toPx(),
                center = Offset(center.x + screenWidth / 2f - 16.dp.toPx(), center.y + 16.dp.toPx())
            )

            // 6. Vẽ Mắt LED (LED Eyes)
            val eyeSpacing = 32.dp.toPx()
            val eyeY = center.y - 10.dp.toPx()
            val eyeColor = when (state) {
                ConnectionState.LISTENING -> Color(0xFF34D399) // Xanh ngọc lắng nghe
                ConnectionState.SPEAKING -> Color(0xFF38BDF8)  // Xanh dương tươi vui
                ConnectionState.THINKING -> Color(0xFFFBBF24)  // Vàng suy nghĩ
                else -> Color(0xFF60A5FA)
            }

            if (state == ConnectionState.SPEAKING) {
                // Mắt cười cong hình trăng khuyết (^ ^) khi đang nói chuyện
                drawArc(
                    color = eyeColor,
                    startAngle = 180f,
                    sweepAngle = 180f,
                    useCenter = false,
                    topLeft = Offset(center.x - eyeSpacing - 14.dp.toPx(), eyeY - 8.dp.toPx()),
                    size = Size(24.dp.toPx(), 18.dp.toPx()),
                    style = Stroke(width = 5.dp.toPx(), cap = StrokeCap.Round)
                )
                drawArc(
                    color = eyeColor,
                    startAngle = 180f,
                    sweepAngle = 180f,
                    useCenter = false,
                    topLeft = Offset(center.x + eyeSpacing - 10.dp.toPx(), eyeY - 8.dp.toPx()),
                    size = Size(24.dp.toPx(), 18.dp.toPx()),
                    style = Stroke(width = 5.dp.toPx(), cap = StrokeCap.Round)
                )
            } else {
                // Mắt tròn to tròn thông minh
                val eyeScaleY = eyeBlink
                drawOval(
                    color = eyeColor,
                    topLeft = Offset(center.x - eyeSpacing - 10.dp.toPx(), eyeY - (12.dp.toPx() * eyeScaleY)),
                    size = Size(20.dp.toPx(), 24.dp.toPx() * eyeScaleY)
                )
                drawOval(
                    color = eyeColor,
                    topLeft = Offset(center.x + eyeSpacing - 10.dp.toPx(), eyeY - (12.dp.toPx() * eyeScaleY)),
                    size = Size(20.dp.toPx(), 24.dp.toPx() * eyeScaleY)
                )
            }

            // 7. Miệng Robot Cử Động Theo Âm Thanh (Lip-Sync Real-Time)
            val mouthY = center.y + 24.dp.toPx()
            val mouthBaseWidth = 28.dp.toPx()
            val mouthOpenHeight = (4.dp.toPx() + (amplitude * 24.dp.toPx())).coerceAtMost(28.dp.toPx())

            if (amplitude > 0.05f || state == ConnectionState.SPEAKING) {
                // Miệng mở đóng theo nhịp âm lượng
                drawRoundRect(
                    color = Color(0xFF38BDF8),
                    topLeft = Offset(center.x - mouthBaseWidth / 2f, mouthY - mouthOpenHeight / 2f),
                    size = Size(mouthBaseWidth, mouthOpenHeight),
                    cornerRadius = CornerRadius(mouthOpenHeight / 2f)
                )
            } else {
                // Nụ cười mỉm lúc bình thường
                drawArc(
                    color = Color(0xFF94A3B8),
                    startAngle = 0f,
                    sweepAngle = 180f,
                    useCenter = false,
                    topLeft = Offset(center.x - 14.dp.toPx(), mouthY - 4.dp.toPx()),
                    size = Size(28.dp.toPx(), 12.dp.toPx()),
                    style = Stroke(width = 4.dp.toPx(), cap = StrokeCap.Round)
                )
            }
        }
    }
}
