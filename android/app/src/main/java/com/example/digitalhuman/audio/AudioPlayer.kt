package com.example.digitalhuman.audio

import android.media.AudioAttributes
import android.media.AudioFormat
import android.media.AudioTrack
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import java.util.concurrent.atomic.AtomicInteger
import java.util.concurrent.ConcurrentLinkedQueue
import kotlin.math.sqrt

/**
 * Phát âm thanh phản hồi từ Gemini Live API:
 * - Sample Rate: 24,000 Hz (24kHz)
 * - Channel: Mono
 * - Encoding: PCM 16-bit
 * - Báo cáo trạng thái đang phát (playback state) chính xác cho Echo Gating.
 * - Tính toán biên độ âm lượng thời gian thực để cử động môi Robot.
 */
class AudioPlayer(
    private val onOutputAmplitude: (Float) -> Unit = {},
    private val onPlaybackStateChanged: (Boolean) -> Unit = {}
) {
    companion object {
        const val SAMPLE_RATE = 24000
        const val CHANNEL_CONFIG = AudioFormat.CHANNEL_OUT_MONO
        const val AUDIO_FORMAT = AudioFormat.ENCODING_PCM_16BIT

        // Pre-buffer mục tiêu ~80ms audio trước khi phát để chống rách tiếng mà vẫn đảm bảo phản hồi tức thì.
        private const val BYTES_PER_SECOND = SAMPLE_RATE * 2
        private const val MIN_PREBUFFER_BYTES = BYTES_PER_SECOND * 80 / 1000

        // Timeout pre-buffer ngắn để giảm độ trễ khởi đầu giọng nói.
        private const val MAX_PREBUFFER_WAIT_MS = 120L

        // Khoảng lặng để xả sạch buffer khi Gemini đang tạm dừng giữa câu (~200ms).
        private const val SILENT_CYCLES_TO_FINISH = 20

        // Khi server đã báo turn_complete, chỉ cần chờ ~80ms (8 cycles) để xả nốt phần cứng rồi mở mic ngay.
        private const val SHORT_SILENT_CYCLES_AFTER_TURN_COMPLETE = 8

        // Khuếch đại âm lượng phát lại: 2.0x để giọng Doraemon phát ra loa ngoài to rõ, trong trẻo.
        private const val VOLUME_GAIN = 2.0f
    }

    private var audioTrack: AudioTrack? = null
    private val audioQueue = ConcurrentLinkedQueue<ByteArray>()
    private var playbackJob: Job? = null
    @Volatile
    private var isPlaying = false

    @Volatile
    var isCurrentlyPlayingAudio = false
        private set

    val isPlayingOrPending: Boolean
        get() = isCurrentlyPlayingAudio || pendingBytes.get() > 0 || audioQueue.isNotEmpty()

    @Volatile
    private var isPreBuffering = true

    @Volatile
    private var isServerTurnComplete = false

    private val pendingBytes = AtomicInteger(0)

    fun start(scope: CoroutineScope) {
        if (isPlaying) return

        val minBufferSize = AudioTrack.getMinBufferSize(SAMPLE_RATE, CHANNEL_CONFIG, AUDIO_FORMAT)

        audioTrack = AudioTrack.Builder()
            .setAudioAttributes(
                AudioAttributes.Builder()
                    .setUsage(AudioAttributes.USAGE_MEDIA)
                    .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH)
                    .build()
            )
            .setAudioFormat(
                AudioFormat.Builder()
                    .setSampleRate(SAMPLE_RATE)
                    .setChannelMask(CHANNEL_CONFIG)
                    .setEncoding(AUDIO_FORMAT)
                    .build()
            )
            .setBufferSizeInBytes(minBufferSize * 2)
            .setTransferMode(AudioTrack.MODE_STREAM)
            .build()

        audioTrack?.setVolume(AudioTrack.getMaxVolume())
        audioTrack?.play()
        isPlaying = true

        playbackJob = scope.launch(Dispatchers.IO) {
            var silentCycles = 0
            isPreBuffering = true
            var preBufferStartedAt = System.currentTimeMillis()
            while (isActive && isPlaying) {
                // Pre-buffer đủ ~150ms hoặc hết timeout trước khi phát để triệt tiêu hiện tượng rách âm do độ trễ mạng.
                if (isPreBuffering) {
                    val waited = System.currentTimeMillis() - preBufferStartedAt
                    if (pendingBytes.get() >= MIN_PREBUFFER_BYTES || waited >= MAX_PREBUFFER_WAIT_MS) {
                        isPreBuffering = false
                    } else {
                        kotlinx.coroutines.delay(10)
                        continue
                    }
                }

                val chunk = audioQueue.poll()
                if (chunk != null && chunk.isNotEmpty()) {
                    pendingBytes.addAndGet(-chunk.size)
                    if (!isCurrentlyPlayingAudio) {
                        isCurrentlyPlayingAudio = true
                        onPlaybackStateChanged(true)
                    }
                    silentCycles = 0

                    audioTrack?.write(applyGain(chunk), 0, chunk.size)

                    // Tính biên độ âm lượng để nhép môi Robot
                    val amplitude = calculateRMS(chunk)
                    onOutputAmplitude(amplitude)
                } else {
                    onOutputAmplitude(0f)
                    if (isCurrentlyPlayingAudio) {
                        silentCycles++
                        // Nếu server đã báo turn_complete thì chỉ cần xả nhanh (SHORT_SILENT_CYCLES_AFTER_TURN_COMPLETE = 80ms)
                        // Nếu đang stream dở thì đợi 200ms để tránh ngắt giữa câu.
                        val finishThreshold = if (isServerTurnComplete) {
                            SHORT_SILENT_CYCLES_AFTER_TURN_COMPLETE
                        } else {
                            SILENT_CYCLES_TO_FINISH
                        }
                        if (silentCycles > finishThreshold) {
                            isCurrentlyPlayingAudio = false
                            isServerTurnComplete = false
                            onPlaybackStateChanged(false)
                            silentCycles = 0
                            isPreBuffering = true
                            preBufferStartedAt = System.currentTimeMillis()
                        }
                    }
                    kotlinx.coroutines.delay(10)
                }
            }
        }
    }

    fun enqueueAudio(data: ByteArray) {
        isServerTurnComplete = false
        audioQueue.add(data)
        pendingBytes.addAndGet(data.size)
        if (!isCurrentlyPlayingAudio) {
            isCurrentlyPlayingAudio = true
            onPlaybackStateChanged(true)
        }
    }

    /**
     * Báo cho player biết server đã kết thúc turn nói hiện tại (turn_complete).
     * Player sẽ chủ động xả nốt hàng đợi và mở mic tức thì ngay khi phát xong frame cuối.
     */
    fun notifyTurnComplete() {
        isServerTurnComplete = true
        // Nếu hàng đợi đã rỗng hoàn toàn từ trước, mở mic ngay sau một nhịp ngắn
        if (audioQueue.isEmpty() && pendingBytes.get() == 0 && !isCurrentlyPlayingAudio) {
            onPlaybackStateChanged(false)
        }
    }

    /**
     * Dừng ngay lập tức khi bé ngắt lời (Barge-in / Interrupt)
     */
    fun stopAndFlush() {
        synchronized(this) {
            audioQueue.clear()
            pendingBytes.set(0)
            isPreBuffering = true
            isServerTurnComplete = false
            try {
                audioTrack?.pause()
                audioTrack?.flush()
                audioTrack?.play()
            } catch (e: Exception) {
                e.printStackTrace()
            }
        }
        isCurrentlyPlayingAudio = false
        onOutputAmplitude(0f)
        onPlaybackStateChanged(false)
    }

    fun release() {
        isPlaying = false
        isCurrentlyPlayingAudio = false
        playbackJob?.cancel()
        playbackJob = null
        audioQueue.clear()
        pendingBytes.set(0)
        try {
            audioTrack?.stop()
            audioTrack?.release()
        } catch (e: Exception) {
            e.printStackTrace()
        }
        audioTrack = null
        onPlaybackStateChanged(false)
    }

    private fun applyGain(audioData: ByteArray): ByteArray {
        if (VOLUME_GAIN == 1.0f) return audioData
        val result = ByteArray(audioData.size)
        val shortCount = audioData.size / 2
        for (i in 0 until shortCount) {
            val sample = ((audioData[i * 2].toInt() and 0xFF) or (audioData[i * 2 + 1].toInt() shl 8)).toShort()
            val amplified = (sample * VOLUME_GAIN).toInt().coerceIn(Short.MIN_VALUE.toInt(), Short.MAX_VALUE.toInt())
            result[i * 2] = (amplified and 0xFF).toByte()
            result[i * 2 + 1] = ((amplified shr 8) and 0xFF).toByte()
        }
        return result
    }

    private fun calculateRMS(audioData: ByteArray): Float {
        var sum = 0.0
        val shortCount = audioData.size / 2
        for (i in 0 until shortCount) {
            val sample = (audioData[i * 2].toInt() and 0xFF) or (audioData[i * 2 + 1].toInt() shl 8)
            val normalized = sample.toShort() / 32768.0f
            sum += normalized * normalized
        }
        val rms = sqrt(sum / shortCount).toFloat()
        // Map biên độ thật ra thang 0..1 mà KHÔNG kẹp cứng. Giọng Gemini bình thường
        // RMS ~0.05-0.15, đỉnh ~0.3-0.4, nên nhân 4 để dùng được dải động rộng hơn
        // cho lip-sync (trước đây nhân 3.5 + clamp 1.0 làm mép dính ở max).
        return (rms * 4.0f).coerceIn(0.0f, 1.0f)
    }
}

