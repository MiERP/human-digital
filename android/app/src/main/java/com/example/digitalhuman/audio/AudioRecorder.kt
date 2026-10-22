package com.example.digitalhuman.audio

import android.annotation.SuppressLint
import android.content.Context
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import android.media.audiofx.AcousticEchoCanceler
import android.media.audiofx.AutomaticGainControl
import android.media.audiofx.NoiseSuppressor
import android.util.Log
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

        // Khoảng lặng để chốt kết thúc lượt nói: 11 frames x 32ms = ~352ms.
        // Ngắn hơn trước (640ms) để giảm lag phản hồi; Silero hangover đã set 300ms.
        private const val SILENCE_FRAMES_THRESHOLD = 11

        // Sau khi chốt cưỡng bức, tạm bỏ qua speech để không tái latch ngay.
        private const val FORCE_END_QUIET_MS = 1000L

        // Nếu Gemini không trả lời trong khoảng này, mở lại quyền nghe bình thường
        // để một lỗi phía server không khóa mic vĩnh viễn.
        private const val ASSISTANT_BUSY_TIMEOUT_MS = 12_000L

        // Cửa sổ năng lượng ~1 giây để phát hiện "VAD nói speech nhưng thực ra
        // chỉ là tiếng ồn nền" và đóng lượt thay vì stream nhiễu hàng chục giây.
        private const val VOICE_ENERGY_WINDOW_FRAMES = 32

        // Ngưỡng RMS tối thiểu để coi là barge-in thật khi loa đang phát.
        // Nâng lên 0.10 vì tiếng loa Luna lọt vào mic (dù có AEC) từng làm
        // cô ấy tự ngắt lời mình nhiều lần trong một lượt.
        private const val MIN_BARGE_RMS = 0.10f

        // Fallback khi Silero VAD không khởi tạo được.
        private const val RMS_FALLBACK_THRESHOLD = 0.035f

        // Gia hạn echo gate sau khi Doraemon dứt lời thực tế trên loa (150ms) —
        // ngắn hơn trước (450ms) để giảm dead-air nhưng vẫn đủ chống vọng phòng.
        private const val PLAYBACK_GRACE_MS = 150L
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

    // Gemini đang xử lý lượt của bé (từ lúc bé dứt lời đến turn_complete).
    // Trong khoảng này tiếng ồn nền không được mở lượt mới, nếu không Gemini
    // sẽ tự ngắt câu trả lời của mình trước cả khi phát audio.
    @Volatile
    var isAssistantTurnActive = false

    @Volatile
    private var assistantTurnStartedAt = 0L

    fun onAssistantTurnFinished() {
        isAssistantTurnActive = false
    }

    // Chẩn đoán chỉ bật ở bản debug, không làm nhiễu log bản phát hành.
    private val isDebuggable: Boolean =
        (context.applicationInfo.flags and android.content.pm.ApplicationInfo.FLAG_DEBUGGABLE) != 0

    // Biên độ âm thanh loa đang phát (0..1) để tính ngưỡng barge-in thích ứng.
    @Volatile
    private var lastPlaybackAmplitude = 0f

    @Volatile
    private var playbackGraceUntil = 0L

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

        val localVad = try {
            Vad.builder()
                .setContext(context)
                .setSampleRate(SampleRate.SAMPLE_RATE_16K)
                .setFrameSize(FrameSize.FRAME_SIZE_512)
                .setMode(Mode.NORMAL)
                .setSpeechDurationMs(100)
                .setSilenceDurationMs(300)
                .build()
        } catch (e: Exception) {
            e.printStackTrace()
            null
        }
        vad = localVad

        // Lớp lọc gió + tạp âm phần mềm (high-pass 200Hz + adaptive noise gate).
        val noiseCleaner = NoiseCleaner()

        audioRecord?.startRecording()
        isRecording = true

        val job = scope.launch(Dispatchers.IO) {
            val frame = ByteArray(VAD_FRAME_BYTES)
            val preRoll = ArrayDeque<ByteArray>(PRE_ROLL_FRAMES + 1)
            var userSpeaking = false
            var silenceFrames = 0
            var speechOnsetFrames = 0
            var loudOnsetFrames = 0
            var utteranceFrames = 0
            var muteOnsetUntil = 0L
            val energyWindow = ArrayDeque<Float>(VOICE_ENERGY_WINDOW_FRAMES)
            var frameOffset = 0
            var diagnosticStartedAt = System.currentTimeMillis()
            var diagnosticPeakRms = 0f
            var diagnosticVadFrames = 0
            var diagnosticEnabledFrames = 0
            var diagnosticPlaybackFrames = 0
            var diagnosticOnsets = 0

            while (isActive && isRecording) {
                // Đọc đúng 1024 bytes (512 mẫu 16-bit PCM = 32ms).
                // Bọc lỗi vì stopRecording() có thể giải phóng AudioRecord đúng lúc.
                val readBytes = try {
                    audioRecord?.read(frame, frameOffset, frame.size - frameOffset) ?: 0
                } catch (e: Exception) {
                    if (isRecording) {
                        Log.w("AudioRecorder", "AudioRecord read failed: ${e.message}")
                    }
                    0
                }
                if (readBytes <= 0) {
                    if (!isRecording) break
                    continue
                }

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
                // Micro chỉ bị tắt HẲN khi đang ngủ / mất kết nối. Trong lúc Doraemon
                // nói, mic vẫn nghe để bé có thể ngắt lời (full-duplex barge-in).
                val micDisabled = !isMicListeningEnabled
                if (isAssistantTurnActive && now - assistantTurnStartedAt > ASSISTANT_BUSY_TIMEOUT_MS) {
                    isAssistantTurnActive = false
                }
                val playing = isPlaybackActive || now < playbackGraceUntil || isAssistantTurnActive
                val echoThreshold = (lastPlaybackAmplitude * 0.5f).coerceAtLeast(MIN_BARGE_RMS)

                // Dùng đúng instance VAD của phiên này. Nếu stopRecording() đã
                // đóng nó, coi frame là im lặng thay vì ném lỗi làm sập app.
                val isSpeech = if (localVad != null) {
                    try {
                        localVad.isSpeech(frameData)
                    } catch (e: Exception) {
                        Log.w("AudioRecorder", "VAD unavailable during frame: ${e.message}")
                        false
                    }
                } else {
                    cleanRms > RMS_FALLBACK_THRESHOLD
                }
                // Sau khi chốt cưỡng bức, xem các frame kế tiếp là im lặng trong
                // một khoảng ngắn để VAD không mở lại lượt ngay trên cùng nhiễu.
                val effectiveSpeech = isSpeech && now >= muteOnsetUntil

                // Chẩn đoán tạm thời: chỉ thống kê mức tín hiệu/trạng thái, không ghi âm hay transcript.
                diagnosticPeakRms = maxOf(diagnosticPeakRms, cleanRms)
                if (isSpeech) diagnosticVadFrames++
                if (!micDisabled) diagnosticEnabledFrames++
                if (playing) diagnosticPlaybackFrames++
                if (isDebuggable && now - diagnosticStartedAt >= 2000L) {
                    Log.i("AudioRecorder", "Mic diagnostics: enabledFrames=$diagnosticEnabledFrames vadFrames=$diagnosticVadFrames onsets=$diagnosticOnsets playbackFrames=$diagnosticPlaybackFrames peakRms=${"%.3f".format(diagnosticPeakRms)}")
                    diagnosticStartedAt = now
                    diagnosticPeakRms = 0f
                    diagnosticVadFrames = 0
                    diagnosticEnabledFrames = 0
                    diagnosticPlaybackFrames = 0
                    diagnosticOnsets = 0
                }

                if (micDisabled) {
                    // Micro bị tắt hẳn (đang ngủ hoặc mất kết nối): bỏ toàn bộ frame.
                    // Đặt userSpeaking = false mà KHÔNG gọi onSpeechEnded() để tránh
                    // gửi tín hiệu kết thúc lượt giả mạo.
                    speechOnsetFrames = 0
                    loudOnsetFrames = 0
                    silenceFrames = 0
                    utteranceFrames = 0
                    muteOnsetUntil = 0L
                    preRoll.clear()
                    userSpeaking = false
                } else if (effectiveSpeech) {
                    if (!userSpeaking) {
                        speechOnsetFrames++
                        preRoll.addLast(frameData)
                        while (preRoll.size > PRE_ROLL_FRAMES) {
                            preRoll.removeFirst()
                        }

                        // Debounce thích ứng:
                        // - Loa đang phát (barge-in): cần onset dài (~450ms) VÀ đủ to
                        //   trên ngưỡng echo mới coi là bé ngắt lời thật.
                        // - Khi loa đã dứt: chỉ cần ~64ms để không bỏ câu đáp ngắn.
                        val requiredOnset = requiredSpeechOnsetFrames(playing)
                        // Khi loa không phát, vẫn cần vượt sàn năng lượng thích ứng.
                        // Trước đây một frame im lặng (RMS=0.000) vẫn được VAD nhận
                        // là speech, mở lượt và khiến app không bao giờ chốt lượt.
                        val onsetFloor = speechOnsetFloor(
                            playing = playing,
                            echoThreshold = echoThreshold,
                            noiseFloor = noiseCleaner.noiseFloorRms,
                        )
                        // Đếm riêng các frame đủ to. Chỉ cần một frame to sau nhiều
                        // frame VAD "speech" là đủ để tiếng loa tự ngắt lời Luna.
                        if (cleanRms > onsetFloor) {
                            loudOnsetFrames++
                        } else {
                            loudOnsetFrames = 0
                        }

                        if (speechOnsetFrames >= requiredOnset && loudOnsetFrames >= requiredOnset) {
                            diagnosticOnsets++
                            Log.i(
                                "AudioRecorder",
                                "Speech onset: playback=$playing frames=$speechOnsetFrames rms=${"%.3f".format(cleanRms)} echoThreshold=${"%.3f".format(echoThreshold)}",
                            )
                            userSpeaking = true
                            silenceFrames = 0
                            loudOnsetFrames = 0
                            utteranceFrames = 0
                            energyWindow.clear()
                            // Bé đã giành lượt: mở lại VAD bình thường.
                            isAssistantTurnActive = false

                            // 1. Báo bắt đầu lượt (UI: nếu đang phát thì flush loa ngay).
                            onSpeechStarted()

                            // 2. Gửi các frame pre-roll đệm trước đó để không bị mất âm đầu
                            while (preRoll.isNotEmpty()) {
                                onAudioChunk(preRoll.removeFirst())
                            }
                        }
                    } else {
                        silenceFrames = 0
                        speechOnsetFrames = 0
                        loudOnsetFrames = 0
                        onAudioChunk(frameData)
                        // VAD có thể giữ "speech" mãi trong phòng ồn. Nếu năng
                        // lượng trung bình ~1 giây quá thấp thì đây là nhiễu,
                        // không phải giọng bé: đóng lượt ngay.
                        energyWindow.addLast(cleanRms)
                        while (energyWindow.size > VOICE_ENERGY_WINDOW_FRAMES) {
                            energyWindow.removeFirst()
                        }
                        val noiseTurn = energyWindow.size >= VOICE_ENERGY_WINDOW_FRAMES &&
                            shouldEndNoisyUtterance(
                                meanRms = energyWindow.average().toFloat(),
                                noiseFloor = noiseCleaner.noiseFloorRms,
                            )
                        utteranceFrames++
                        if (noiseTurn) {
                            Log.i("AudioRecorder", "Low-energy speech; closing noise turn")
                            userSpeaking = false
                            silenceFrames = 0
                            speechOnsetFrames = 0
                            loudOnsetFrames = 0
                            utteranceFrames = 0
                            energyWindow.clear()
                            preRoll.clear()
                            muteOnsetUntil = now + FORCE_END_QUIET_MS
                            isAssistantTurnActive = true
                            assistantTurnStartedAt = now
                            onSpeechEnded()
                        } else if (shouldForceEndUtterance(utteranceFrames)) {
                            Log.i("AudioRecorder", "Max utterance reached; closing turn to avoid VAD latch")
                            userSpeaking = false
                            silenceFrames = 0
                            speechOnsetFrames = 0
                            loudOnsetFrames = 0
                            utteranceFrames = 0
                            preRoll.clear()
                            muteOnsetUntil = now + FORCE_END_QUIET_MS
                            isAssistantTurnActive = true
                            assistantTurnStartedAt = now
                            onSpeechEnded()
                        }
                    }
                } else if (userSpeaking) {
                    // Trong khi đang nói nhưng có khoảng nghỉ giữa các từ:
                    // Vẫn stream audio để âm cuối tự nhiên và đếm frame khoảng lặng
                    speechOnsetFrames = 0
                    loudOnsetFrames = 0
                    onAudioChunk(frameData)
                    silenceFrames++
                    if (silenceFrames >= SILENCE_FRAMES_THRESHOLD) {
                        userSpeaking = false
                        silenceFrames = 0
                        speechOnsetFrames = 0
                        loudOnsetFrames = 0
                        utteranceFrames = 0
                        energyWindow.clear()
                        isAssistantTurnActive = true
                        assistantTurnStartedAt = now
                        onSpeechEnded()
                    }
                } else {
                    // Đang im lặng bình thường: lưu đệm pre-roll
                    speechOnsetFrames = 0
                    loudOnsetFrames = 0
                    silenceFrames = 0
                    utteranceFrames = 0
                    preRoll.addLast(frameData)
                    while (preRoll.size > PRE_ROLL_FRAMES) {
                        preRoll.removeFirst()
                    }
                }
            }
        }

        recordingJob = job
        // Chỉ đóng VAD sau khi coroutine thu âm đã dừng hẳn. Đóng sớm trong
        // stopRecording() làm isSpeech() ném "You can't use Vad after closing session!".
        job.invokeOnCompletion {
            try {
                localVad?.close()
            } catch (_: Exception) {
            }
            if (vad === localVad) vad = null
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
        playbackGraceUntil = now + PLAYBACK_GRACE_MS
    }

    /**
     * AudioPlayer báo biên độ âm thanh đang phát (0..1). Dùng để tính ngưỡng
     * barge-in thích ứng: bé phải nói to hơn tiếng loa (sau AEC) mới được coi
     * là ngắt lời thật, tránh tiếng vang/ồn kích hoạt ngắt lời giả.
     */
    fun updatePlaybackAmplitude(amplitude: Float) {
        lastPlaybackAmplitude = amplitude
    }

    /**
     * Gọi khi AudioPlayer thực sự kết thúc phát toàn bộ âm thanh qua loa.
     * Giữ cổng chống vọng thêm PLAYBACK_GRACE_MS (150ms) sau khi loa dừng.
     */
    fun onPlaybackFinished() {
        isPlaybackActive = false
        val now = System.currentTimeMillis()
        playbackGraceUntil = now + PLAYBACK_GRACE_MS
    }

    fun stopRecording() {
        isRecording = false
        isAssistantTurnActive = false
        recordingJob?.cancel()
        recordingJob = null

        try {
            // VAD được đóng trong invokeOnCompletion của job thu âm, tránh
            // tranh chấp với frame đang xử lý.
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

internal fun requiredSpeechOnsetFrames(playing: Boolean): Int = if (playing) 14 else 2

// Chốt lượt tối đa khi VAD "latch" speech liên tục (manual VAD không có
// server VAD bảo hiểm): 625 frames x 32ms = ~20 giây.
internal const val MAX_UTTERANCE_FRAMES = 625

internal fun shouldForceEndUtterance(utteranceFrames: Int): Boolean =
    utteranceFrames >= MAX_UTTERANCE_FRAMES

// Sàn năng lượng cho onset: chặn VAD "latch" speech từ frame gần như im lặng
// (đã quan sát onset RMS=0.000 làm app kẹt lượt vĩnh viễn).
private const val ONSET_MIN_RMS = 0.03f

/**
 * Nhiễu nền có thể làm Silero trả "speech" liên tục. Nếu năng lượng trung bình
 * của cửa sổ ~1 giây quá thấp thì coi đó là nhiễu và đóng lượt thay vì stream
 * hàng chục giây tiếng ồn lên Gemini.
 */
internal fun shouldEndNoisyUtterance(meanRms: Float, noiseFloor: Float): Boolean =
    meanRms < maxOf(0.03f, noiseFloor * 2.0f)

/**
 * Ngưỡng RMS tối thiểu để bắt đầu một lượt nói.
 *
 * Khi loa đang phát, phải vượt ngưỡng echo để tránh tiếng vọng kích hoạt barge-in.
 * Khi loa im, vẫn cần vượt sàn nhiễu nền: Silero có thể trả "speech" cho một frame
 * gần như im lặng (RMS≈0), và nếu mở lượt từ đó thì app kẹt không bao giờ chốt lượt.
 */
internal fun speechOnsetFloor(playing: Boolean, echoThreshold: Float, noiseFloor: Float): Float =
    if (playing) echoThreshold else maxOf(ONSET_MIN_RMS, noiseFloor * 1.8f)
