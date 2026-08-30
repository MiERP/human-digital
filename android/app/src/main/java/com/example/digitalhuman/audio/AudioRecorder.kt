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

        // Giữ lại ~448ms audio (14 frames x 32ms) trước điểm bắt đầu nói để không mất âm tiết đầu (như "Có", "Dạ").
        private const val PRE_ROLL_FRAMES = 14

        // Khoảng lặng để chốt kết thúc lượt nói: 20 frames x 32ms = ~640ms.
        // Tối ưu cho on-device Silero VAD: phản hồi nhanh, không lag, vẫn đủ kiên nhẫn khi bé ngập ngừng.
        private const val SILENCE_FRAMES_THRESHOLD = 20

        // Chốt "bé bắt đầu nói" trong điều kiện bình thường: 2 frames (~64ms) để nhận diện nhanh.
        private const val SPEECH_ONSET_FRAMES_NORMAL = 2

        // Trong 800ms ngay sau khi Doraemon phát âm thanh, cần 4 frames (~128ms) để
        // triệt tiêu tuyệt đối rủi ro tiếng vang phòng (room reverb) kích hoạt giả mạo ngắt lời.
        private const val SPEECH_ONSET_FRAMES_POST_PLAYBACK = 4

        // Fallback khi Silero VAD không khởi tạo được.
        private const val RMS_FALLBACK_THRESHOLD = 0.035f

        // Gia hạn echo gate sau khi Doraemon dứt lời thực tế trên loa (450ms) để tiêu tán toàn bộ tiếng vang phòng.
        private const val PLAYBACK_GRACE_MS = 450L
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

    @Volatile
    var isMicListeningEnabled = true

    @Volatile
    private var playbackGraceUntil = 0L

    @Volatile
    private var lastPlaybackChunkTime = 0L

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
                .setMode(Mode.AGGRESSIVE)
                .setSpeechDurationMs(100)
                .setSilenceDurationMs(700)
                .build()
        } catch (e: Exception) {
            e.printStackTrace()
            null
        }

        // Lớp lọc gió + tạp âm phần mềm (high-pass 200Hz + adaptive noise gate).
        val noiseCleaner = NoiseCleaner()

        audioRecord?.startRecording()
        isRecording = true

        recordingJob = scope.launch(Dispatchers.IO) {
            val frame = ByteArray(VAD_FRAME_BYTES)
            val preRoll = ArrayDeque<ByteArray>(PRE_ROLL_FRAMES + 1)
            var userSpeaking = false
            var silenceFrames = 0
            var speechOnsetFrames = 0
            var frameOffset = 0

            while (isActive && isRecording) {
                // Đọc đúng 1024 bytes (512 mẫu 16-bit PCM = 32ms)
                val readBytes = audioRecord?.read(frame, frameOffset, frame.size - frameOffset) ?: 0
                if (readBytes <= 0) continue

                frameOffset += readBytes
                if (frameOffset < frame.size) continue
                frameOffset = 0
                val frameData = frame.copyOf()

                // Lọc gió + tạp âm trước khi đưa vào VAD và stream lên server
                val cleanRms = noiseCleaner.cleanInPlace(frameData)

                // Âm lượng hiển thị trên UI
                val rawRms = calculateRawRMS(frameData)
                onInputVolume((rawRms * 4.0f).coerceIn(0.0f, 1.0f))

                val now = System.currentTimeMillis()
                val isGated = !isMicListeningEnabled || isPlaybackActive || now < playbackGraceUntil

                // Silero VAD phát hiện giọng nói từ audio đã qua lọc nhiễu
                val vadInstance = vad
                val isSpeech = if (vadInstance != null) {
                    vadInstance.isSpeech(frameData)
                } else {
                    cleanRms > RMS_FALLBACK_THRESHOLD
                }

                if (isGated) {
                    // Micro đang bị khoá (Doraemon đang suy nghĩ hoặc đang phát âm thanh):
                    // KHÔNG nhận diện giọng nói, xóa sạch đệm pre-roll để không lọt tiếng vang loa hoặc tạp âm phòng.
                    // Đặt userSpeaking = false mà KHÔNG gọi onSpeechEnded() để tránh gửi activity_end giả mạo làm Gemini bị interrupted!
                    speechOnsetFrames = 0
                    silenceFrames = 0
                    preRoll.clear()
                    userSpeaking = false
                } else if (isSpeech) {
                    if (!userSpeaking) {
                        speechOnsetFrames++
                        preRoll.addLast(frameData)
                        while (preRoll.size > PRE_ROLL_FRAMES) {
                            preRoll.removeFirst()
                        }

                        // Debounce thích ứng: Trong 800ms sau khi Doraemon phát âm thanh, cần 4 frame (~128ms)
                        // để chống tiếng vang phòng kích hoạt ngắt lời giả. Bình thường chỉ cần 2 frame (~64ms).
                        val timeSincePlayback = now - lastPlaybackChunkTime
                        val requiredOnset = if (timeSincePlayback < 800L) {
                            SPEECH_ONSET_FRAMES_POST_PLAYBACK
                        } else {
                            SPEECH_ONSET_FRAMES_NORMAL
                        }

                        if (speechOnsetFrames >= requiredOnset) {
                            userSpeaking = true
                            silenceFrames = 0

                            // 1. Gửi signal activity_start TRƯỚC KHI gửi bất kỳ chunk audio nào
                            onSpeechStarted()

                            // 2. Gửi các frame pre-roll đệm trước đó để không bị mất âm đầu
                            while (preRoll.isNotEmpty()) {
                                onAudioChunk(preRoll.removeFirst())
                            }
                        }
                    } else {
                        silenceFrames = 0
                        speechOnsetFrames = 0
                        onAudioChunk(frameData)
                    }
                } else if (userSpeaking) {
                    // Trong khi đang nói nhưng có khoảng nghỉ giữa các từ:
                    // Vẫn stream audio để âm cuối tự nhiên và đếm frame khoảng lặng
                    speechOnsetFrames = 0
                    onAudioChunk(frameData)
                    silenceFrames++
                    if (silenceFrames >= SILENCE_FRAMES_THRESHOLD) {
                        userSpeaking = false
                        silenceFrames = 0
                        onSpeechEnded()
                    }
                } else {
                    // Đang im lặng bình thường: lưu đệm pre-roll
                    speechOnsetFrames = 0
                    silenceFrames = 0
                    preRoll.addLast(frameData)
                    while (preRoll.size > PRE_ROLL_FRAMES) {
                        preRoll.removeFirst()
                    }
                }
            }
        }
    }

    /**
     * MainActivity gọi khi nhận được một audio chunk mới từ Gemini (Robo đang nói).
     * Gia hạn echo gate thêm một khoảng ngắn sau chunk cuối để che các khoảng
     * dừng giữa câu, ngăn echo lọt vào giữa câu trả lời.
     */
    fun onPlaybackChunkReceived() {
        isPlaybackActive = true
        val now = System.currentTimeMillis()
        lastPlaybackChunkTime = now
        playbackGraceUntil = now + PLAYBACK_GRACE_MS
    }

    /**
     * Gọi khi AudioPlayer thực sự kết thúc phát toàn bộ âm thanh qua loa.
     * Khóa micro thêm PLAYBACK_GRACE_MS (450ms) tính từ thời điểm loa ngừng rung
     * để triệt tiêu 100% tiếng vang loa lọt vào mic.
     */
    fun onPlaybackFinished() {
        isPlaybackActive = false
        val now = System.currentTimeMillis()
        lastPlaybackChunkTime = now
        playbackGraceUntil = now + PLAYBACK_GRACE_MS
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
