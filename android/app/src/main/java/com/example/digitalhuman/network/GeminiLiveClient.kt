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

class GeminiLiveClient(
    private val serverUrl: String,
    private val childId: String,
    private val apiKey: String? = null,
    private val onAudioReceived: (ByteArray) -> Unit,
    private val onStateChanged: (ConnectionState) -> Unit,
    private val onInterrupted: () -> Unit,
    private val onEmotionChanged: ((RobotEmotion) -> Unit)? = null,
    private val onSessionEnded: (() -> Unit)? = null,
    private val onTurnComplete: (() -> Unit)? = null,
    private val onClarificationRequest: ((question: String, options: List<String>) -> Unit)? = null,
    private val onLearningCue: ((topic: String, masteredWords: List<String>, needsPractice: List<String>) -> Unit)? = null
) {
    companion object {
        private const val TAG = "GeminiLiveClient"
    }

    private var client: OkHttpClient? = null
    private var webSocket: WebSocket? = null
    @Volatile
    private var currentState = ConnectionState.IDLE

    private var reconnectAttempts = 0
    private val maxReconnectAttempts = 5
    private var shouldReconnect = true

    private fun scheduleReconnect() {
        if (!shouldReconnect || reconnectAttempts >= maxReconnectAttempts) return
        val delayMs = minOf(1000L * (1 shl reconnectAttempts), 30000L) // exponential backoff, max 30s
        reconnectAttempts++
        android.os.Handler(android.os.Looper.getMainLooper()).postDelayed({
            if (shouldReconnect) connect()
        }, delayMs)
    }

    fun connect() {
        shouldReconnect = true
        if (currentState == ConnectionState.CONNECTING || currentState == ConnectionState.CONNECTED) return

        updateState(ConnectionState.CONNECTING)

        client = OkHttpClient.Builder()
            .readTimeout(0, TimeUnit.MILLISECONDS)
            .pingInterval(10, TimeUnit.SECONDS)
            .build()

        // Attach child_id và api_key (nếu có) as query parameters
        val httpUrl = serverUrl
            .replaceFirst("ws://", "http://")
            .replaceFirst("wss://", "https://")
        val urlBuilder = httpUrl.toHttpUrl().newBuilder()
            .addQueryParameter("child_id", childId)
        if (!apiKey.isNullOrBlank()) {
            urlBuilder.addQueryParameter("api_key", apiKey.trim())
        }
        val url: HttpUrl = urlBuilder.build()

        val request = Request.Builder()
            .url(url)
            .build()

        webSocket = client?.newWebSocket(request, object : WebSocketListener() {
            override fun onOpen(webSocket: WebSocket, response: Response) {
                Log.d(TAG, "WebSocket connected successfully.")
                reconnectAttempts = 0
                updateState(ConnectionState.CONNECTED)
            }

            override fun onMessage(webSocket: WebSocket, bytes: ByteString) {
                // Nhận raw PCM audio 24kHz từ Gemini
                val audioData = bytes.toByteArray()
                onAudioReceived(audioData)
            }

            override fun onMessage(webSocket: WebSocket, text: String) {
                try {
                    val json = JSONObject(text)
                    if (json.has("event")) {
                        when (json.getString("event")) {
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
                        }
                    } else if (json.has("status") && json.getString("status") == "ready") {
                        updateState(ConnectionState.LISTENING)
                        // Trạng thái cảm xúc khởi đầu gửi kèm trong gói "ready".
                        parseEmotion(json.optJSONObject("emotion"))
                    }
                } catch (e: Exception) {
                    Log.e(TAG, "Error parsing server message: $text", e)
                }
            }

            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
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
            webSocket?.send(chunk.toByteString())
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

    fun disconnect() {
        shouldReconnect = false
        try {
            webSocket?.close(1000, "User disconnect")
            client?.dispatcher?.executorService?.shutdown()
        } catch (e: Exception) {
            e.printStackTrace()
        }
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
}
