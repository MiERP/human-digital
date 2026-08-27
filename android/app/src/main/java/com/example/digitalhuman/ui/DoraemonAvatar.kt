package com.example.digitalhuman.ui

import androidx.compose.animation.core.FastOutSlowInEasing
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
import androidx.compose.ui.geometry.Rect
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.drawscope.clipPath
import androidx.compose.ui.unit.dp
import com.example.digitalhuman.network.ConnectionState
import com.example.digitalhuman.network.RobotEmotion

/**
 * Avatar Doraemon vẽ hoàn toàn bằng Jetpack Compose Canvas (Native, 60 FPS).
 * - Chuông cổ phát sáng theo trạng thái trò chuyện và đổi màu theo cảm xúc.
 * - Biểu cảm qua mắt, mũi, miệng, ria mép và TAY (giơ cao, chống hông, rủ xuống...).
 * - Miệng cử động theo biên độ âm thanh (lip-sync real-time).
 * - Khi ngủ: nhắm mắt, tay rủ, bong bóng mũi phập phồng.
 */
@Composable
fun DoraemonAvatar(
    state: ConnectionState,
    amplitude: Float, // 0.0f -> 1.0f
    emotion: RobotEmotion = RobotEmotion(),
    modifier: Modifier = Modifier
) {
    val infiniteTransition = rememberInfiniteTransition(label = "doraemon_anim")
    val isSleeping = state == ConnectionState.SLEEPING

    // Hiệu ứng lơ lửng — khi ngủ chỉ lơ lửng nhẹ để trông đang thở.
    val floatOffset by infiniteTransition.animateFloat(
        initialValue = -10f,
        targetValue = 10f,
        animationSpec = infiniteRepeatable(
            animation = tween(if (isSleeping) 2600 else 2000, easing = FastOutSlowInEasing),
            repeatMode = RepeatMode.Reverse
        ),
        label = "floating"
    )

    // Hiệu ứng chớp mắt — khi ngủ thì mắt nhắm hẳn, không chớp.
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
        ),
        label = "eyeBlink"
    )

    // Hào quang chuông cổ khi lắng nghe/nói
    val bellPulse by infiniteTransition.animateFloat(
        initialValue = 0.5f,
        targetValue = 1.3f,
        animationSpec = infiniteRepeatable(
            animation = tween(800, easing = FastOutSlowInEasing),
            repeatMode = RepeatMode.Reverse
        ),
        label = "bell_pulse"
    )

    Box(
        modifier = modifier.size(280.dp),
        contentAlignment = Alignment.Center
    ) {
        Canvas(modifier = Modifier.fillMaxSize()) {
            val floatScale = if (isSleeping) 0.25f else 1f
            val cx = size.width / 2f
            val floatY = floatOffset * floatScale
            val headRadius = 92.dp.toPx()
            val headCenter = Offset(cx, size.height / 2f - 26.dp.toPx() + floatY)

            // ==== 1. Thân + chân (nằm phía sau đầu) ====
            val bodyTop = headCenter.y + headRadius - 16.dp.toPx()
            val bodyW = 148.dp.toPx()
            val bodyH = 74.dp.toPx()

            // Chân trắng tròn
            drawOval(
                color = DoraemonWhite,
                topLeft = Offset(cx - 52.dp.toPx(), bodyTop + bodyH - 18.dp.toPx()),
                size = Size(44.dp.toPx(), 22.dp.toPx())
            )
            drawOval(
                color = DoraemonWhite,
                topLeft = Offset(cx + 8.dp.toPx(), bodyTop + bodyH - 18.dp.toPx()),
                size = Size(44.dp.toPx(), 22.dp.toPx())
            )

            // Thân xanh
            drawOval(
                color = DoraemonBlue,
                topLeft = Offset(cx - bodyW / 2f, bodyTop),
                size = Size(bodyW, bodyH)
            )

            // Bụng trắng
            drawOval(
                color = DoraemonWhite,
                topLeft = Offset(cx - 52.dp.toPx(), bodyTop + 14.dp.toPx()),
                size = Size(104.dp.toPx(), 46.dp.toPx())
            )

            // Túi thần kỳ 4D (bán nguyệt trắng viền nhạt trên bụng)
            val pocketR = 30.dp.toPx()
            val pocketTop = bodyTop + 32.dp.toPx() - pocketR
            drawArc(
                color = DoraemonWhite,
                startAngle = 0f,
                sweepAngle = 180f,
                useCenter = true,
                topLeft = Offset(cx - pocketR, pocketTop),
                size = Size(pocketR * 2, pocketR * 2)
            )
            drawArc(
                color = Color(0xFFB0BEC5),
                startAngle = 0f,
                sweepAngle = 180f,
                useCenter = false,
                topLeft = Offset(cx - pocketR, pocketTop),
                size = Size(pocketR * 2, pocketR * 2),
                style = Stroke(width = 2.dp.toPx())
            )

            // ==== 2. Chuông cổ (đèn cảm xúc — thay cho ăng-ten) ====
            val bellCenter = Offset(cx, bodyTop + 16.dp.toPx())
            drawRoundRect(
                color = BellRed,
                topLeft = Offset(cx - 22.dp.toPx(), bodyTop - 2.dp.toPx()),
                size = Size(44.dp.toPx(), 8.dp.toPx()),
                cornerRadius = CornerRadius(4.dp.toPx())
            )
            val bellColor = if (isSleeping) {
                Color(0xFF90A4AE).copy(alpha = 0.5f)
            } else {
                emotionBellColor(emotion, state)
            }
            if (!isSleeping && (state == ConnectionState.LISTENING || state == ConnectionState.SPEAKING)) {
                drawCircle(
                    color = bellColor.copy(alpha = 0.3f),
                    radius = 14.dp.toPx() * bellPulse,
                    center = bellCenter
                )
            }
            drawCircle(color = bellColor, radius = 11.dp.toPx(), center = bellCenter)
            // Hai lỗ trên chuông
            drawCircle(
                color = Color(0xFF8D6E63).copy(alpha = 0.85f),
                radius = 2.5.dp.toPx(),
                center = bellCenter + Offset(-3.dp.toPx(), 4.dp.toPx())
            )
            drawCircle(
                color = Color(0xFF8D6E63).copy(alpha = 0.85f),
                radius = 2.5.dp.toPx(),
                center = bellCenter + Offset(3.dp.toPx(), 4.dp.toPx())
            )

            // ==== 3. Đầu tròn xanh ====
            drawCircle(color = DoraemonBlue, radius = headRadius, center = headCenter)

            // Mặt trắng (clip trong đầu để không tràn ra ngoài)
            val headRect = Rect(
                headCenter.x - headRadius,
                headCenter.y - headRadius,
                headCenter.x + headRadius,
                headCenter.y + headRadius
            )
            clipPath(Path().apply { addOval(headRect) }) {
                val faceW = 156.dp.toPx()
                val faceH = 140.dp.toPx()
                val faceTop = headCenter.y + 14.dp.toPx() - faceH / 2f
                drawOval(
                    color = DoraemonWhite,
                    topLeft = Offset(cx - faceW / 2f, faceTop),
                    size = Size(faceW, faceH)
                )
                drawOval(
                    color = Color(0xFFCFD8DC),
                    topLeft = Offset(cx - faceW / 2f, faceTop),
                    size = Size(faceW, faceH),
                    style = Stroke(width = 1.5.dp.toPx())
                )
            }

            // ==== 4. Mắt — biểu cảm theo cảm xúc, fallback theo trạng thái ====
            val eyeSpacing = 26.dp.toPx()
            val eyeY = headCenter.y - 16.dp.toPx()

            if (isSleeping) {
                drawSleepingEyes(cx, eyeSpacing, eyeY)
            } else {
                when (emotion.emotion) {
                    "happy" -> drawHappyEyes(cx, eyeSpacing, eyeY)
                    "surprised" -> drawSurprisedEyes(cx, eyeSpacing, eyeY, eyeBlink)
                    "sad" -> drawSadEyes(cx, eyeSpacing, eyeY, eyeBlink)
                    "strict" -> drawStrictEyes(cx, eyeSpacing, eyeY, eyeBlink)
                    "displeased" -> drawDispleasedEyes(cx, eyeSpacing, eyeY, eyeBlink)
                    else -> {
                        if (isLowEnergy(emotion)) {
                            drawSleepyEyes(cx, eyeSpacing, eyeY, eyeBlink)
                        } else {
                            drawRoundEyes(cx, eyeSpacing, eyeY, eyeBlink)
                        }
                    }
                }
            }

            // ==== 5. Mũi đỏ + đường nối xuống miệng ====
            val noseY = headCenter.y + 12.dp.toPx()
            drawCircle(color = Color(0xFFE53935), radius = 8.dp.toPx(), center = Offset(cx, noseY))
            drawLine(
                color = Color(0xFF90A4AE),
                start = Offset(cx, noseY + 8.dp.toPx()),
                end = Offset(cx, headCenter.y + 34.dp.toPx()),
                strokeWidth = 2.5.dp.toPx(),
                cap = StrokeCap.Round
            )

            // ==== 6. Ria mép (3 sợi mỗi bên) ====
            val whiskerY = headCenter.y + 10.dp.toPx()
            for (side in intArrayOf(-1, 1)) {
                val startX = cx + side * 34.dp.toPx()
                for (i in 0..2) {
                    val endX = cx + side * (60 + i * 7).dp.toPx()
                    val endY = whiskerY + (i - 1) * 8.dp.toPx()
                    drawLine(
                        color = InkGray,
                        start = Offset(startX, whiskerY),
                        end = Offset(endX, endY),
                        strokeWidth = 2.dp.toPx(),
                        cap = StrokeCap.Round
                    )
                }
            }

            // ==== 7. Miệng cử động theo âm thanh (lip-sync) ====
            val mouthY = headCenter.y + 44.dp.toPx()
            when {
                isSleeping -> drawSleepingMouth(cx, mouthY)
                amplitude > 0.05f || state == ConnectionState.SPEAKING -> drawTalkingMouth(cx, mouthY, amplitude)
                else -> when {
                    emotion.emotion == "displeased" -> drawPoutMouth(cx, mouthY)
                    emotion.emotion == "sad" -> drawSadMouth(cx, mouthY)
                    emotion.emotion == "strict" -> drawStraightMouth(cx, mouthY)
                    emotion.emotion == "surprised" -> drawSurprisedMouth(cx, mouthY)
                    emotion.energy == "sleepy" || emotion.energy == "drowsy" -> drawYawnMouth(cx, mouthY)
                    else -> drawSmileMouth(cx, mouthY, big = emotion.emotion == "happy")
                }
            }

            // ==== 8. Tay tròn trắng — tư thế theo cảm xúc ====
            val (handL, handR) = handOffsets(emotion, state, cx, headCenter.y, bodyTop, bodyH)
            val handRadius = 20.dp.toPx()
            drawCircle(color = DoraemonWhite, radius = handRadius, center = handL)
            drawCircle(color = DoraemonWhite, radius = handRadius, center = handR)
            drawCircle(
                color = Color(0xFFCFD8DC),
                radius = handRadius,
                center = handL,
                style = Stroke(width = 1.5.dp.toPx())
            )
            drawCircle(
                color = Color(0xFFCFD8DC),
                radius = handRadius,
                center = handR,
                style = Stroke(width = 1.5.dp.toPx())
            )

            // ==== 9. Bong bóng mũi khi ngủ ====
            if (isSleeping) {
                drawCircle(
                    color = Color(0xFF81D4FA).copy(alpha = 0.7f),
                    radius = 4.dp.toPx() + 3.dp.toPx() * bellPulse,
                    center = Offset(cx + 22.dp.toPx(), noseY - 6.dp.toPx())
                )
            }
        }
    }
}

// ==================== Mắt ====================

/** Mắt cơ bản của Doraemon: oval trắng + con ngươi đen + highlight. */
private fun DrawScope.drawEyeBase(
    cx: Float,
    eyeY: Float,
    blink: Float,
    pupilDx: Float = 0f,
    pupilDy: Float = 0f,
    pupilRadius: Float = 6.5.dp.toPx(),
    eyeScale: Float = 1f,
) {
    val eyeW = 26.dp.toPx() * eyeScale
    val eyeH = 32.dp.toPx() * eyeScale * blink
    val top = eyeY - eyeH / 2f

    // Đang chớp: mắt khép thành đường cong
    if (blink < 0.25f) {
        drawArc(
            color = InkGray,
            startAngle = 0f,
            sweepAngle = 180f,
            useCenter = false,
            topLeft = Offset(cx - 10.dp.toPx(), top),
            size = Size(20.dp.toPx(), 8.dp.toPx()),
            style = Stroke(width = 4.dp.toPx(), cap = StrokeCap.Round)
        )
        return
    }

    drawOval(color = DoraemonWhite, topLeft = Offset(cx - eyeW / 2f, top), size = Size(eyeW, eyeH))
    drawOval(
        color = Color(0xFFB0BEC5),
        topLeft = Offset(cx - eyeW / 2f, top),
        size = Size(eyeW, eyeH),
        style = Stroke(width = 1.5.dp.toPx())
    )

    val pr = (pupilRadius * eyeScale) * blink
    drawCircle(color = InkGray, radius = pr, center = Offset(cx + pupilDx, eyeY + pupilDy))
    drawCircle(
        color = Color.White,
        radius = pr * 0.35f,
        center = Offset(cx + pupilDx - pr * 0.3f, eyeY + pupilDy - pr * 0.3f)
    )
}

private fun DrawScope.drawRoundEyes(cx: Float, spacing: Float, eyeY: Float, blink: Float) {
    drawEyeBase(cx - spacing, eyeY, blink)
    drawEyeBase(cx + spacing, eyeY, blink)
}

private fun DrawScope.drawHappyEyes(cx: Float, spacing: Float, eyeY: Float) {
    // Mắt cười cong hình trăng khuyết (^ ^)
    fun arc(ex: Float) {
        drawArc(
            color = InkGray,
            startAngle = 180f,
            sweepAngle = 180f,
            useCenter = false,
            topLeft = Offset(ex - 13.dp.toPx(), eyeY - 10.dp.toPx()),
            size = Size(26.dp.toPx(), 16.dp.toPx()),
            style = Stroke(width = 5.dp.toPx(), cap = StrokeCap.Round)
        )
    }
    arc(cx - spacing)
    arc(cx + spacing)
}

private fun DrawScope.drawSurprisedEyes(cx: Float, spacing: Float, eyeY: Float, blink: Float) {
    // Mắt mở to, con ngươi nhỏ
    drawEyeBase(cx - spacing, eyeY, blink, eyeScale = 1.15f, pupilRadius = 4.dp.toPx())
    drawEyeBase(cx + spacing, eyeY, blink, eyeScale = 1.15f, pupilRadius = 4.dp.toPx())
}

private fun DrawScope.drawSadEyes(cx: Float, spacing: Float, eyeY: Float, blink: Float) {
    // Con ngươi cụp xuống + mí sụp + giọt lệ nhỏ
    fun eye(ex: Float) {
        drawEyeBase(ex, eyeY, blink, pupilDy = 5.dp.toPx())
        drawArc(
            color = InkGray,
            startAngle = 0f,
            sweepAngle = 180f,
            useCenter = false,
            topLeft = Offset(ex - 13.dp.toPx(), eyeY - 14.dp.toPx()),
            size = Size(26.dp.toPx(), 10.dp.toPx()),
            style = Stroke(width = 4.dp.toPx(), cap = StrokeCap.Round)
        )
    }
    eye(cx - spacing)
    eye(cx + spacing)
    drawCircle(
        color = Color(0xFF81D4FA),
        radius = 3.5.dp.toPx(),
        center = Offset(cx + spacing + 12.dp.toPx(), eyeY + 10.dp.toPx())
    )
}

private fun DrawScope.drawStrictEyes(cx: Float, spacing: Float, eyeY: Float, blink: Float) {
    // Con ngươi nhìn lên + "lông mày" chéo xuống
    fun eye(ex: Float, dir: Int) {
        drawEyeBase(ex, eyeY, blink, pupilDy = -4.dp.toPx())
        drawLine(
            color = InkGray,
            start = Offset(ex - 9.dp.toPx(), eyeY - 18.dp.toPx() + dir * 2.dp.toPx()),
            end = Offset(ex + 9.dp.toPx(), eyeY - 14.dp.toPx() - dir * 2.dp.toPx()),
            strokeWidth = 4.dp.toPx(),
            cap = StrokeCap.Round
        )
    }
    eye(cx - spacing, 1)
    eye(cx + spacing, -1)
}

private fun DrawScope.drawDispleasedEyes(cx: Float, spacing: Float, eyeY: Float, blink: Float) {
    // Con ngươi nhìn chéo ra ngoài (hờn dỗi)
    drawEyeBase(cx - spacing, eyeY, blink, pupilDx = -3.dp.toPx(), pupilDy = 3.dp.toPx())
    drawEyeBase(cx + spacing, eyeY, blink, pupilDx = 3.dp.toPx(), pupilDy = 3.dp.toPx())
}

private fun DrawScope.drawSleepyEyes(cx: Float, spacing: Float, eyeY: Float, blink: Float) {
    // Mí sụp che nửa mắt
    fun eye(ex: Float) {
        drawEyeBase(ex, eyeY, blink, pupilDy = 3.dp.toPx())
        drawLine(
            color = InkGray,
            start = Offset(ex - 14.dp.toPx(), eyeY - 6.dp.toPx()),
            end = Offset(ex + 14.dp.toPx(), eyeY - 6.dp.toPx()),
            strokeWidth = 4.dp.toPx(),
            cap = StrokeCap.Round
        )
    }
    eye(cx - spacing)
    eye(cx + spacing)
}

private fun DrawScope.drawSleepingEyes(cx: Float, spacing: Float, eyeY: Float) {
    // Mắt nhắm khi ngủ: hai đường cong êm (⌒⌒)
    fun closed(ex: Float) {
        drawArc(
            color = InkGray,
            startAngle = 180f,
            sweepAngle = 180f,
            useCenter = false,
            topLeft = Offset(ex - 10.dp.toPx(), eyeY - 4.dp.toPx()),
            size = Size(20.dp.toPx(), 10.dp.toPx()),
            style = Stroke(width = 4.dp.toPx(), cap = StrokeCap.Round)
        )
    }
    closed(cx - spacing)
    closed(cx + spacing)
}

// ==================== Miệng ====================

private fun DrawScope.drawSmileMouth(cx: Float, mouthY: Float, big: Boolean = false) {
    val w = if (big) 30.dp.toPx() else 20.dp.toPx()
    val h = if (big) 14.dp.toPx() else 8.dp.toPx()
    drawArc(
        color = MouthRed,
        startAngle = 0f,
        sweepAngle = 180f,
        useCenter = false,
        topLeft = Offset(cx - w, mouthY - h),
        size = Size(w * 2, h * 2),
        style = Stroke(width = 4.dp.toPx(), cap = StrokeCap.Round)
    )
}

private fun DrawScope.drawTalkingMouth(cx: Float, mouthY: Float, amplitude: Float) {
    // Miệng mở đóng theo nhịp âm lượng, bên trong có lưỡi hồng
    val openH = (6.dp.toPx() + amplitude * 16.dp.toPx()).coerceAtMost(24.dp.toPx())
    val w = 40.dp.toPx()
    drawOval(
        color = MouthRedDark,
        topLeft = Offset(cx - w / 2f, mouthY - openH / 2f),
        size = Size(w, openH)
    )
    if (openH > 10.dp.toPx()) {
        drawOval(
            color = Color(0xFFF48FB1),
            topLeft = Offset(cx - w * 0.3f, mouthY + openH * 0.1f),
            size = Size(w * 0.6f, openH * 0.5f)
        )
    }
}

private fun DrawScope.drawSadMouth(cx: Float, mouthY: Float) {
    // Miệng cong xuống (∩)
    drawArc(
        color = MouthRed,
        startAngle = 180f,
        sweepAngle = 180f,
        useCenter = false,
        topLeft = Offset(cx - 12.dp.toPx(), mouthY - 10.dp.toPx()),
        size = Size(24.dp.toPx(), 12.dp.toPx()),
        style = Stroke(width = 4.dp.toPx(), cap = StrokeCap.Round)
    )
}

private fun DrawScope.drawPoutMouth(cx: Float, mouthY: Float) {
    // Miệng bĩu hờn dỗi
    drawArc(
        color = MouthRed,
        startAngle = 0f,
        sweepAngle = 220f,
        useCenter = false,
        topLeft = Offset(cx - 6.dp.toPx(), mouthY - 6.dp.toPx()),
        size = Size(18.dp.toPx(), 12.dp.toPx()),
        style = Stroke(width = 4.dp.toPx(), cap = StrokeCap.Round)
    )
}

private fun DrawScope.drawStraightMouth(cx: Float, mouthY: Float) {
    // Miệng mím thẳng, nghiêm nghị
    drawLine(
        color = MouthRed,
        start = Offset(cx - 13.dp.toPx(), mouthY + 2.dp.toPx()),
        end = Offset(cx + 13.dp.toPx(), mouthY + 2.dp.toPx()),
        strokeWidth = 4.dp.toPx(),
        cap = StrokeCap.Round
    )
}

private fun DrawScope.drawSurprisedMouth(cx: Float, mouthY: Float) {
    // Miệng tròn chữ "o" ngạc nhiên
    drawOval(
        color = MouthRedDark,
        topLeft = Offset(cx - 8.dp.toPx(), mouthY - 4.dp.toPx()),
        size = Size(16.dp.toPx(), 16.dp.toPx())
    )
}

private fun DrawScope.drawYawnMouth(cx: Float, mouthY: Float) {
    // Miệng ngáp: oval to, màu nhạt
    drawOval(
        color = MouthRed.copy(alpha = 0.8f),
        topLeft = Offset(cx - 11.dp.toPx(), mouthY - 8.dp.toPx()),
        size = Size(22.dp.toPx(), 16.dp.toPx())
    )
}

private fun DrawScope.drawSleepingMouth(cx: Float, mouthY: Float) {
    // Khi ngủ: miệng nhỏ thả lỏng
    drawArc(
        color = MouthRed.copy(alpha = 0.6f),
        startAngle = 0f,
        sweepAngle = 150f,
        useCenter = false,
        topLeft = Offset(cx - 8.dp.toPx(), mouthY - 4.dp.toPx()),
        size = Size(16.dp.toPx(), 8.dp.toPx()),
        style = Stroke(width = 3.dp.toPx(), cap = StrokeCap.Round)
    )
}

// ==================== Tay & màu sắc ====================

/** Tư thế tay theo cảm xúc/năng lượng: giơ cao, giơ ngang, chống hông, rủ xuống. */
private fun DrawScope.handOffsets(
    emotion: RobotEmotion,
    state: ConnectionState,
    cx: Float,
    headY: Float,
    bodyTop: Float,
    bodyH: Float,
): Pair<Offset, Offset> {
    val restY = bodyTop + 22.dp.toPx()
    val hangY = bodyTop + bodyH + 4.dp.toPx()
    val sideX = 88.dp.toPx()
    val upX = 106.dp.toPx()

    return when {
        emotion.energy == "excited" ||
            (emotion.emotion == "happy" && state == ConnectionState.SPEAKING) ->
            Offset(cx - upX, headY - 36.dp.toPx()) to Offset(cx + upX, headY - 36.dp.toPx())
        emotion.emotion == "happy" ->
            Offset(cx - upX, headY + 6.dp.toPx()) to Offset(cx + upX, headY + 6.dp.toPx())
        emotion.emotion == "surprised" ->
            Offset(cx - 96.dp.toPx(), headY + 30.dp.toPx()) to Offset(cx + 96.dp.toPx(), headY + 30.dp.toPx())
        emotion.emotion == "strict" ->
            Offset(cx - 64.dp.toPx(), restY) to Offset(cx + 64.dp.toPx(), restY)
        emotion.emotion == "sad" || isLowEnergy(emotion) || state == ConnectionState.SLEEPING ->
            Offset(cx - sideX, hangY) to Offset(cx + sideX, hangY)
        else ->
            Offset(cx - sideX, restY) to Offset(cx + sideX, restY)
    }
}

private fun isLowEnergy(emotion: RobotEmotion): Boolean =
    emotion.energy == "sleepy" || emotion.energy == "drowsy" || emotion.energy == "tired"

/** Màu chuông cổ theo cảm xúc Robo, fallback theo trạng thái trò chuyện. */
private fun emotionBellColor(emotion: RobotEmotion, state: ConnectionState): Color =
    when (emotion.emotion) {
        "happy" -> if (emotion.energy == "excited") Color(0xFFF472B6)
        else Color(0xFF34D399)
        "surprised" -> Color(0xFFA78BFA)
        "strict" -> Color(0xFFF59E0B)
        "displeased" -> Color(0xFFFB7185)
        "sad" -> Color(0xFF94A3B8)
        else -> when (state) {
            ConnectionState.LISTENING -> Color(0xFF10B981)
            ConnectionState.THINKING -> Color(0xFFF59E0B)
            ConnectionState.SPEAKING -> Color(0xFF06B6D4)
            else -> Color(0xFFFFC107)
        }
    }

// ==================== Bảng màu Doraemon ====================

private val DoraemonBlue = Color(0xFF1E88E5)
private val DoraemonWhite = Color(0xFFFDFDFD)
private val MouthRed = Color(0xFFE53935)
private val MouthRedDark = Color(0xFFB71C1C)
private val BellRed = Color(0xFFD32F2F)
private val InkGray = Color(0xFF37474F)
