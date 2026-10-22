package com.example.digitalhuman.audio

import android.media.AudioAttributes
import android.media.AudioFormat
import android.media.AudioTrack
import android.util.Log
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
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
 * - Audio Stream: USAGE_VOICE_COMMUNICATION (chuẩn VoIP đồng bộ với AudioRecord)
 * - Báo cáo trạng thái đang phát chính xác, loại bỏ hoàn toàn hiện tượng tự ngắt tiếng.
 */
class AudioPlayer(
    private val onOutputAmplitude: (Float) -> Unit = {},
    private val onPlaybackStateChanged: (Boolean) -> Unit = {}
) {
    companion object {
        private const val TAG = "AudioPlayer"
        const val SAMPLE_RATE = 24000
        const val CHANNEL_CONFIG = AudioFormat.CHANNEL_OUT_MONO
        const val AUDIO_FORMAT = AudioFormat.ENCODING_PCM_16BIT

        // Pre-buffer ~80ms audio trước khi phát để chống rách tiếng & jitter trên mạng WAN/VPS.
        private const val BYTES_PER_SECOND = SAMPLE_RATE * 2
        private const val MIN_PREBUFFER_BYTES = BYTES_PER_SECOND * 80 / 1000

        // Timeout pre-buffer tối đa để bắt đầu phát ngay cả khi stream chậm (120ms).
        private const val MAX_PREBUFFER_WAIT_MS = 120L

        // Chu kỳ chờ xả sạch phần cứng sau khi nhận turn_complete từ server (~100ms).
        private const val HARDWARE_DRAIN_CYCLES = 10

        // Khuếch đại âm lượng phát lại: 1.8x để giọng Doraemon to rõ nhưng không bị méo tiếng.
        private const val VOLUME_GAIN = 1.8f

        // Nếu mạng dồn quá nhiều audio, hàng đợi phát lại sẽ nghe như lặp nội dung cũ.
        private const val MAX_PENDING_BYTES = BYTES_PER_SECOND * 8

        // Sau khi bé ngắt lời, bỏ các chunk của lượt cũ còn đang bay tới.
        // Không có cửa sổ này, loa sẽ phát tiếp nửa câu vừa bị ngắt.
        private const val INTERRUPT_SUPPRESS_MS = 400L
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
    private var preBufferStartedAt = 0L

    @Volatile
    private var isServerTurnComplete = false

    @Volatile
    private var suppressIncomingUntilMs = 0L

    private val pendingBytes = AtomicInteger(0)

    private fun initAudioTrack(): Boolean {
        try {
            audioTrack?.release()
        } catch (_: Exception) {}

        return try {
            val minBufferSize = AudioTrack.getMinBufferSize(SAMPLE_RATE, CHANNEL_CONFIG, AUDIO_FORMAT)
            audioTrack = AudioTrack.Builder()
                .setAudioAttributes(
                    AudioAttributes.Builder()
                        .setUsage(AudioAttributes.USAGE_VOICE_COMMUNICATION)
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
                .setBufferSizeInBytes(maxOf(minBufferSize * 2, BYTES_PER_SECOND / 2))
                .setTransferMode(AudioTrack.MODE_STREAM)
                .build()

            audioTrack?.setVolume(AudioTrack.getMaxVolume())
            audioTrack?.play()
            true
        } catch (e: Exception) {
            Log.e(TAG, "Failed to initialize AudioTrack: ${e.message}")
            false
        }
    }

    fun start(scope: CoroutineScope) {
        if (isPlaying) return
        initAudioTrack()
        isPlaying = true

        playbackJob = scope.launch(Dispatchers.IO) {
            var silentCycles = 0
            isPreBuffering = true
            preBufferStartedAt = System.currentTimeMillis()

            while (isActive && isPlaying) {
                // 1. Giai đoạn Pre-buffering: đệm đủ ~180ms hoặc chờ tối đa MAX_PREBUFFER_WAIT_MS
                if (isPreBuffering) {
                    val waited = System.currentTimeMillis() - preBufferStartedAt
                    if (pendingBytes.get() >= MIN_PREBUFFER_BYTES || waited >= MAX_PREBUFFER_WAIT_MS || (isServerTurnComplete && audioQueue.isNotEmpty())) {
                        isPreBuffering = false
                    } else {
                        delay(10)
                        continue
                    }
                }

                // 2. Lấy audio chunk từ hàng đợi
                val chunk = audioQueue.poll()
                if (chunk != null && chunk.isNotEmpty()) {
                    pendingBytes.addAndGet(-chunk.size)
                    if (!isCurrentlyPlayingAudio) {
                        isCurrentlyPlayingAudio = true
                        onPlaybackStateChanged(true)
                    }
                    silentCycles = 0

                    val gainedChunk = applyGain(chunk)
                    var written = audioTrack?.write(gainedChunk, 0, gainedChunk.size) ?: 0
                    if (written < 0) {
                        Log.w(TAG, "AudioTrack write error: $written, reinitializing...")
                        initAudioTrack()
                        written = audioTrack?.write(gainedChunk, 0, gainedChunk.size) ?: 0
                    }

                    // Tính biên độ âm lượng nhép môi Doraemon
                    val amplitude = calculateRMS(chunk)
                    onOutputAmplitude(amplitude)
                } else {
                    onOutputAmplitude(0f)
                    if (isCurrentlyPlayingAudio) {
                        silentCycles++
                        // CHỈ kết thúc lượt phát khi VÀ CHỈ KHI server đã báo turn_complete
                        // VÀ hàng đợi đã xả sạch phần cứng trong ít nhất HARDWARE_DRAIN_CYCLES (250ms).
                        // TUYỆT ĐỐI KHÔNG tự ý ngắt lượt phát giữa chừng khi server đang xử lý Tool / tìm kiếm.
                        if (isServerTurnComplete && silentCycles >= HARDWARE_DRAIN_CYCLES) {
                            isCurrentlyPlayingAudio = false
                            isServerTurnComplete = false
                            onPlaybackStateChanged(false)
                            silentCycles = 0
                            isPreBuffering = true
                            preBufferStartedAt = System.currentTimeMillis()
                        }
                    }
                    delay(10)
                }
            }
        }
    }

    fun enqueueAudio(data: ByteArray) {
        var wasIdle: Boolean
        // Cùng một lock với stopAndFlush(): một chunk đang tới đúng lúc bé ngắt
        // lời không thể lọt vào hàng đợi sau khi đã flush.
        synchronized(this) {
            if (System.currentTimeMillis() < suppressIncomingUntilMs) {
                Log.d(TAG, "Dropping stale audio chunk after interruption (${data.size} bytes)")
                return
            }
            if (pendingBytes.get() + data.size > MAX_PENDING_BYTES) {
                Log.w(TAG, "Audio backlog too large; flushing stale queue")
                audioQueue.clear()
                pendingBytes.set(0)
            }

            wasIdle = audioQueue.isEmpty() && pendingBytes.get() == 0 && !isCurrentlyPlayingAudio
            isServerTurnComplete = false
            audioQueue.add(data)
            pendingBytes.addAndGet(data.size)
        }

        if (wasIdle) {
            isPreBuffering = true
            preBufferStartedAt = System.currentTimeMillis()
            isCurrentlyPlayingAudio = true
            onPlaybackStateChanged(true)
        }
    }

    /**
     * Báo cho player biết server đã kết thúc gửi dữ liệu cho lượt này (turn_complete).
     */
    fun notifyTurnComplete() {
        isServerTurnComplete = true
        if (audioQueue.isEmpty() && pendingBytes.get() == 0 && !isCurrentlyPlayingAudio) {
            onPlaybackStateChanged(false)
        }
    }

    /**
     * Bé ngắt lời: dừng phát ngay và bỏ luôn các chunk của lượt cũ còn đang
     * bay tới. Không có bước này, loa sẽ phát tiếp phần còn lại của câu vừa bị
     * ngắt rồi mới trả lời lượt mới — nghe như robot nói lặp.
     */
    fun beginInterruption() {
        suppressIncomingUntilMs = System.currentTimeMillis() + INTERRUPT_SUPPRESS_MS
        stopAndFlush()
    }

    /**
     * Dừng ngay lập tức khi bé ngắt lời (Barge-in / Interrupt) hoặc phiên kết thúc.
     */
    fun stopAndFlush() {
        synchronized(this) {
            audioQueue.clear()
            pendingBytes.set(0)
            isPreBuffering = true
            isServerTurnComplete = false
            try {
                if (audioTrack?.state == AudioTrack.STATE_INITIALIZED) {
                    audioTrack?.pause()
                    audioTrack?.flush()
                    audioTrack?.play()
                }
            } catch (e: Exception) {
                Log.e(TAG, "Error in stopAndFlush: ${e.message}")
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
        return (rms * 4.0f).coerceIn(0.0f, 1.0f)
    }
}

