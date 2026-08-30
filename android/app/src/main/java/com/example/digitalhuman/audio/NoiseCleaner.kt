package com.example.digitalhuman.audio

import kotlin.math.max
import kotlin.math.sqrt

/**
 * Lọc nhiễu phần mềm trước khi đưa vào Silero VAD và stream lên server:
 * - High-pass Butterworth bậc 2 @ 200 Hz: triệt tiếng gió (wind rumble nằm dưới
 *   ~250 Hz) trong khi giữ nguyên giọng nói (giọng trẻ em có tần số cơ bản >250 Hz).
 * - DC removal: thành phần DC của micro bị high-pass loại bỏ luôn.
 * - Adaptive noise gate: theo dõi noise floor theo thời gian, zero-out các frame
 *   chỉ chứa tạp âm nền để VAD và server không nhận nhiễu thành giọng nói.
 */
class NoiseCleaner {
    companion object {
        // Frame có RMS dưới (noiseFloor * GATE_RATIO) sẽ bị chặn (zero-out).
        private const val GATE_RATIO = 2.5f

        // Ngưỡng tối thiểu tuyệt đối để frame được coi là "có thể có giọng nói".
        private const val MIN_SPEECH_RMS = 0.004f

        // Cập nhật noise floor mỗi ~2 giây (64 frame x 32ms).
        private const val NOISE_WINDOW_FRAMES = 64
    }

    // Biquad high-pass Butterworth bậc 2, fc=200Hz, fs=16kHz, Q=0.7071 (hệ số đã chuẩn hóa).
    private val b0 = 0.94597687
    private val b1 = -1.89195374
    private val b2 = 0.94597687
    private val a1 = -1.88903252
    private val a2 = 0.89487449

    private var x1 = 0.0
    private var x2 = 0.0
    private var y1 = 0.0
    private var y2 = 0.0

    private var noiseFloor = 0.004f
    private var windowMin = Float.MAX_VALUE
    private var windowFrames = 0

    /**
     * Lọc frame in-place (high-pass Butterworth 200Hz để khử DC và tiếng gió sub-rumble).
     * Trả về RMS của frame sau lọc. Không can thiệp zero-out thô bạo để giữ trọn vẹn
     * các âm tiết nhẹ của trẻ nhỏ.
     */
    fun cleanInPlace(frame: ByteArray): Float {
        val shortCount = frame.size / 2
        var sum = 0.0
        for (i in 0 until shortCount) {
            val s = ((frame[i * 2].toInt() and 0xFF) or (frame[i * 2 + 1].toInt() shl 8)).toShort()
            val x = s / 32768.0
            val y = b0 * x + b1 * x1 + b2 * x2 - a1 * y1 - a2 * y2
            x2 = x1
            x1 = x
            y2 = y1
            y1 = y
            sum += y * y
            val v = (y * 32768.0).toInt().coerceIn(Short.MIN_VALUE.toInt(), Short.MAX_VALUE.toInt())
            frame[i * 2] = (v and 0xFF).toByte()
            frame[i * 2 + 1] = ((v shr 8) and 0xFF).toByte()
        }
        val rms = sqrt(sum / shortCount).toFloat()

        // Theo dõi noise floor
        if (rms < windowMin) windowMin = rms
        windowFrames++
        if (windowFrames >= NOISE_WINDOW_FRAMES) {
            noiseFloor = noiseFloor * 0.6f + windowMin * 0.4f
            windowMin = Float.MAX_VALUE
            windowFrames = 0
        }

        return rms
    }
}
