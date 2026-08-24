package com.example.digitalhuman.audio

import android.annotation.SuppressLint
import android.content.Context
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import android.media.audiofx.AcousticEchoCanceler
import android.media.audiofx.AutomaticGainControl
import android.media.audiofx.NoiseSuppressor
import com.konovalov.vad.silero.Vad
import com.konovalov.vad.silero.VadSilero
import com.konovalov.vad.silero.config.FrameSize
import com.konovalov.vad.silero.config.Mode
import com.konovalov.vad.silero.config.SampleRate
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlin.math.sqrt

/**
 * Thu âm giọng nói từ Micro của Android theo chuẩn Gemini Live API & Google Audio Architecture:
 * - Sample Rate: 16,000 Hz (16kHz)
 * - Channel: Mono (1 kênh)
 * - Encoding: PCM 16-bit (Little Endian)
 * - Tích hợp Hardware Acoustic Echo Canceler (AEC), Noise Suppressor (NS), Automatic Gain Control (AGC).
 * - Sử dụng Silero VAD on-device để phát hiện chính xác lúc người dùng đang nói, thay cho
 *   ngưỡng RMS thủ công trước đây vốn không phân biệt được giọng nói với tiếng loa/tạp âm.
 */
class AudioRecorder(
    private val context: Context,
    private val onAudioChunk: (ByteArray) -> Unit,
    private val onInputVolume: (Float) -> Unit = {},
    private val onSpeechStarted: () -> Unit = {},
    private val onSpeechEnded: () -> Unit = {}
) {
    companion object {
        const val SAMPLE_RATE = 16000
        const val CHANNEL_CONFIG = AudioFormat.CHANNEL_IN_MONO
        const val AUDIO_FORMAT = AudioFormat.ENCODING_PCM_16BIT

        // Silero VAD khuyến nghị frame 512 mẫu (16-bit mono -> 1024 bytes) cho 16kHz.
        private const val VAD_FRAME_SAMPLES = 512
        private const val VAD_FRAME_BYTES = VAD_FRAME_SAMPLES * 2

        // Giữ lại ~300ms audio trước điểm bắt đầu nói để không cắt mất âm tiết đầu.
        // Tương ứng với VAD_PREFIX_PADDING_MS=200 ở backend.
        private const val PRE_ROLL_FRAMES = 9

        // Manual VAD: Gemini server không có prefix padding/silence tolerance — xử lý ngay
        // khi nhận activity_end. Chỉ cần gửi thêm 1-2 frames (~30-60ms) để chắc chắn
        // âm tiết cuối không bị cắt giữa packet. Tăng cao sẽ gây audio thừa bị model xử lý.
        private const val TAIL_FRAMES = 2

        // Fallback khi Silero VAD không khởi tạo được (mất model/ONNX lỗi).
        private const val RMS_FALLBACK_THRESHOLD = 0.05f
    }

    private var audioRecord: AudioRecord? = null
    private var echoCanceler: AcousticEchoCanceler? = null
    private var noiseSuppressor: NoiseSuppressor? = null
    private var gainControl: AutomaticGainControl? = null
    private var vad: VadSilero? = null

    private var recordingJob: Job? = null
    private var isRecording = false

    @Volatile
    var isPlaybackActive = false

    @SuppressLint("MissingPermission")
    fun startRecording(scope: CoroutineScope) {
        if (isRecording) return

        val minBufferSize = AudioRecord.getMinBufferSize(SAMPLE_RATE, CHANNEL_CONFIG, AUDIO_FORMAT)
        val bufferSize = maxOf(minBufferSize, VAD_FRAME_BYTES * 4)

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

        // Kích hoạt chống vọng âm và khử nhiễu phần cứng (Hardware AEC & NS)
        val sessionId = audioRecord?.audioSessionId ?: 0
        if (sessionId != 0) {
            try {
                if (AcousticEchoCanceler.isAvailable()) {
                    echoCanceler = AcousticEchoCanceler.create(sessionId)?.apply { enabled = true }
                }
                if (NoiseSuppressor.isAvailable()) {
                    noiseSuppressor = NoiseSuppressor.create(sessionId)?.apply { enabled = true }
                }
                if (AutomaticGainControl.isAvailable()) {
                    gainControl = AutomaticGainControl.create(sessionId)?.apply { enabled = true }
                }
            } catch (e: Exception) {
                e.printStackTrace()
            }
        }

        vad = try {
            Vad.builder()
                .setContext(context)
                .setSampleRate(SampleRate.SAMPLE_RATE_16K)
                .setFrameSize(FrameSize.FRAME_SIZE_512)
                .setMode(Mode.NORMAL)
                .setSpeechDurationMs(80)
                .setSilenceDurationMs(700)
                .build()
        } catch (e: Exception) {
            e.printStackTrace()
            null
        }

        audioRecord?.startRecording()
        isRecording = true

        recordingJob = scope.launch(Dispatchers.IO) {
            val frame = ByteArray(VAD_FRAME_BYTES)
            val preRoll = ArrayDeque<ByteArray>(PRE_ROLL_FRAMES + 1)
            var userSpeaking = false
            var tailFrames = 0
            var frameOffset = 0

            while (isActive && isRecording) {
                // Đọc đủ đúng 1024 byte (512 mẫu) cho Silero VAD; AudioRecord có thể
                // trả về ít hơn yêu cầu nên phải tích lũy cho đến khi đủ một frame.
                val readBytes = audioRecord?.read(frame, frameOffset, frame.size - frameOffset) ?: 0
                if (readBytes <= 0) continue

                frameOffset += readBytes
                if (frameOffset < frame.size) continue
                frameOffset = 0
                val frameData = frame.copyOf()

                // Âm lượng hiển thị (RMS chỉ dùng cho UI, không dùng để quyết định gửi audio).
                val rawRms = calculateRawRMS(frameData)
                onInputVolume((rawRms * 4.0f).coerceIn(0.0f, 1.0f))

                // Silero VAD phát hiện giọng nói; fallback RMS nếu VAD không khả dụng.
                val isSpeech = vad?.isSpeech(frameData) ?: (rawRms > RMS_FALLBACK_THRESHOLD)

                if (isSpeech) {
                    if (!userSpeaking) {
                        userSpeaking = true
                        tailFrames = 0

                        // Gửi pre-roll để server không bị mất âm tiết đầu tiên.
                        while (preRoll.isNotEmpty()) {
                            onAudioChunk(preRoll.removeFirst())
                        }
                        onSpeechStarted()
                    }
                    onAudioChunk(frameData)
                } else if (userSpeaking) {
                    // Kéo dài một đoạn đuôi sau khi hết nói để server kết thúc lượt tự nhiên.
                    onAudioChunk(frameData)
                    tailFrames++
                    if (tailFrames >= TAIL_FRAMES) {
                        userSpeaking = false
                        tailFrames = 0
                        onSpeechEnded()
                    }
                } else {
                    // Đang im lặng: chỉ đệm pre-roll, không gửi liên tục.
                    // Khi loa đang phát, không đệm tiếng vọng của robot để tránh echo khi barge-in.
                    if (!isPlaybackActive) {
                        preRoll.addLast(frameData)
                        while (preRoll.size > PRE_ROLL_FRAMES) {
                            preRoll.removeFirst()
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
            vad?.close()
            vad = null

            echoCanceler?.release()
            echoCanceler = null
            noiseSuppressor?.release()
            noiseSuppressor = null
            gainControl?.release()
            gainControl = null

            audioRecord?.stop()
            audioRecord?.release()
        } catch (e: Exception) {
            e.printStackTrace()
        }
        audioRecord = null
    }

    private fun calculateRawRMS(audioData: ByteArray): Float {
        var sum = 0.0
        val shortCount = audioData.size / 2
        for (i in 0 until shortCount) {
            val sample = (audioData[i * 2].toInt() and 0xFF) or (audioData[i * 2 + 1].toInt() shl 8)
            val normalized = sample.toShort() / 32768.0f
            sum += normalized * normalized
        }
        return sqrt(sum / shortCount).toFloat()
    }
}
