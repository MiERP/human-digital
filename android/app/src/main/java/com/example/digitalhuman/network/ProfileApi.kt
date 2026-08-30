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
 * - GET  /api/child/topics : lấy danh sách thẻ chủ đề khám phá động
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

    /**
     * Kiểm tra khả năng kết nối đến máy chủ và kiểm tra tính hợp lệ của Gemini API Key
     */
    fun testConnection(customApiKey: String? = null): Pair<Boolean, String> {
        return try {
            val url = "$baseUrl/api/test-connection"
            val payload = JSONObject()
            if (!customApiKey.isNullOrBlank()) {
                payload.put("api_key", customApiKey.trim())
            }
            val request = Request.Builder()
                .url(url)
                .post(payload.toString().toRequestBody(jsonMediaType))
                .build()

            client.newCall(request).execute().use { response ->
                val body = response.body?.string() ?: ""
                if (response.isSuccessful) {
                    val json = JSONObject(body)
                    val success = json.optBoolean("success", false)
                    val message = json.optString("message", if (success) "Kết nối thành công!" else "Lỗi kết nối")
                    Pair(success, message)
                } else {
                    Pair(false, "Lỗi HTTP ${response.code}: $body")
                }
            }
        } catch (e: Exception) {
            android.util.Log.w(TAG, "testConnection failed: ${e.message}")
            Pair(false, "Không thể kết nối đến máy chủ: ${e.localizedMessage ?: e.message}")
        }
    }

    /**
     * Lấy danh sách thẻ chủ đề khám phá thông minh từ backend (/api/child/topics)
     */
    fun getDiscoveryTopics(childId: String): List<DiscoveryTopic> {
        return try {
            val url = "$baseUrl/api/child/topics?child_id=$childId"
            val request = Request.Builder().url(url).get().build()
            client.newCall(request).execute().use { response ->
                if (!response.isSuccessful) return fallbackTopics()
                val body = response.body?.string() ?: return fallbackTopics()
                val json = JSONObject(body)
                val array = json.optJSONArray("topics") ?: return fallbackTopics()
                val list = mutableListOf<DiscoveryTopic>()
                for (i in 0 until array.length()) {
                    val obj = array.getJSONObject(i)
                    list.add(
                        DiscoveryTopic(
                            id = obj.optString("id", "topic_$i"),
                            title = obj.optString("title", "Khám phá"),
                            titleEn = obj.optString("title_en", "Discovery"),
                            emoji = obj.optString("emoji", "⭐"),
                            colorHex = obj.optString("color_hex", "#38BDF8"),
                            tag = obj.optString("tag", "Chủ đề vui"),
                            description = obj.optString("description", ""),
                            promptHint = obj.optString("prompt_hint", "")
                        )
                    )
                }
                if (list.isEmpty()) fallbackTopics() else list
            }
        } catch (e: Exception) {
            android.util.Log.w(TAG, "getDiscoveryTopics failed: ${e.message}")
            fallbackTopics()
        }
    }

    private fun fallbackTopics(): List<DiscoveryTopic> {
        return listOf(
            DiscoveryTopic("dino", "Khủng Long Khổng Lồ", "Dinosaurs", "🦖", "#F472B6", "Muôn loài", "Khám phá sức mạnh T-Rex bạo chúa!", "[Bé vừa chọn khám phá chủ đề: Khủng Long Kỷ Jura.]"),
            DiscoveryTopic("space", "Du Hành Vũ Trụ", "Space Mission", "🚀", "#8B5CF6", "Vũ trụ", "Lái Tàu Vũ Trụ đổ bộ lên Mặt Trăng!", "[Bé vừa chọn khám phá chủ đề: Du Hành Vũ Trụ.]"),
            DiscoveryTopic("animals", "Thế Giới Động Vật", "Animal World", "🦁", "#10B981", "Bách khoa", "Tìm hiểu bí mật của các bạn thú đáng yêu!", "[Bé vừa chọn khám phá chủ đề: Thế Giới Động Vật.]"),
            DiscoveryTopic("english", "Tiệm Kem New York", "Ice Cream Shop", "🍦", "#EC4899", "Tiếng Anh", "Nhập vai gọi các vị kem thơm ngon!", "[Bé vừa chọn trò chơi nhập vai Tiệm Kem New York.]"),
            DiscoveryTopic("science", "Khoa Học Quanh Em", "Fun Science", "🔬", "#FBBF24", "Khoa học", "Tại sao cầu vồng lại có 7 màu rực rỡ?", "[Bé vừa chọn chủ đề: Khoa Học Quanh Em.]"),
            DiscoveryTopic("ocean", "Đại Dương Huyền Bí", "Ocean Mysteries", "🌊", "#06B6D4", "Đại dương", "Lặn sâu ngắm nhìn Cá Voi Xanh khổng lồ!", "[Bé vừa chọn khám phá: Đại Dương Huyền Bí.]")
        )
    }
}

data class DiscoveryTopic(
    val id: String,
    val title: String,
    val titleEn: String,
    val emoji: String,
    val colorHex: String,
    val tag: String,
    val description: String,
    val promptHint: String
)
