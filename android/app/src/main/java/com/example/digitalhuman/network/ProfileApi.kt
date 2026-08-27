package com.example.digitalhuman.network

import okhttp3.MediaType.Companion.toMediaType
import okhttp3.HttpUrl.Companion.toHttpUrl
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject
import java.util.concurrent.TimeUnit

/**
 * Gọi các endpoint hồ sơ bé trên backend:
 * - GET  /api/child/setup  : kiểm tra màn cấu hình lần đầu đã xong chưa
 * - POST /api/child/setup  : lưu hồ sơ lần đầu (chỉ 1 lần)
 * - DELETE /api/child/setup: reset để màn cấu hình hiện lại
 *
 * Backend WS URL dạng ws://host:8000 -> đổi thành http://host:8000 cho REST.
 */
class ProfileApi(serverUrl: String) {
    companion object {
        private const val TAG = "ProfileApi"
    }

    // serverUrl có dạng ws://host:8000/ws/live — chỉ lấy origin (scheme://host:port),
    // bỏ phần path, vì REST endpoint nằm ở gốc (vd: /api/child/setup).
    private val baseUrl: String = run {
        val httpUrl = serverUrl
            .replaceFirst("ws://", "http://")
            .replaceFirst("wss://", "https://")
        val parsed = httpUrl.toHttpUrl()
        "${parsed.scheme}://${parsed.host}:${parsed.port}"
    }

    private val client = OkHttpClient.Builder()
        .connectTimeout(5, TimeUnit.SECONDS)
        .readTimeout(5, TimeUnit.SECONDS)
        .build()

    private val jsonMediaType = "application/json; charset=utf-8".toMediaType()

    fun isSetupCompleted(childId: String): Boolean {
        return try {
            val url = "$baseUrl/api/child/setup?child_id=$childId"
            val request = Request.Builder().url(url).get().build()
            client.newCall(request).execute().use { response ->
                if (!response.isSuccessful) return false
                val body = response.body?.string() ?: return false
                JSONObject(body).optBoolean("setup_completed", false)
            }
        } catch (e: Exception) {
            android.util.Log.w(TAG, "isSetupCompleted failed: ${e.message}")
            false
        }
    }

    fun submitSetup(
        childId: String,
        name: String,
        age: Int,
        gender: String,
        hobbies: List<String>,
        personality: String,
    ): Boolean {
        try {
            val payload = JSONObject()
                .put("name", name)
                .put("age", age)
                .put("gender", gender)
                .put("hobbies", org.json.JSONArray(hobbies))
                .put("personality", personality)

            val url = "$baseUrl/api/child/setup?child_id=$childId"
            val request = Request.Builder()
                .url(url)
                .post(payload.toString().toRequestBody(jsonMediaType))
                .build()

            val firstResult = client.newCall(request).execute().use { it.isSuccessful }
            if (firstResult) return true

            // Backend có thể đã có hồ sơ (v.d. app bị cài lại, đổi máy mới).
            // Khi đó POST trả về 409 -> reset cờ rồi ghi lại 1 lần nữa.
            resetSetup(childId)
            return client.newCall(request).execute().use { it.isSuccessful }
        } catch (e: Exception) {
            android.util.Log.w(TAG, "submitSetup failed: ${e.message}")
            return false
        }
    }

    fun resetSetup(childId: String): Boolean {
        return try {
            val url = "$baseUrl/api/child/setup?child_id=$childId"
            val request = Request.Builder().url(url).delete().build()
            client.newCall(request).execute().use { it.isSuccessful }
        } catch (e: Exception) {
            android.util.Log.w(TAG, "resetSetup failed: ${e.message}")
            false
        }
    }
}
