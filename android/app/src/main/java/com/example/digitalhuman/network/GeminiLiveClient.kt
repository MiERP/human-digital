package com.example.digitalhuman.network

import android.util.Log
import okhttp3.HttpUrl
import okhttp3.HttpUrl.Companion.toHttpUrl
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener
import okio.ByteString
import okio.ByteString.Companion.toByteString
import org.json.JSONObject
import java.util.concurrent.TimeUnit

enum class ConnectionState {
    IDLE,
    DISCONNECTED,
    CONNECTING,
    CONNECTED,
    LISTENING,
    THINKING,
    SPEAKING,
    SLEEPING,   // Robo đã chào tạm biệt và "đi ngủ" — phiên đã kết thúc êm đềm
    ERROR
}

/** Trạng thái cảm xúc + năng lượng của Robo do backend (EmotionEngine) gửi về. */
data class RobotEmotion(
    val emotion: String = "neutral",   // happy, surprised, strict, displeased, sad, neutral
    val energy: String = "neutral",    // energetic, excited, sleepy, drowsy, tired, neutral
    val intensity: Double = 0.5,       // 0.0 -> 1.0
    val fatigue: Double = 0.0,         // 0.0 -> 1.0
)

/** Bản sắc nhân vật đồng hành do backend gửi về trong gói "ready". */
data class CompanionInfo(
    val id: String = "boy_blue",
    val name: String = "Dora",
    val gender: String = "male",       // male | female
    val voice: String = "Puck",
    val palette: List<String> = listOf("#0288D1", "#4FC3F7", "#FFD54F"),
    val accessory: String = "cap",     // cap | bow | none
)

class GeminiLiveClient(
    private val serverUrl: String,
    private val childId: String,
    private val apiKey: String? = null,
    private val deviceFingerprint: String? = null,
    private val deviceModel: String? = null,
    private val androidVersion: String? = null,
    private val onAudioReceived: (ByteArray) -> Unit,
    private val onStateChanged: (ConnectionState) -> Unit,
    private val onInterrupted: () -> Unit,
    private val onEmotionChanged: ((RobotEmotion) -> Unit)? = null,
    private val onSessionEnded: (() -> Unit)? = null,
    private val onTurnComplete: (() -> Unit)? = null,
    private val onClarificationRequest: ((question: String, options: List<String>) -> Unit)? = null,
    private val onLearningCue: ((topic: String, masteredWords: List<String>, needsPractice: List<String>) -> Unit)? = null,
    private val onDeviceBanned: ((reason: String) -> Unit)? = null,
    private val onCompanionReady: ((CompanionInfo) -> Unit)? = null,
    private val onPlanUpdated: ((String) -> Unit)? = null
) {
    companion object {
        private const val TAG = "GeminiLiveClient"

        // Dùng chung một OkHttpClient cho mọi lần kết nối. Tạo mới mỗi lần
        // connect() sẽ rò rỉ thread/dispatcher và làm chậm lúc mở phiên.
        private val sharedClient: OkHttpClient by lazy {
            OkHttpClient.Builder()
                .readTimeout(0, TimeUnit.MILLISECONDS)
                .pingInterval(10, TimeUnit.SECONDS)
                .build()
        }
    }

    private var webSocket: WebSocket? = null
    @Volatile
    private var currentState = ConnectionState.IDLE

    private var reconnectAttempts = 0
    private val maxReconnectAttempts = 5
    private var shouldReconnect = true

    private val mainHandler = android.os.Handler(android.os.Looper.getMainLooper())
    private var reconnectRunnable: Runnable? = null

    // Mỗi lần connect() tăng generation. Callback của socket cũ bị bỏ qua,
    // nhờ vậy không có hai socket cùng đẩy audio/lời chào về app.
    @Volatile
    private var connectionGeneration = 0
    @Volatile
    private var hasConnectedOnce = false
    private val sessionResumption = SessionResumptionState()

    private var lastStreamEndAt = 0L
    private var audioSentSinceStreamEnd = false

    private fun scheduleReconnect() {
        if (!shouldReconnect || reconnectAttempts >= maxReconnectAttempts) return
        if (reconnectRunnable != null) return // đã có một lần hẹn, không hẹn chồng
        val delayMs = minOf(1000L * (1 shl reconnectAttempts), 30000L) // exponential backoff, max 30s
        reconnectAttempts++
        val runnable = Runnable {
            reconnectRunnable = null
            if (shouldReconnect) connect()
        }
        reconnectRunnable = runnable
        mainHandler.postDelayed(runnable, delayMs)
    }

    private fun cancelScheduledReconnect() {
        reconnectRunnable?.let { mainHandler.removeCallbacks(it) }
        reconnectRunnable = null
    }

    fun connect() {
        shouldReconnect = true
        cancelScheduledReconnect()
        if (currentState == ConnectionState.CONNECTING || currentState == ConnectionState.CONNECTED) return

        updateState(ConnectionState.CONNECTING)
        connectionGeneration++
        val generation = connectionGeneration

        // Đóng socket cũ trước khi mở socket mới.
        try {
            webSocket?.close(1000, "Reconnecting")
        } catch (_: Exception) {
        }
        webSocket = null

        // Attach child_id as query parameter (API key được truyền an toàn qua auth_init JSON, không để lộ qua URL)
        val httpUrl = serverUrl
            .replaceFirst("ws://", "http://")
            .replaceFirst("wss://", "https://")
        val url: HttpUrl = httpUrl.toHttpUrl().newBuilder()
            .addQueryParameter("child_id", childId)
            .build()

        val request = Request.Builder()
            .url(url)
            .build()

        webSocket = sharedClient.newWebSocket(request, object : WebSocketListener() {
            override fun onOpen(webSocket: WebSocket, response: Response) {
                if (generation != connectionGeneration) return
                Log.d(TAG, "WebSocket connected successfully.")
                reconnectAttempts = 0
                updateState(ConnectionState.CONNECTED)

                val isReconnect = hasConnectedOnce

                // Gửi gói tin auth_init bảo mật ngay sau khi mở kết nối
                try {
                    val initPayload = JSONObject().apply {
                        put("action", "auth_init")
                        put("child_id", childId)
                        put("is_reconnect", isReconnect)
                        if (isReconnect) {
                            sessionResumption.handleForReconnect()?.let {
                                put("session_resumption_handle", it)
                                put("resumption_key_id", sessionResumption.keyIdForReconnect())
                            }
                        }
                        if (!deviceFingerprint.isNullOrBlank()) {
                            put("device_fingerprint", deviceFingerprint)
                        }
                        if (!deviceModel.isNullOrBlank()) {
                            put("device_model", deviceModel)
                        }
                        if (!androidVersion.isNullOrBlank()) {
                            put("android_version", androidVersion)
                        }
                        if (!apiKey.isNullOrBlank()) {
                            put("api_key", apiKey.trim())
                        }
                    }
                    webSocket.send(initPayload.toString())
                    Log.d(TAG, "Sent secure auth_init handshake payload with device fingerprint.")
                } catch (e: Exception) {
                    Log.e(TAG, "Failed to send auth_init payload: ${e.message}", e)
                }
            }

            override fun onMessage(webSocket: WebSocket, bytes: ByteString) {
                if (generation != connectionGeneration) return
                // Nhận raw PCM audio 24kHz từ Gemini
                val audioData = bytes.toByteArray()
                onAudioReceived(audioData)
            }

            override fun onMessage(webSocket: WebSocket, text: String) {
                if (generation != connectionGeneration) return
                try {
                    val json = JSONObject(text)
                    if (json.has("event")) {
                        when (json.getString("event")) {
                            "device_banned" -> {
                                val reason = json.optString("reason", "Thiết bị này đã bị tạm ngưng kết nối bởi Quản trị viên.")
                                Log.w(TAG, "Device banned event received: $reason")
                                shouldReconnect = false
                                updateState(ConnectionState.ERROR)
                                onDeviceBanned?.invoke(reason)
                            }
                            "emotion_update" -> {
                                // Backend đẩy trạng thái cảm xúc/năng lượng mới.
                                parseEmotion(json.optJSONObject("emotion"))
                            }
                            "session_ended" -> {
                                // Robo đã chào tạm biệt xong — avatar chuyển "ngủ".
                                // Backend đóng WebSocket; app giữ màn ngủ 120s để bé
                                // bấm nút đánh thức, hết giờ thì tự thoát.
                                Log.d(TAG, "session_ended received. Robo is going to sleep.")
                                shouldReconnect = false
                                updateState(ConnectionState.SLEEPING)
                                onSessionEnded?.invoke()
                            }
                            "turn_complete" -> {
                                Log.d(TAG, "Gemini turn_complete received.")
                                onTurnComplete?.invoke()
                            }
                            "interrupted" -> {
                                Log.d(TAG, "Gemini turn interrupted by user.")
                                updateState(ConnectionState.LISTENING)
                                onInterrupted()
                            }
                            "session_resumption" -> {
                                sessionResumption.acceptUpdate(
                                    json.optString("handle", ""),
                                    json.optString("key_id", ""),
                                )
                            }
                            "waiting_for_input" -> {
                                Log.d(TAG, "Gemini waiting_for_input received.")
                                onTurnComplete?.invoke()
                            }
                            "input_transcription", "output_transcription" -> {
                                val text = json.optString("text", "")
                                if (text.isNotBlank()) {
                                    Log.d(TAG, "Transcription: $text")
                                }
                            }
                            "clarification_request" -> {
                                // Backend yêu cầu bé chọn 1 trong N chủ đề.
                                // Parse options array và forward cho UI callback.
                                val question = json.optString("question", "")
                                val optionsArr = json.optJSONArray("options")
                                val options: List<String> = if (optionsArr != null) {
                                    (0 until optionsArr.length()).mapNotNull { i ->
                                        optionsArr.optString(i, null)
                                    }
                                } else emptyList()
                                Log.d(
                                    TAG,
                                    "clarification_request: q='$question' options=$options"
                                )
                                onClarificationRequest?.invoke(question, options)
                            }
                            "learning_cue" -> {
                                val topic = json.optString("topic", "General")
                                val masteredArr = json.optJSONArray("mastered_words")
                                val mastered: List<String> = if (masteredArr != null) {
                                    (0 until masteredArr.length()).mapNotNull { i -> masteredArr.optString(i, null) }
                                } else emptyList()
                                val practiceArr = json.optJSONArray("needs_practice")
                                val practice: List<String> = if (practiceArr != null) {
                                    (0 until practiceArr.length()).mapNotNull { i -> practiceArr.optString(i, null) }
                                } else emptyList()
                                Log.d(TAG, "learning_cue: topic=$topic mastered=$mastered practice=$practice")
                                onLearningCue?.invoke(topic, mastered, practice)
                            }
                            "plan_updated" -> {
                                // Robot vừa chốt kế hoạch học với bé — phụ huynh có thể xem/sửa.
                                Log.d(TAG, "plan_updated received from backend.")
                                onPlanUpdated?.invoke(text)
                            }
                        }
                    } else if (json.has("status") && json.getString("status") == "ready") {
                        // Chỉ tính là "đã kết nối" khi server thực sự mở được phiên.
                        // Nếu lần đầu fail giữa handshake, lần sau vẫn được chào hỏi.
                        hasConnectedOnce = true
                        updateState(ConnectionState.LISTENING)
                        // Trạng thái cảm xúc khởi đầu gửi kèm trong gói "ready".
                        parseEmotion(json.optJSONObject("emotion"))
                        // Bản sắc nhân vật đồng hành (tên/giới tính/bảng màu).
                        parseCompanion(json.optJSONObject("companion"))
                    }
                } catch (e: Exception) {
                    Log.e(TAG, "Error parsing server message: $text", e)
                }
            }

            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                if (generation != connectionGeneration) return
                // Backend đóng WebSocket (code 1000) sau khi session kết thúc êm đềm:
                // không phải lỗi — giữ nguyên trạng thái "Robo đang ngủ".
                if (currentState == ConnectionState.SLEEPING) {
                    Log.d(TAG, "WebSocket closed after session end (ignored as failure).")
                    return
                }
                Log.e(TAG, "WebSocket connection failed: ${t.message}", t)
                updateState(ConnectionState.ERROR)
                scheduleReconnect()
            }

            override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
                if (generation != connectionGeneration) return
                Log.d(TAG, "WebSocket closed: $reason")
                if (currentState != ConnectionState.SLEEPING) {
                    updateState(ConnectionState.DISCONNECTED)
                }
                if (code != 1000 && currentState != ConnectionState.SLEEPING) {
                    scheduleReconnect()
                }
            }
        })
    }

    fun sendAudioChunk(chunk: ByteArray) {
        if (currentState != ConnectionState.DISCONNECTED && currentState != ConnectionState.ERROR) {
            if (webSocket?.send(chunk.toByteString()) == true) {
                audioSentSinceStreamEnd = true
            }
        }
    }

    /**
     * Client-side VAD (Silero) vừa phát hiện user bắt đầu nói.
     * Backend forward thành `activity_start` cho Gemini Live session.
     * Phải được gọi TRƯỚC khi gửi bất kỳ audio chunk nào của utterance.
     */
    fun notifyActivityStart() {
        val ws = webSocket
        if (ws == null) {
            Log.w(TAG, "notifyActivityStart: webSocket is null, dropping signal.")
            return
        }
        if (currentState == ConnectionState.DISCONNECTED || currentState == ConnectionState.ERROR) {
            Log.w(TAG, "notifyActivityStart: state=$currentState, dropping signal.")
            return
        }
        try {
            ws.send(JSONObject().put("action", "activity_start").toString())
            Log.d(TAG, "Sent activity_start signal.")
        } catch (e: Exception) {
            Log.e(TAG, "Failed to send activity_start: ${e.message}", e)
        }
    }

    /**
     * Client-side VAD (Silero) vừa phát hiện user ngừng nói.
     * Backend forward thành `activity_end` cho Gemini Live session — Gemini sẽ
     * finalize turn và bắt đầu generate response.
     */
    fun notifyActivityEnd() {
        val ws = webSocket
        if (ws == null) {
            Log.w(TAG, "notifyActivityEnd: webSocket is null, dropping signal.")
            return
        }
        if (currentState == ConnectionState.DISCONNECTED || currentState == ConnectionState.ERROR) {
            Log.w(TAG, "notifyActivityEnd: state=$currentState, dropping signal.")
            return
        }
        try {
            ws.send(JSONObject().put("action", "activity_end").toString())
            Log.d(TAG, "Sent activity_end signal.")
        } catch (e: Exception) {
            Log.e(TAG, "Failed to send activity_end: ${e.message}", e)
        }
    }

    /**
     * Chế độ hybrid: client-side VAD vừa phát hiện bé ngừng nói.
     * Backend forward thành `audio_stream_end` — Gemini finalize lượt NGAY,
     * bỏ qua độ trễ chờ silence của server (giảm lag phản hồi mạnh).
     */
    fun notifyAudioStreamEnd() {
        val now = System.currentTimeMillis()
        // VAD có thể tách một câu thành nhiều đoạn ngắn. Gửi finalize hai lần
        // sẽ khiến server sinh hai câu trả lời cho cùng một lượt nói.
        if (!audioSentSinceStreamEnd || now - lastStreamEndAt < 300L) {
            Log.d(TAG, "notifyAudioStreamEnd: no new audio since last end, skipping.")
            return
        }
        val ws = webSocket
        if (ws == null) {
            Log.w(TAG, "notifyAudioStreamEnd: webSocket is null, dropping signal.")
            return
        }
        if (currentState == ConnectionState.DISCONNECTED || currentState == ConnectionState.ERROR) {
            Log.w(TAG, "notifyAudioStreamEnd: state=$currentState, dropping signal.")
            return
        }
        try {
            if (ws.send(JSONObject().put("action", "audio_stream_end").toString())) {
                lastStreamEndAt = now
                audioSentSinceStreamEnd = false
                Log.d(TAG, "Sent audio_stream_end signal.")
            }
        } catch (e: Exception) {
            Log.e(TAG, "Failed to send audio_stream_end: ${e.message}", e)
        }
    }

    /**
     * Gửi lại lựa chọn mà bé đã tap trên chip bar (Encyclopedia Mode).
     * Backend sẽ forward thành text turn cho Gemini, model sẽ dùng làm
     * topic_hint cho lần gọi search tiếp theo.
     */
    fun sendClarificationResponse(choice: String) {
        val ws = webSocket
        if (ws == null) {
            Log.w(TAG, "sendClarificationResponse: webSocket is null, dropping.")
            return
        }
        if (currentState == ConnectionState.DISCONNECTED || currentState == ConnectionState.ERROR) {
            Log.w(TAG, "sendClarificationResponse: state=$currentState, dropping.")
            return
        }
        try {
            val payload = JSONObject()
                .put("action", "clarification_response")
                .put("choice", choice)
            ws.send(payload.toString())
            Log.d(TAG, "Sent clarification_response: $choice")
        } catch (e: Exception) {
            Log.e(TAG, "Failed to send clarification_response: ${e.message}", e)
        }
    }

    /**
     * Bé chọn một thẻ chủ đề khám phá từ Chiếc Túi Thần Kỳ.
     * Gửi prompt_hint lên server để Doraemon cất lời chào mở màn ngay lập tức.
     */
    fun selectTopic(topicTitle: String, promptHint: String) {
        val ws = webSocket
        if (ws == null) {
            Log.w(TAG, "selectTopic: webSocket is null, dropping.")
            return
        }
        if (currentState == ConnectionState.DISCONNECTED || currentState == ConnectionState.ERROR) {
            Log.w(TAG, "selectTopic: state=$currentState, dropping.")
            return
        }
        try {
            val payload = JSONObject()
                .put("action", "select_topic")
                .put("title", topicTitle)
                .put("prompt_hint", promptHint)
            ws.send(payload.toString())
            Log.i(TAG, "Sent select_topic: $topicTitle")
        } catch (e: Exception) {
            Log.e(TAG, "Failed to send select_topic: ${e.message}", e)
        }
    }

    /**
     * Gửi khung hình JPEG từ Camera của bé ("Mắt Thần Doraemon") lên server.
     * Backend sẽ chuyển tiếp vào session.send_realtime_input(video=Blob(image/jpeg)).
     */
    fun sendVideoFrame(jpegBytes: ByteArray) {
        val ws = webSocket
        if (ws == null || currentState == ConnectionState.DISCONNECTED || currentState == ConnectionState.ERROR) {
            return
        }
        try {
            val base64Data = android.util.Base64.encodeToString(jpegBytes, android.util.Base64.NO_WRAP)
            val payload = JSONObject()
                .put("action", "video_frame")
                .put("data", base64Data)
            ws.send(payload.toString())
        } catch (e: Exception) {
            Log.e(TAG, "Lỗi gửi video frame: ${e.message}", e)
        }
    }

    /**
     * Gửi nhãn cảm xúc của bé nhận diện từ Edge AI (Google ML Kit Face Detection) lên server.
     * Backend sẽ cập nhật ngữ cảnh hội thoại cho Gemini Live để phản hồi thấu cảm.
     */
    fun sendChildEmotion(emotion: String, confidence: Float = 1.0f) {
        val ws = webSocket
        if (ws == null || currentState == ConnectionState.DISCONNECTED || currentState == ConnectionState.ERROR) {
            return
        }
        try {
            val payload = JSONObject()
                .put("action", "child_emotion")
                .put("emotion", emotion)
                .put("confidence", confidence.toDouble())
                .put("timestamp", System.currentTimeMillis())
            ws.send(payload.toString())
            Log.d(TAG, "Sent child_emotion: $emotion (confidence=$confidence)")
        } catch (e: Exception) {
            Log.e(TAG, "Lỗi gửi child_emotion: ${e.message}", e)
        }
    }

    /**
     * Bé chủ động mở một phiên mới (không phải reconnect tự động).
     * Lần kết nối đầu tiên của phiên sẽ được chào hỏi bình thường.
     */
    fun beginNewSession() {
        hasConnectedOnce = false
        sessionResumption.beginNewSession()
    }

    fun disconnect() {
        shouldReconnect = false
        cancelScheduledReconnect()
        connectionGeneration++
        try {
            webSocket?.close(1000, "User disconnect")
        } catch (e: Exception) {
            e.printStackTrace()
        }
        webSocket = null
        updateState(ConnectionState.DISCONNECTED)
    }

    /** Robo đang "ngủ" — trạng thái nghỉ sau khi kết thúc buổi trò chuyện êm đềm. */
    fun wakeUp() {
        shouldReconnect = false
        updateState(ConnectionState.DISCONNECTED)
    }

    private fun updateState(newState: ConnectionState) {
        currentState = newState
        onStateChanged(newState)
    }

    private fun parseEmotion(json: org.json.JSONObject?) {
        if (json == null) return
        try {
            val emotion = RobotEmotion(
                emotion = json.optString("emotion", "neutral"),
                energy = json.optString("energy", "neutral"),
                intensity = json.optDouble("intensity", 0.5),
                fatigue = json.optDouble("fatigue", 0.0),
            )
            Log.d(TAG, "Emotion state: ${emotion.emotion} / ${emotion.energy} (fatigue=${emotion.fatigue})")
            onEmotionChanged?.invoke(emotion)
        } catch (e: Exception) {
            Log.w(TAG, "Failed to parse emotion state: ${e.message}")
        }
    }

    private fun parseCompanion(json: org.json.JSONObject?) {
        if (json == null) return
        try {
            val paletteArr = json.optJSONArray("palette")
            val palette: List<String> = if (paletteArr != null) {
                (0 until paletteArr.length()).mapNotNull { i -> paletteArr.optString(i, null) }
            } else emptyList()
            val companion = CompanionInfo(
                id = json.optString("id", "boy_blue"),
                name = json.optString("name", "Dora"),
                gender = json.optString("gender", "male"),
                voice = json.optString("voice", "Puck"),
                palette = palette.ifEmpty { listOf("#0288D1", "#4FC3F7", "#FFD54F") },
                accessory = json.optString("accessory", "cap"),
            )
            Log.d(TAG, "Companion: ${companion.name} (${companion.id}/${companion.gender})")
            onCompanionReady?.invoke(companion)
        } catch (e: Exception) {
            Log.w(TAG, "Failed to parse companion: ${e.message}")
        }
    }
}
