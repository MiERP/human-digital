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
        parentPin: String = "1234",
        companionPersona: String = "",
        companionName: String = "",
        companionGender: String = "",
    ): Boolean {
        try {
            val payload = JSONObject()
                .put("name", name)
                .put("age", age)
                .put("gender", gender)
                .put("hobbies", org.json.JSONArray(hobbies))
                .put("personality", personality)
                .put("parent_pin", parentPin.trim())
            if (companionPersona.isNotBlank()) payload.put("companion_persona", companionPersona)
            if (companionName.isNotBlank()) payload.put("companion_name", companionName)
            if (companionGender.isNotBlank()) payload.put("companion_gender", companionGender)

            val url = "$baseUrl/api/child/setup?child_id=$childId"
            val request = Request.Builder()
                .url(url)
                .post(payload.toString().toRequestBody(jsonMediaType))
                .build()

            val firstResult = client.newCall(request).execute().use { it.isSuccessful }
            if (firstResult) return true

            // Backend có thể đã có hồ sơ (v.d. app bị cài lại, đổi máy mới).
            // Khi đó POST trả về 409 -> reset cờ rồi ghi lại 1 lần nữa.
            resetSetup(childId, parentPin)
            return client.newCall(request).execute().use { it.isSuccessful }
        } catch (e: Exception) {
            android.util.Log.w(TAG, "submitSetup failed: ${e.message}")
            return false
        }
    }

    fun resetSetup(childId: String, pin: String = "1234"): Boolean {
        return try {
            val url = "$baseUrl/api/child/setup?child_id=$childId"
            val request = Request.Builder()
                .url(url)
                .header("X-Parent-PIN", pin)
                .delete()
                .build()
            client.newCall(request).execute().use { it.isSuccessful }
        } catch (e: Exception) {
            android.util.Log.w(TAG, "resetSetup failed: ${e.message}")
            false
        }
    }

    /**
     * Xác thực mã PIN phụ huynh để mở Góc Phụ Huynh trên thiết bị
     */
    fun verifyParentPin(childId: String, pin: String): Pair<Boolean, String> {
        return try {
            val url = "$baseUrl/api/child/verify-pin"
            val payload = JSONObject()
                .put("child_id", childId)
                .put("pin", pin.trim())

            val request = Request.Builder()
                .url(url)
                .post(payload.toString().toRequestBody(jsonMediaType))
                .build()

            client.newCall(request).execute().use { response ->
                val body = response.body?.string() ?: ""
                if (response.isSuccessful) {
                    val json = JSONObject(body)
                    val valid = json.optBoolean("valid", false)
                    val msg = json.optString("message", if (valid) "Mã PIN chính xác" else "Mã PIN không đúng")
                    Pair(valid, msg)
                } else {
                    Pair(false, "Lỗi kiểm tra PIN: HTTP ${response.code}")
                }
            }
        } catch (e: Exception) {
            android.util.Log.w(TAG, "verifyParentPin failed: ${e.message}")
            Pair(false, "Lỗi kết nối: ${e.localizedMessage ?: e.message}")
        }
    }

    /**
     * Đổi mã PIN phụ huynh mới cho thiết bị
     */
    fun setParentPin(childId: String, oldPin: String, newPin: String): Pair<Boolean, String> {
        return try {
            val url = "$baseUrl/api/child/set-pin"
            val payload = JSONObject()
                .put("child_id", childId)
                .put("old_pin", oldPin.trim())
                .put("new_pin", newPin.trim())

            val request = Request.Builder()
                .url(url)
                .post(payload.toString().toRequestBody(jsonMediaType))
                .build()

            client.newCall(request).execute().use { response ->
                val body = response.body?.string() ?: ""
                if (response.isSuccessful) {
                    val json = JSONObject(body)
                    Pair(true, json.optString("message", "Đổi mã PIN thành công!"))
                } else {
                    val json = try { JSONObject(body) } catch (_: Exception) { null }
                    val err = json?.optString("detail") ?: "Lỗi đổi mã PIN: HTTP ${response.code}"
                    Pair(false, err)
                }
            }
        } catch (e: Exception) {
            android.util.Log.w(TAG, "setParentPin failed: ${e.message}")
            Pair(false, "Lỗi kết nối: ${e.localizedMessage ?: e.message}")
        }
    }

    /**
     * Lấy Báo Cáo Tiến Độ Học Tập & Huy Hiệu (Daily Digest)
     */
    fun getDailyDigest(childId: String): DailyDigestData? {
        return try {
            val url = "$baseUrl/api/child/digest?child_id=$childId"
            val request = Request.Builder().url(url).get().build()
            client.newCall(request).execute().use { response ->
                if (!response.isSuccessful) return null
                val body = response.body?.string() ?: return null
                val json = JSONObject(body)

                val masteredArr = json.optJSONArray("mastered_words")
                val masteredList = mutableListOf<String>()
                if (masteredArr != null) {
                    for (i in 0 until masteredArr.length()) masteredList.add(masteredArr.getString(i))
                }

                val practiceArr = json.optJSONArray("needs_practice")
                val practiceList = mutableListOf<String>()
                if (practiceArr != null) {
                    for (i in 0 until practiceArr.length()) practiceList.add(practiceArr.getString(i))
                }

                val badgesArr = json.optJSONArray("badges")
                val badgeList = mutableListOf<BadgeItem>()
                if (badgesArr != null) {
                    for (i in 0 until badgesArr.length()) {
                        val bObj = badgesArr.getJSONObject(i)
                        badgeList.add(
                            BadgeItem(
                                id = bObj.optString("id"),
                                title = bObj.optString("title"),
                                icon = bObj.optString("icon", "🏅"),
                                description = bObj.optString("description"),
                                unlocked = bObj.optBoolean("unlocked", false)
                            )
                        )
                    }
                }

                val planObj = json.optJSONObject("learning_plan")
                val learningPlan = if (planObj != null) parsePlan(planObj) else null
                val adherenceObj = json.optJSONObject("plan_adherence")
                val adherence = if (adherenceObj != null) PlanAdherence(
                    hasPlan = adherenceObj.optBoolean("has_plan", false),
                    planned = adherenceObj.optInt("planned", 0),
                    done = adherenceObj.optInt("done", 0),
                    missed = adherenceObj.optInt("missed", 0),
                    rate = adherenceObj.optDouble("rate", 0.0),
                ) else null

                DailyDigestData(
                    streakDays = json.optInt("streak_days", 0),
                    totalSessions = json.optInt("total_sessions", 0),
                    totalDurationSeconds = json.optInt("total_duration_seconds", 0),
                    masteredWordsCount = json.optInt("mastered_words_count", 0),
                    masteredWords = masteredList,
                    needsPracticeWords = practiceList,
                    pedagogicalAdvice = json.optString("pedagogical_advice", "Hãy cùng học từ vựng mỗi ngày nhé!"),
                    badges = badgeList,
                    learningPlan = learningPlan,
                    planAdherence = adherence,
                )
            }
        } catch (e: Exception) {
            android.util.Log.w(TAG, "getDailyDigest failed: ${e.message}")
            null
        }
    }

    /**
     * Lấy toàn bộ hồ sơ chi tiết của bé (yêu cầu mã PIN)
     */
    fun getProfile(childId: String, pin: String): ChildProfileData? {
        return try {
            val url = "$baseUrl/api/child/profile?child_id=$childId"
            val request = Request.Builder()
                .url(url)
                .header("X-Parent-PIN", pin)
                .get()
                .build()

            client.newCall(request).execute().use { response ->
                if (!response.isSuccessful) return null
                val body = response.body?.string() ?: return null
                val json = JSONObject(body)

                val hobbiesArr = json.optJSONArray("hobbies")
                val hobbiesList = mutableListOf<String>()
                if (hobbiesArr != null) {
                    for (i in 0 until hobbiesArr.length()) hobbiesList.add(hobbiesArr.getString(i))
                }

                ChildProfileData(
                    name = json.optString("name", "Bé"),
                    nickname = json.optString("nickname", ""),
                    age = json.optInt("age", 5),
                    gender = json.optString("gender", "Nam"),
                    hobbies = hobbiesList,
                    personality = json.optString("personality", "Hiếu động"),
                    learningLevel = json.optString("learning_level", "Starters"),
                    favoriteColor = json.optString("favorite_color", "Xanh dương"),
                    favoriteAnimal = json.optString("favorite_animal", "Mèo máy"),
                    favoriteFood = json.optString("favorite_food", "Bánh rán"),
                    parentPin = json.optString("parent_pin", pin),
                    companionPersona = json.optString("companion_persona", ""),
                    companionName = json.optString("companion_name", ""),
                    companionGender = json.optString("companion_gender", "")
                )
            }
        } catch (e: Exception) {
            android.util.Log.w(TAG, "getProfile failed: ${e.message}")
            null
        }
    }

    /**
     * Cập nhật hồ sơ bé từ Góc Phụ Huynh trên App (yêu cầu mã PIN)
     */
    fun updateProfileWithPin(
        childId: String,
        pin: String,
        name: String,
        age: Int,
        gender: String,
        hobbies: List<String>,
        personality: String,
        learningLevel: String = "Starters",
        companionPersona: String = "",
        companionName: String = "",
        companionGender: String = "",
    ): Pair<Boolean, String> {
        return try {
            val url = "$baseUrl/api/child/profile?child_id=$childId"
            val payload = JSONObject()
                .put("name", name)
                .put("age", age)
                .put("gender", gender)
                .put("hobbies", org.json.JSONArray(hobbies))
                .put("personality", personality)
                .put("learning_level", learningLevel)
                .put("parent_pin", pin.trim())
            if (companionPersona.isNotBlank()) payload.put("companion_persona", companionPersona)
            if (companionName.isNotBlank()) payload.put("companion_name", companionName)
            if (companionGender.isNotBlank()) payload.put("companion_gender", companionGender)

            val request = Request.Builder()
                .url(url)
                .header("X-Parent-PIN", pin.trim())
                .post(payload.toString().toRequestBody(jsonMediaType))
                .build()

            client.newCall(request).execute().use { response ->
                if (response.isSuccessful) {
                    Pair(true, "Cập nhật hồ sơ thành công!")
                } else {
                    Pair(false, "Lỗi cập nhật: HTTP ${response.code}")
                }
            }
        } catch (e: Exception) {
            android.util.Log.w(TAG, "updateProfileWithPin failed: ${e.message}")
            Pair(false, "Lỗi kết nối: ${e.localizedMessage ?: e.message}")
        }
    }

    /**
     * Xóa vĩnh viễn toàn bộ dữ liệu của bé (Tuân thủ quyền riêng tư COPPA/GDPR)
     */
    fun deleteChildDataWithPin(childId: String, pin: String): Pair<Boolean, String> {
        return try {
            val url = "$baseUrl/api/child/data?child_id=$childId"
            val request = Request.Builder()
                .url(url)
                .header("X-Parent-PIN", pin.trim())
                .delete()
                .build()

            client.newCall(request).execute().use { response ->
                if (response.isSuccessful) {
                    Pair(true, "Đã xóa sạch dữ liệu của bé.")
                } else {
                    Pair(false, "Lỗi xóa dữ liệu: HTTP ${response.code}")
                }
            }
        } catch (e: Exception) {
            android.util.Log.w(TAG, "deleteChildDataWithPin failed: ${e.message}")
            Pair(false, "Lỗi kết nối: ${e.localizedMessage ?: e.message}")
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

    /**
     * Lấy danh sách nhân vật đồng hành dựng sẵn để bé tự chọn (/api/companions).
     */
    fun getCompanions(): List<CompanionInfo> {
        return try {
            val url = "$baseUrl/api/companions"
            val request = Request.Builder().url(url).get().build()
            client.newCall(request).execute().use { response ->
                if (!response.isSuccessful) return fallbackCompanions()
                val body = response.body?.string() ?: return fallbackCompanions()
                val array = JSONObject(body).optJSONArray("companions") ?: return fallbackCompanions()
                val list = mutableListOf<CompanionInfo>()
                for (i in 0 until array.length()) {
                    val obj = array.getJSONObject(i)
                    val paletteArr = obj.optJSONArray("palette")
                    val palette = if (paletteArr != null) {
                        (0 until paletteArr.length()).map { j -> paletteArr.optString(j, "#0288D1") }
                    } else listOf("#0288D1")
                    list.add(
                        CompanionInfo(
                            id = obj.optString("id", "boy_blue"),
                            name = obj.optString("default_name", "Dora"),
                            gender = obj.optString("gender", "male"),
                            voice = obj.optString("voice", "Puck"),
                            palette = palette,
                            accessory = obj.optString("accessory", "cap"),
                        )
                    )
                }
                if (list.isEmpty()) fallbackCompanions() else list
            }
        } catch (e: Exception) {
            android.util.Log.w(TAG, "getCompanions failed: ${e.message}")
            fallbackCompanions()
        }
    }

    private fun fallbackCompanions(): List<CompanionInfo> {
        return listOf(
            CompanionInfo("boy_blue", "Dora", "male", "Puck", listOf("#0288D1", "#4FC3F7", "#FFD54F"), "cap"),
            CompanionInfo("boy_green", "Siro", "male", "Charon", listOf("#2E7D32", "#66BB6A", "#FFCA28"), "cap"),
            CompanionInfo("girl_pink", "Miu", "female", "Aoede", listOf("#EC4899", "#F9A8D4", "#FDE68A"), "bow"),
            CompanionInfo("girl_purple", "Luna", "female", "Kore", listOf("#8B5CF6", "#C4B5FD", "#FDE68A"), "bow"),
        )
    }

    /**
     * Lấy kế hoạch học tập hiện tại của bé (/api/child/plan, yêu cầu PIN).
     */
    fun getPlan(childId: String, pin: String): LearningPlanData? {
        return try {
            val url = "$baseUrl/api/child/plan?child_id=$childId"
            val request = Request.Builder()
                .url(url)
                .header("X-Parent-PIN", pin)
                .get()
                .build()
            client.newCall(request).execute().use { response ->
                if (!response.isSuccessful) return null
                val body = response.body?.string() ?: return null
                val planObj = JSONObject(body).optJSONObject("plan") ?: return null
                parsePlan(planObj)
            }
        } catch (e: Exception) {
            android.util.Log.w(TAG, "getPlan failed: ${e.message}")
            null
        }
    }

    /**
     * Phụ huynh xem/sửa kế hoạch học tập (/api/child/plan, yêu cầu PIN).
     */
    fun updatePlan(
        childId: String,
        pin: String,
        days: List<String>,
        startTime: String,
        durationMinutes: Int,
        focusTopics: List<String>,
        weeklyGoal: String,
        reminderEnabled: Boolean,
    ): Pair<Boolean, String> {
        return try {
            val url = "$baseUrl/api/child/plan?child_id=$childId"
            val payload = JSONObject()
                .put("days", org.json.JSONArray(days))
                .put("start_time", startTime)
                .put("duration_minutes", durationMinutes)
                .put("focus_topics", org.json.JSONArray(focusTopics))
                .put("weekly_goal", weeklyGoal)
                .put("reminder_enabled", reminderEnabled)
                .put("is_active", true)
            val request = Request.Builder()
                .url(url)
                .header("X-Parent-PIN", pin.trim())
                .post(payload.toString().toRequestBody(jsonMediaType))
                .build()
            client.newCall(request).execute().use { response ->
                if (response.isSuccessful) Pair(true, "Đã lưu kế hoạch học tập!")
                else Pair(false, "Lỗi lưu kế hoạch: HTTP ${response.code}")
            }
        } catch (e: Exception) {
            android.util.Log.w(TAG, "updatePlan failed: ${e.message}")
            Pair(false, "Lỗi kết nối: ${e.localizedMessage ?: e.message}")
        }
    }

    private fun parsePlan(obj: JSONObject): LearningPlanData {
        val daysArr = obj.optJSONArray("days")
        val days = if (daysArr != null) (0 until daysArr.length()).map { daysArr.optString(it, "") } else emptyList()
        val topicsArr = obj.optJSONArray("focus_topics")
        val topics = if (topicsArr != null) (0 until topicsArr.length()).map { topicsArr.optString(it, "") } else emptyList()
        return LearningPlanData(
            days = days,
            startTime = obj.optString("start_time", "19:00"),
            durationMinutes = obj.optInt("duration_minutes", 20),
            focusTopics = topics,
            weeklyGoal = obj.optString("weekly_goal", ""),
            reminderEnabled = obj.optBoolean("reminder_enabled", true),
            isActive = obj.optBoolean("is_active", true),
        )
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

data class DailyDigestData(
    val streakDays: Int,
    val totalSessions: Int,
    val totalDurationSeconds: Int,
    val masteredWordsCount: Int,
    val masteredWords: List<String>,
    val needsPracticeWords: List<String>,
    val pedagogicalAdvice: String,
    val badges: List<BadgeItem>,
    val learningPlan: LearningPlanData? = null,
    val planAdherence: PlanAdherence? = null,
)

data class BadgeItem(
    val id: String,
    val title: String,
    val icon: String,
    val description: String,
    val unlocked: Boolean
)

data class ChildProfileData(
    val name: String,
    val nickname: String,
    val age: Int,
    val gender: String,
    val hobbies: List<String>,
    val personality: String,
    val learningLevel: String,
    val favoriteColor: String,
    val favoriteAnimal: String,
    val favoriteFood: String,
    val parentPin: String,
    val companionPersona: String = "",
    val companionName: String = "",
    val companionGender: String = "",
)

/** Kế hoạch học tập đã thống nhất giữa robot và bé. */
data class LearningPlanData(
    val days: List<String>,
    val startTime: String,
    val durationMinutes: Int,
    val focusTopics: List<String>,
    val weeklyGoal: String,
    val reminderEnabled: Boolean,
    val isActive: Boolean,
)

/** Mức độ tuân thủ kế hoạch trong tuần. */
data class PlanAdherence(
    val hasPlan: Boolean = false,
    val planned: Int = 0,
    val done: Int = 0,
    val missed: Int = 0,
    val rate: Double = 0.0,
)
