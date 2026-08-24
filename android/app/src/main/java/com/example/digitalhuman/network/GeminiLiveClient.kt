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
    private var currentState = ConnectionState.DISCONNECTED

    fun connect() {
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
                            }
                            "interrupted" -> {
                                Log.d(TAG, "Gemini turn interrupted by user.")
                                onInterrupted()
                            }
                            "waiting_for_input" -> {
                                Log.d(TAG, "Gemini waiting_for_input received.")
                                updateState(ConnectionState.LISTENING)
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
            }

            override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
                Log.d(TAG, "WebSocket closed: $reason")
                updateState(ConnectionState.DISCONNECTED)
            }
        })
    }

    fun sendAudioChunk(chunk: ByteArray) {
        if (currentState != ConnectionState.DISCONNECTED && currentState != ConnectionState.ERROR) {
            webSocket?.send(chunk.toByteString())
        }
    }

    fun disconnect() {
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
