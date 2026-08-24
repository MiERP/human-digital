package com.example.digitalhuman.network

import android.util.Log
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
    ERROR
}

class GeminiLiveClient(
    private val serverUrl: String,
    private val onAudioReceived: (ByteArray) -> Unit,
    private val onStateChanged: (ConnectionState) -> Unit,
    private val onInterrupted: () -> Unit
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

        val request = Request.Builder()
            .url(serverUrl)
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
                            "turn_complete" -> {
                                Log.d(TAG, "Gemini turn_complete received.")
                                updateState(ConnectionState.LISTENING)
                            }
                            "interrupted" -> {
                                Log.d(TAG, "Gemini turn interrupted by user.")
                                onInterrupted()
                            }
                            "waiting_for_input" -> {
                                Log.d(TAG, "Gemini waiting_for_input received.")
                                updateState(ConnectionState.LISTENING)
                            }
                            "input_transcription", "output_transcription" -> {
                                val text = json.optString("text", "")
                                if (text.isNotBlank()) {
                                    Log.d(TAG, "Transcription: $text")
                                }
                            }
                        }
                    } else if (json.has("status") && json.getString("status") == "ready") {
                        updateState(ConnectionState.LISTENING)
                    }
                } catch (e: Exception) {
                    Log.e(TAG, "Error parsing server message: $text", e)
                }
            }

            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                Log.e(TAG, "WebSocket connection failed: ${t.message}", t)
                updateState(ConnectionState.ERROR)
                scheduleReconnect()
            }

            override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
                Log.d(TAG, "WebSocket closed: $reason")
                updateState(ConnectionState.DISCONNECTED)
                if (code != 1000) {
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

    private fun updateState(newState: ConnectionState) {
        currentState = newState
        onStateChanged(newState)
    }
}
