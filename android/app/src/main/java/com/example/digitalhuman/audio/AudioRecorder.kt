package com.example.digitalhuman.audio

import android.annotation.SuppressLint
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlin.math.sqrt

/**
 * Thu âm giọng nói từ Micro của Android theo chuẩn Gemini Live API:
 * - Sample Rate: 16,000 Hz (16kHz)
 * - Channel: Mono (1 kênh)
 * - Encoding: PCM 16-bit (Little Endian)
 * - Tích hợp bộ ngắt khoảng lặng thông minh (Smart VAD Silence Gate) 1.2s
 */
class AudioRecorder(
    private val onAudioChunk: (ByteArray) -> Unit,
    private val onInputVolume: (Float) -> Unit = {},
    private val onSpeechStarted: () -> Unit = {},
    private val onSpeechEnded: () -> Unit = {}
) {
    companion object {
        const val SAMPLE_RATE = 16000
        const val CHANNEL_CONFIG = AudioFormat.CHANNEL_IN_MONO
        const val AUDIO_FORMAT = AudioFormat.ENCODING_PCM_16BIT
        const val CHUNK_SIZE = 3200 // ~100ms
        const val SPEECH_THRESHOLD = 0.02f
        const val SILENCE_TIMEOUT_MS = 1200L // 1.2 giây dừng nói
    }

    private var audioRecord: AudioRecord? = null
    private var recordingJob: Job? = null
    private var isRecording = false

    private var isUserSpeaking = false
    private var lastSpeechTime = 0L
    private var silencePadding = 0

    @SuppressLint("MissingPermission")
    fun startRecording(scope: CoroutineScope) {
        if (isRecording) return

        val minBufferSize = AudioRecord.getMinBufferSize(SAMPLE_RATE, CHANNEL_CONFIG, AUDIO_FORMAT)
        val bufferSize = maxOf(minBufferSize, CHUNK_SIZE * 2)

        audioRecord = AudioRecord(
            MediaRecorder.AudioSource.VOICE_COMMUNICATION,
            SAMPLE_RATE,
            CHANNEL_CONFIG,
            AUDIO_FORMAT,
            bufferSize
        )

        if (audioRecord?.state != AudioRecord.STATE_INITIALIZED) {
            audioRecord?.release()
            audioRecord = null
            return
        }

        audioRecord?.startRecording()
        isRecording = true
        isUserSpeaking = false
        lastSpeechTime = 0L

        recordingJob = scope.launch(Dispatchers.IO) {
            val buffer = ByteArray(CHUNK_SIZE)
            while (isActive && isRecording) {
                val readBytes = audioRecord?.read(buffer, 0, buffer.size) ?: 0
                if (readBytes > 0) {
                    val chunk = buffer.copyOf(readBytes)
                    val volume = calculateRMS(chunk)
                    onInputVolume(volume)

                    val now = System.currentTimeMillis()

                    if (volume > SPEECH_THRESHOLD) {
                        // Bé đang nói
                        lastSpeechTime = now
                        silencePadding = 5
                        if (!isUserSpeaking) {
                            isUserSpeaking = true
                            onSpeechStarted()
                        }
                        onAudioChunk(chunk)
                    } else {
                        // Bé tạm dừng nói
                        if (isUserSpeaking) {
                            if (now - lastSpeechTime < SILENCE_TIMEOUT_MS) {
                                if (silencePadding > 0) {
                                    silencePadding--
                                    onAudioChunk(chunk)
                                }
                            } else {
                                // Đã dừng nói 1.2s -> Kích hoạt suy nghĩ và ngắt gửi silence
                                isUserSpeaking = false
                                onSpeechEnded()
                            }
                        }
                    }
                }
            }
        }
    }

    fun stopRecording() {
        isRecording = false
        recordingJob?.cancel()
        recordingJob = null
        try {
            audioRecord?.stop()
            audioRecord?.release()
        } catch (e: Exception) {
            e.printStackTrace()
        }
        audioRecord = null
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
