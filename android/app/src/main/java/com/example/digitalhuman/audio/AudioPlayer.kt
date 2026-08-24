package com.example.digitalhuman.audio

import android.media.AudioAttributes
import android.media.AudioFormat
import android.media.AudioTrack
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
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
    }

    private var audioTrack: AudioTrack? = null
    private val audioQueue = ConcurrentLinkedQueue<ByteArray>()
    private var playbackJob: Job? = null
    private var isPlaying = false

    @Volatile
    var isCurrentlyPlayingAudio = false
        private set

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
            while (isActive && isPlaying) {
                val chunk = audioQueue.poll()
                if (chunk != null && chunk.isNotEmpty()) {
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
                        // Sau ~100ms không có thêm audio chunk mới -> Hoàn tất phát
                        if (silentCycles > 10) {
                            isCurrentlyPlayingAudio = false
                            onPlaybackStateChanged(false)
                            silentCycles = 0
                        }
                    }
                    Thread.sleep(10)
                }
            }
        }
    }

    fun enqueueAudio(data: ByteArray) {
        audioQueue.add(data)
    }

    /**
     * Dừng ngay lập tức khi bé ngắt lời (Barge-in / Interrupt)
     */
    fun stopAndFlush() {
        audioQueue.clear()
        try {
            audioTrack?.pause()
            audioTrack?.flush()
            audioTrack?.play()
        } catch (e: Exception) {
            e.printStackTrace()
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

