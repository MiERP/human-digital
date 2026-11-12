package com.example.digitalhuman.network

/** Handle do Gemini cấp chỉ có hiệu lực cho cùng một cuộc trò chuyện. */
internal class SessionResumptionState {
    @Volatile
    private var handle: String? = null
    @Volatile
    private var keyId: String? = null

    fun acceptUpdate(newHandle: String?, newKeyId: String?) {
        handle = newHandle?.takeIf { it.isNotBlank() && !newKeyId.isNullOrBlank() }
        keyId = newKeyId?.takeIf { handle != null }
    }

    fun handleForReconnect(): String? = handle
    fun keyIdForReconnect(): String? = keyId

    fun beginNewSession() {
        handle = null
        keyId = null
    }
}
