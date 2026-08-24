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

        // Pre-buffer mục tiêu ~150ms audio trước khi phát để chống rách tiếng do jitter mạng.
        private const val BYTES_PER_SECOND = SAMPLE_RATE * 2
        private const val MIN_PREBUFFER_BYTES = BYTES_PER_SECOND * 150 / 1000

        // Không chờ pre-buffer quá lâu để giữ độ trễ hội thoại ở mức thấp.
        private const val MAX_PREBUFFER_WAIT_MS = 250L
    }

    private var audioTrack: AudioTrack? = null
    private val audioQueue = ConcurrentLinkedQueue<ByteArray>()
    private var playbackJob: Job? = null
    @Volatile
    private var isPlaying = false

    @Volatile
    var isCurrentlyPlayingAudio = false
        private set

    @Volatile
    private var isPreBuffering = true

    private val pendingBytes = AtomicInteger(0)

    fun start(scope: CoroutineScope) {
        if (isPlaying) return

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
            .setBufferSizeInBytes(minBufferSize * 2)
            .setTransferMode(AudioTrack.MODE_STREAM)
            .build()

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

                    audioTrack?.write(chunk, 0, chunk.size)

                    // Tính biên độ âm lượng để nhép môi Robot
                    val amplitude = calculateRMS(chunk)
                    onOutputAmplitude(amplitude)
                } else {
                    onOutputAmplitude(0f)
                    if (isCurrentlyPlayingAudio) {
                        silentCycles++
                        // Sau ~100ms không có thêm audio chunk mới -> Hoàn tất phát lượt
                        if (silentCycles > 10) {
                            isCurrentlyPlayingAudio = false
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
        audioQueue.add(data)
        pendingBytes.addAndGet(data.size)
    }

    /**
     * Dừng ngay lập tức khi bé ngắt lời (Barge-in / Interrupt)
     */
    fun stopAndFlush() {
        synchronized(this) {
            audioQueue.clear()
            pendingBytes.set(0)
            isPreBuffering = true
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

    private fun calculateRMS(audioData: ByteArray): Float {
        var sum = 0.0
        val shortCount = audioData.size / 2
        for (i in 0 until shortCount) {
            val sample = (audioData[i * 2].toInt() and 0xFF) or (audioData[i * 2 + 1].toInt() shl 8)
            val normalized = sample.toShort() / 32768.0f
            sum += normalized * normalized
        }
        val rms = sqrt(sum / shortCount).toFloat()
        return (rms * 3.5f).coerceIn(0.0f, 1.0f)
    }
}

