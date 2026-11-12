package com.example.digitalhuman.audio

/** Ghép ngắt lời VAD cục bộ với thông báo xác nhận đến muộn từ Gemini. */
internal class InterruptionGate {
    private var awaitingServerAcknowledgement = false

    fun onLocalInterruption() {
        awaitingServerAcknowledgement = true
    }

    fun reset() {
        awaitingServerAcknowledgement = false
    }

    fun shouldFlushOnServerInterruption(): Boolean {
        if (awaitingServerAcknowledgement) {
            awaitingServerAcknowledgement = false
            return false
        }
        return true
    }
}
