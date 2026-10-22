package com.example.digitalhuman.ui

import android.Manifest
import android.app.Activity
import android.content.pm.PackageManager
import android.os.Bundle
import android.util.Log
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.Image
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.tween
import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.core.content.ContextCompat
import com.example.digitalhuman.audio.AudioPlayer
import com.example.digitalhuman.R
import com.example.digitalhuman.audio.AudioRecorder
import com.example.digitalhuman.network.ConnectionState
import com.example.digitalhuman.network.GeminiLiveClient
import com.example.digitalhuman.network.ProfileApi
import com.example.digitalhuman.network.DiscoveryTopic
import com.example.digitalhuman.network.RobotEmotion
import com.example.digitalhuman.network.CompanionInfo
import com.example.digitalhuman.network.mergeCompanionName
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import androidx.compose.foundation.border
import androidx.compose.ui.viewinterop.AndroidView
import androidx.compose.ui.platform.LocalLifecycleOwner
import androidx.camera.view.PreviewView
import com.example.digitalhuman.camera.CameraStreamManager
import com.example.digitalhuman.camera.FaceEmotionManager
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.VisualTransformation
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.util.UUID

/**
 * Chuẩn hóa input của người dùng thành WebSocket URL đầy đủ:
 * - "192.168.0.3:8000" -> "ws://192.168.0.3:8000/ws/live"
 * - "192.168.0.3" -> "ws://192.168.0.3:8000/ws/live"
 * - "http://192.168.0.3:8000" -> "ws://192.168.0.3:8000/ws/live"
 * - "ws://192.168.0.3:8000/ws/live" -> giữ nguyên
 */
fun normalizeServerWsUrl(input: String): String {
    val trimmed = input.trim()
    if (trimmed.startsWith("ws://") || trimmed.startsWith("wss://")) {
        return if (trimmed.endsWith("/ws/live")) trimmed else "${trimmed.trimEnd('/')}/ws/live"
    }
    val clean = trimmed
        .removePrefix("http://")
        .removePrefix("https://")
        .trimEnd('/')
    val hostPort = if (!clean.contains(":")) "$clean:8000" else clean
    val withoutPath = hostPort.substringBefore("/")
    return "ws://$withoutPath/ws/live"
}

fun displayHostFromWsUrl(wsUrl: String): String {
    return wsUrl
        .removePrefix("ws://")
        .removePrefix("wss://")
        .substringBefore("/ws/live")
        .substringBefore("/")
}

class MainActivity : ComponentActivity() {

    companion object {
        // Mặc định ban đầu nếu chưa có trong SharedPreferences (Trỏ thẳng vào VPS 103.20.102.229)
        private const val DEFAULT_SERVER_WS_URL = "ws://103.20.102.229/ws/live"

        // SharedPreferences keys
        const val PREFS_NAME = "robo_setup_prefs"
        private const val KEY_SETUP_DONE = "setup_done"
        private const val KEY_CHILD_ID = "child_id"
        private const val KEY_SERVER_WS_URL = "server_ws_url"
        const val KEY_GEMINI_API_KEY = "gemini_api_key"
        const val KEY_EMOTION_VISION_ENABLED = "emotion_vision_enabled"
        // Nhân vật đồng hành đã chọn (cache để hiển thị đúng tên/màu khi chưa kết nối).
        const val KEY_COMPANION_ID = "companion_id"
        const val KEY_COMPANION_NAME = "companion_name"
        const val KEY_COMPANION_GENDER = "companion_gender"
        const val KEY_COMPANION_VOICE = "companion_voice"
        const val KEY_COMPANION_PALETTE = "companion_palette"
        const val KEY_COMPANION_ACCESSORY = "companion_accessory"
    }

    /**
     * child_id riêng cho từng máy: sinh UUID 1 lần khi cài app, lưu vào
     * SharedPreferences để các lần mở sau vẫn dùng đúng ID (giữ memory của bé).
     * Cài lại app (xóa dữ liệu) sẽ sinh ID mới.
     */
    private fun resolveChildId(prefs: android.content.SharedPreferences): String {
        val existing = prefs.getString(KEY_CHILD_ID, null)
        if (!existing.isNullOrBlank()) return existing
        val fresh = UUID.randomUUID().toString()
        prefs.edit().putString(KEY_CHILD_ID, fresh).apply()
        return fresh
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        volumeControlStream = android.media.AudioManager.STREAM_VOICE_CALL

        val prefs = getSharedPreferences(PREFS_NAME, MODE_PRIVATE)
        val localSetupDone = prefs.getBoolean(KEY_SETUP_DONE, false)
        val childId = resolveChildId(prefs)
        val initialServerUrl = prefs.getString(KEY_SERVER_WS_URL, null) ?: DEFAULT_SERVER_WS_URL
        val initialApiKey = prefs.getString(KEY_GEMINI_API_KEY, "") ?: ""

        setContent {
            MaterialTheme {
                Surface(
                    modifier = Modifier.fillMaxSize(),
                    color = Color(0xFF0F172A)
                ) {
                    AppRoot(
                        initialServerUrl = initialServerUrl,
                        initialApiKey = initialApiKey,
                        childId = childId,
                        localSetupDone = localSetupDone,
                        onSetupDone = { prefs.edit().putBoolean(KEY_SETUP_DONE, true).apply() },
                        onSetupReset = { prefs.edit().putBoolean(KEY_SETUP_DONE, false).apply() },
                        onSaveServerConfig = { newUrl, newKey ->
                            prefs.edit()
                                .putString(KEY_SERVER_WS_URL, newUrl)
                                .putString(KEY_GEMINI_API_KEY, newKey)
                                .apply()
                        },
                    )
                }
            }
        }
    }
}

/**
 * Gốc điều hướng: quyết định hiện màn cấu hình lần đầu hay màn trò chuyện.
 * - Cờ local (SharedPreferences) giúp không phải gọi API mỗi lần mở app.
 * - Cho phép thay đổi IP máy chủ và API Key linh hoạt từ cả màn Setup lẫn màn Trò chuyện.
 */
@Composable
fun AppRoot(
    initialServerUrl: String,
    initialApiKey: String,
    childId: String,
    localSetupDone: Boolean,
    onSetupDone: () -> Unit,
    onSetupReset: () -> Unit,
    onSaveServerConfig: (String, String) -> Unit,
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var serverUrl by remember { mutableStateOf(initialServerUrl) }
    var customApiKey by remember { mutableStateOf(initialApiKey) }
    var setupDone by remember { mutableStateOf(localSetupDone) }
    var isCheckingBackend by remember { mutableStateOf(!localSetupDone) }
    var isSubmitting by remember { mutableStateOf(false) }
    var submitError by remember { mutableStateOf<String?>(null) }
    var showServerConfigDialog by remember { mutableStateOf(false) }
    var showParentZoneDialog by remember { mutableStateOf(false) }
    var retryTrigger by remember { mutableStateOf(0) }
    val companionPrefs = remember {
        context.getSharedPreferences(MainActivity.PREFS_NAME, android.content.Context.MODE_PRIVATE)
    }
    var selectedCompanion by remember { mutableStateOf(loadCachedCompanion(companionPrefs)) }

    val profileApi = remember(serverUrl) { ProfileApi(serverUrl) }

    // Kiểm tra backend: nếu đã có hồ sơ hoàn chỉnh (app cài lại/đổi máy),
    // không bắt phụ huynh điền lại từ đầu.
    LaunchedEffect(setupDone, serverUrl, retryTrigger) {
        if (!setupDone) {
            isCheckingBackend = true
            val backendDone = withContext(Dispatchers.IO) {
                profileApi.isSetupCompleted(childId)
            }
            if (backendDone) {
                setupDone = true
                onSetupDone()
            }
            isCheckingBackend = false
        } else {
            val chosen = withContext(Dispatchers.IO) {
                profileApi.getSelectedCompanion(childId)
            }
            if (chosen != null) {
                selectedCompanion = chosen
                saveCachedCompanion(companionPrefs, chosen)
            }
        }
    }

    if (showServerConfigDialog) {
        ServerConfigDialog(
            currentServerUrl = serverUrl,
            currentApiKey = customApiKey,
            onDismiss = { showServerConfigDialog = false },
            onSave = { newUrl, newKey ->
                serverUrl = newUrl
                customApiKey = newKey
                onSaveServerConfig(newUrl, newKey)
                showServerConfigDialog = false
                retryTrigger++
                submitError = null
                Toast.makeText(
                    context,
                    "Đã lưu cấu hình máy chủ & API Key!",
                    Toast.LENGTH_SHORT
                ).show()
            }
        )
    }

    if (showParentZoneDialog) {
        ParentZoneDialog(
            childId = childId,
            serverUrl = serverUrl,
            onDismiss = { showParentZoneDialog = false },
            onProfileUpdated = {
                retryTrigger++
            }
        )
    }

    if (setupDone) {
        TutorScreen(
            serverUrl = serverUrl,
            apiKey = customApiKey,
            childId = childId,
            initialCompanion = selectedCompanion,
            onOpenServerConfig = { showServerConfigDialog = true },
            onOpenParentZone = { showParentZoneDialog = true },
            onResetSetup = { pin ->
                scope.launch {
                    val ok = withContext(Dispatchers.IO) { profileApi.resetSetup(childId, pin) }
                    if (ok) {
                        setupDone = false
                        onSetupReset()
                    } else {
                        Toast.makeText(context, "PIN không đúng hoặc không kết nối được máy chủ.", Toast.LENGTH_LONG).show()
                    }
                }
            }
        )
    } else {
        Box(modifier = Modifier.fillMaxSize()) {
            SetupScreen(
                serverUrl = serverUrl,
                onOpenServerConfig = { showServerConfigDialog = true },
                onComplete = { name, age, gender, hobbies, personality, parentPin, companionPersona, companionName, companionGender ->
                    isSubmitting = true
                    submitError = null
                    scope.launch {
                        val ok = withContext(Dispatchers.IO) {
                            profileApi.submitSetup(
                                childId, name, age, gender, hobbies, personality, parentPin,
                                companionPersona, companionName, companionGender
                            )
                        }
                        if (ok) {
                            setupDone = true
                            onSetupDone()
                        } else {
                            submitError = "Không thể lưu hồ sơ lên máy chủ. Hãy kiểm tra kết nối Wi-Fi."
                        }
                        isSubmitting = false
                    }
                },
                isSubmitting = isSubmitting,
                submitError = submitError,
            )

            // Hiển thị đang kiểm tra khi chưa xong setup
            if (isCheckingBackend) {
                Box(
                    modifier = Modifier
                        .fillMaxSize()
                        .background(Color(0xFF0F172A).copy(alpha = 0.6f)),
                    contentAlignment = Alignment.Center
                ) {
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        Text(
                            text = "Đang kiểm tra hồ sơ từ máy chủ...",
                            color = Color.White,
                            fontSize = 14.sp
                        )
                        Spacer(modifier = Modifier.height(8.dp))
                        Text(
                            text = displayHostFromWsUrl(serverUrl),
                            color = Color(0xFF38BDF8),
                            fontSize = 12.sp
                        )
                    }
                }
            }
        }
    }
}

/**
 * Dialog cấu hình IP / Host của máy chủ Backend và Gemini API Key với chức năng Kiểm tra kết nối
 */
@Composable
fun ServerConfigDialog(
    currentServerUrl: String,
    currentApiKey: String,
    onDismiss: () -> Unit,
    onSave: (serverUrl: String, apiKey: String) -> Unit,
) {
    val scope = rememberCoroutineScope()
    var hostInput by remember { mutableStateOf(displayHostFromWsUrl(currentServerUrl)) }
    var apiKeyInput by remember { mutableStateOf(currentApiKey) }
    var isApiKeyVisible by remember { mutableStateOf(false) }
    var errorMessage by remember { mutableStateOf<String?>(null) }

    // Trạng thái kiểm tra kết nối
    var isTesting by remember { mutableStateOf(false) }
    var testResult by remember { mutableStateOf<Pair<Boolean, String>?>(null) }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = {
            Text(
                text = "⚙️ Cấu hình Máy Chủ & API Key",
                fontWeight = FontWeight.Bold,
                fontSize = 17.sp,
                color = Color.White
            )
        },
        containerColor = Color(0xFF1E293B),
        text = {
            Column(
                verticalArrangement = Arrangement.spacedBy(10.dp),
                modifier = Modifier.verticalScroll(rememberScrollState())
            ) {
                Text(
                    text = "Địa chỉ IP & Cổng máy chủ (cùng Wi-Fi):",
                    fontSize = 12.sp,
                    color = Color(0xFFCBD5E1)
                )

                OutlinedTextField(
                    value = hostInput,
                    onValueChange = {
                        hostInput = it
                        errorMessage = null
                        testResult = null
                    },
                    label = { Text("IP : Cổng", color = Color(0xFF94A3B8), fontSize = 12.sp) },
                    placeholder = { Text("192.168.0.3:8000", color = Color(0xFF64748B), fontSize = 12.sp) },
                    singleLine = true,
                    isError = errorMessage != null,
                    modifier = Modifier.fillMaxWidth(),
                    colors = OutlinedTextFieldDefaults.colors(
                        focusedTextColor = Color.White,
                        unfocusedTextColor = Color.White,
                        focusedBorderColor = Color(0xFF38BDF8),
                        unfocusedBorderColor = Color(0xFF475569),
                        cursorColor = Color(0xFF38BDF8)
                    )
                )

                Text(
                    text = "Google Gemini API Key (Tùy chọn):",
                    fontSize = 12.sp,
                    color = Color(0xFFCBD5E1)
                )

                OutlinedTextField(
                    value = apiKeyInput,
                    onValueChange = {
                        apiKeyInput = it
                        testResult = null
                    },
                    label = { Text("API Key", color = Color(0xFF94A3B8), fontSize = 12.sp) },
                    placeholder = { Text("Để trống để dùng key mặc định", color = Color(0xFF64748B), fontSize = 11.sp) },
                    singleLine = true,
                    visualTransformation = if (isApiKeyVisible) VisualTransformation.None else PasswordVisualTransformation(),
                    trailingIcon = {
                        Text(
                            text = if (isApiKeyVisible) "🙈" else "👁️",
                            modifier = Modifier
                                .clickable { isApiKeyVisible = !isApiKeyVisible }
                                .padding(8.dp),
                            fontSize = 16.sp
                        )
                    },
                    modifier = Modifier.fillMaxWidth(),
                    colors = OutlinedTextFieldDefaults.colors(
                        focusedTextColor = Color.White,
                        unfocusedTextColor = Color.White,
                        focusedBorderColor = Color(0xFF38BDF8),
                        unfocusedBorderColor = Color(0xFF475569),
                        cursorColor = Color(0xFF38BDF8)
                    )
                )

                Text(
                    text = "💡 Nếu để trống, hệ thống sẽ dùng API Key cấu hình sẵn trên máy chủ.",
                    fontSize = 11.sp,
                    color = Color(0xFF94A3B8)
                )

                // Nút Kiểm Tra Kết Nối
                Button(
                    onClick = {
                        val trimmedHost = hostInput.trim()
                        if (trimmedHost.isEmpty()) {
                            errorMessage = "Vui lòng nhập IP máy chủ trước khi kiểm tra"
                            return@Button
                        }
                        val normalized = normalizeServerWsUrl(trimmedHost)
                        isTesting = true
                        testResult = null
                        scope.launch {
                            val api = ProfileApi(normalized)
                            val result = withContext(Dispatchers.IO) {
                                api.testConnection(apiKeyInput.trim())
                            }
                            testResult = result
                            isTesting = false
                        }
                    },
                    enabled = !isTesting,
                    colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF0284C7)),
                    shape = RoundedCornerShape(10.dp),
                    modifier = Modifier.fillMaxWidth()
                ) {
                    if (isTesting) {
                        Text("⏳ Đang kiểm tra kết nối & API Key...", color = Color.White, fontSize = 12.sp)
                    } else {
                        Text("🔍 Kiểm tra kết nối đến Máy Chủ", color = Color.White, fontSize = 12.sp, fontWeight = FontWeight.Bold)
                    }
                }

                // Hiển thị kết quả kiểm tra
                testResult?.let { (success, msg) ->
                    Box(
                        modifier = Modifier
                            .fillMaxWidth()
                            .clip(RoundedCornerShape(10.dp))
                            .background(if (success) Color(0xFF10B981).copy(alpha = 0.15f) else Color(0xFFEF4444).copy(alpha = 0.15f))
                            .border(
                                1.dp,
                                if (success) Color(0xFF10B981) else Color(0xFFEF4444),
                                RoundedCornerShape(10.dp)
                            )
                            .padding(10.dp)
                    ) {
                        Text(
                            text = if (success) "🟢 $msg" else "🔴 $msg",
                            color = if (success) Color(0xFF6EE7B7) else Color(0xFFFCA5A5),
                            fontSize = 12.sp,
                            fontWeight = FontWeight.Medium
                        )
                    }
                }

                if (errorMessage != null) {
                    Text(
                        text = errorMessage ?: "",
                        color = Color(0xFFFCA5A5),
                        fontSize = 12.sp
                    )
                }

                Text(
                    text = "Gợi ý kết nối nhanh:",
                    fontSize = 11.sp,
                    fontWeight = FontWeight.SemiBold,
                    color = Color(0xFF94A3B8)
                )

                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(6.dp)
                ) {
                    Button(
                        onClick = { hostInput = "192.168.0.3:8000" },
                        colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF334155)),
                        contentPadding = PaddingValues(horizontal = 6.dp, vertical = 2.dp),
                        modifier = Modifier.weight(1f)
                    ) {
                        Text("LAN", fontSize = 10.sp, maxLines = 1)
                    }

                    Button(
                        onClick = { hostInput = "10.0.2.2:8000" },
                        colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF334155)),
                        contentPadding = PaddingValues(horizontal = 6.dp, vertical = 2.dp),
                        modifier = Modifier.weight(1f)
                    ) {
                        Text("Emulator", fontSize = 10.sp, maxLines = 1)
                    }

                    Button(
                        onClick = { hostInput = "127.0.0.1:8000" },
                        colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF334155)),
                        contentPadding = PaddingValues(horizontal = 6.dp, vertical = 2.dp),
                        modifier = Modifier.weight(1f)
                    ) {
                        Text("USB adb", fontSize = 10.sp, maxLines = 1)
                    }
                }
            }
        },
        confirmButton = {
            Button(
                onClick = {
                    val trimmed = hostInput.trim()
                    if (trimmed.isEmpty()) {
                        errorMessage = "Vui lòng nhập IP máy chủ"
                        return@Button
                    }
                    val normalized = normalizeServerWsUrl(trimmed)
                    onSave(normalized, apiKeyInput.trim())
                },
                colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF10B981))
            ) {
                Text("Lưu cấu hình", color = Color.White, fontWeight = FontWeight.Bold)
            }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) {
                Text("Hủy", color = Color(0xFF94A3B8))
            }
        }
    )
}

@Composable
fun TutorScreen(
    serverUrl: String,
    apiKey: String,
    childId: String,
    initialCompanion: CompanionInfo = CompanionInfo(),
    onOpenServerConfig: () -> Unit = {},
    onOpenParentZone: () -> Unit = {},
    onResetSetup: (String) -> Unit = {},
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()

    // Doraemon ngủ 120s chờ wake word; hết giờ không ai gọi → thoát app hoàn toàn.
    val SLEEP_TIMEOUT_MS = 120_000L
    val TAG = "TutorScreen"

    var connectionState by remember { mutableStateOf(ConnectionState.DISCONNECTED) }
    var robotAmplitude by remember { mutableFloatStateOf(0f) }
    var userVolume by remember { mutableFloatStateOf(0f) }
    var isSessionActive by remember { mutableStateOf(false) }
    var sessionEndPending by remember { mutableStateOf(false) }

    // Đồng hồ ngủ: sau session_ended, đếm 120s chờ wake word rồi thoát app.
    var sleepJob by remember { mutableStateOf<Job?>(null) }

    // Trạng thái cảm xúc + năng lượng của Doraemon (do backend EmotionEngine đẩy về).
    var robotEmotion by remember { mutableStateOf(RobotEmotion()) }

    // Bản sắc nhân vật đồng hành (tên/giới tính/bảng màu). Khởi tạo từ cache cục bộ,
    // cập nhật lại khi backend gửi gói "ready".
    val companionPrefs = remember {
        context.getSharedPreferences(MainActivity.PREFS_NAME, android.content.Context.MODE_PRIVATE)
    }
    var companionInfo by remember { mutableStateOf(initialCompanion) }
    LaunchedEffect(initialCompanion) { companionInfo = initialCompanion }
    val currentChosenCompanion by rememberUpdatedState(initialCompanion)

    // Encyclopedia Mode: state cho chip bar hỏi chủ đề
    var clarificationRequest by remember { mutableStateOf<ClarificationRequest?>(null) }

    // Visual Vocabulary / Learning Cue: state hiển thị thẻ từ vựng nổi bật
    var activeLearningCue by remember { mutableStateOf<LearningWordCue?>(null) }

    // Tự động mờ dần thẻ từ vựng sau 6 giây
    LaunchedEffect(activeLearningCue) {
        if (activeLearningCue != null) {
            delay(6000L)
            activeLearningCue = null
        }
    }

    // Menu tùy chọn (IP máy chủ / Reset hồ sơ)
    var showSettingsMenu by remember { mutableStateOf(false) }
    // Xác nhận reset cấu hình (chống bé bấm nhầm khi đang chơi)
    var showResetConfirm by remember { mutableStateOf(false) }
    var resetPin by remember { mutableStateOf("") }

    // Chiếc Túi Thần Kỳ - Menu Thẻ Chủ Đề Khám Phá ⭐
    var showTopicSheet by remember { mutableStateOf(false) }
    var discoveryTopics by remember { mutableStateOf<List<DiscoveryTopic>>(emptyList()) }
    var isLoadingTopics by remember { mutableStateOf(false) }

    var audioRecorderRef by remember { mutableStateOf<AudioRecorder?>(null) }
    val mainHandler = remember { android.os.Handler(android.os.Looper.getMainLooper()) }

    // Helper an toàn đảm bảo mọi thay đổi Compose State đều diễn ra trên Main (UI) Thread
    fun runOnMain(block: () -> Unit) {
        if (android.os.Looper.myLooper() == android.os.Looper.getMainLooper()) {
            block()
        } else {
            mainHandler.post(block)
        }
    }

    fun finishSessionAfterPlayback() {
        if (!sessionEndPending) return
        sessionEndPending = false
        isSessionActive = false
        connectionState = ConnectionState.SLEEPING
        audioRecorderRef?.isMicListeningEnabled = false
        sleepJob?.cancel()
        sleepJob = scope.launch {
            delay(SLEEP_TIMEOUT_MS)
            Log.i(TAG, "Companion slept ${SLEEP_TIMEOUT_MS}ms — exiting app.")
            (context as? Activity)?.finishAndRemoveTask()
        }
    }

    fun setSpeakerphoneRouting(enable: Boolean) {
        try {
            val audioManager = context.getSystemService(android.content.Context.AUDIO_SERVICE) as? android.media.AudioManager ?: return
            if (enable) {
                audioManager.mode = android.media.AudioManager.MODE_IN_COMMUNICATION
                if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.S) {
                    val speakerDevice = audioManager.availableCommunicationDevices.firstOrNull {
                        it.type == android.media.AudioDeviceInfo.TYPE_BUILTIN_SPEAKER
                    }
                    if (speakerDevice != null) {
                        audioManager.setCommunicationDevice(speakerDevice)
                    } else {
                        @Suppress("DEPRECATION")
                        audioManager.isSpeakerphoneOn = true
                    }
                } else {
                    @Suppress("DEPRECATION")
                    audioManager.isSpeakerphoneOn = true
                }
            } else {
                if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.S) {
                    audioManager.clearCommunicationDevice()
                } else {
                    @Suppress("DEPRECATION")
                    audioManager.isSpeakerphoneOn = false
                }
                audioManager.mode = android.media.AudioManager.MODE_NORMAL
            }
        } catch (e: Exception) {
            Log.e(TAG, "Speakerphone routing error: ${e.message}")
        }
    }

    fun loadDiscoveryTopics() {
        isLoadingTopics = true
        scope.launch(Dispatchers.IO) {
            val api = ProfileApi(serverUrl)
            val list = api.getDiscoveryTopics(childId)
            runOnMain {
                discoveryTopics = list
                isLoadingTopics = false
            }
        }
    }

    // Khởi tạo Audio Player với tracking trạng thái phát thực tế
    val audioPlayer = remember {
        AudioPlayer(
            onOutputAmplitude = { amp ->
                runOnMain {
                    robotAmplitude = amp
                    // Báo biên độ loa cho recorder để tính ngưỡng barge-in thích ứng.
                    audioRecorderRef?.updatePlaybackAmplitude(amp)
                }
            },
            onPlaybackStateChanged = { isPlaying ->
                runOnMain {
                    if (isPlaying) {
                        audioRecorderRef?.isPlaybackActive = true
                        if (isSessionActive && connectionState != ConnectionState.SLEEPING) {
                            connectionState = ConnectionState.SPEAKING
                            // GIỮ micro mở trong lúc phát để bé có thể ngắt lời (barge-in).
                            audioRecorderRef?.isMicListeningEnabled = true
                        }
                    } else {
                        audioRecorderRef?.onPlaybackFinished()
                        if (sessionEndPending) {
                            finishSessionAfterPlayback()
                        } else if (isSessionActive && connectionState != ConnectionState.SLEEPING) {
                            connectionState = ConnectionState.LISTENING
                            audioRecorderRef?.isMicListeningEnabled = true
                        }
                    }
                }
            }
        )
    }

    // Định danh phần cứng bất biến cho thiết bị (Hardware Fingerprint)
    val deviceFingerprint = remember {
        val aid = android.provider.Settings.Secure.getString(context.contentResolver, android.provider.Settings.Secure.ANDROID_ID) ?: "default_aid"
        val raw = "${aid}_${android.os.Build.MANUFACTURER}_${android.os.Build.MODEL}"
        try {
            val md = java.security.MessageDigest.getInstance("SHA-256")
            val digest = md.digest(raw.toByteArray(Charsets.UTF_8))
            digest.fold("") { str, it -> str + "%02x".format(it) }
        } catch (e: Exception) {
            raw.replace(" ", "_")
        }
    }
    val deviceModel = remember { "${android.os.Build.MANUFACTURER} ${android.os.Build.MODEL}" }
    val androidVersion = remember { "Android ${android.os.Build.VERSION.RELEASE} (API ${android.os.Build.VERSION.SDK_INT})" }
    var bannedMessageDialog by remember { mutableStateOf<String?>(null) }
    val notificationPermissionLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.RequestPermission()
    ) { granted ->
        if (!granted) {
            Toast.makeText(context, "Cần cho phép thông báo để nhận lời nhắc giờ học.", Toast.LENGTH_LONG).show()
        }
    }

    // Khởi tạo Client WebSocket
    val client = remember(serverUrl, childId, apiKey, deviceFingerprint) {
        GeminiLiveClient(
            serverUrl = serverUrl,
            childId = childId,
            apiKey = apiKey,
            deviceFingerprint = deviceFingerprint,
            deviceModel = deviceModel,
            androidVersion = androidVersion,
            onAudioReceived = { audioBytes ->
                runOnMain {
                    connectionState = ConnectionState.SPEAKING
                    // GIỮ micro mở trong lúc phát để bé có thể ngắt lời (barge-in).
                    audioRecorderRef?.isMicListeningEnabled = true
                    audioRecorderRef?.onPlaybackChunkReceived()
                    audioPlayer.enqueueAudio(audioBytes)
                }
            },
            onStateChanged = { newState ->
                runOnMain {
                    when (newState) {
                        ConnectionState.CONNECTED -> {
                            connectionState = ConnectionState.LISTENING
                            audioRecorderRef?.isMicListeningEnabled = true
                        }
                        ConnectionState.SLEEPING -> {
                            audioRecorderRef?.isMicListeningEnabled = false
                            if (!audioPlayer.isPlayingOrPending) {
                                connectionState = ConnectionState.SLEEPING
                            }
                        }
                        ConnectionState.DISCONNECTED, ConnectionState.ERROR -> {
                            connectionState = newState
                            audioRecorderRef?.isMicListeningEnabled = false
                        }
                        ConnectionState.LISTENING -> {
                            if (!audioPlayer.isPlayingOrPending && isSessionActive && connectionState != ConnectionState.SLEEPING) {
                                connectionState = ConnectionState.LISTENING
                                audioRecorderRef?.isMicListeningEnabled = true
                            }
                        }
                        ConnectionState.SPEAKING -> {
                            if (isSessionActive && connectionState != ConnectionState.SLEEPING) {
                                connectionState = ConnectionState.SPEAKING
                                // Giữ mic mở để hỗ trợ ngắt lời (barge-in).
                                audioRecorderRef?.isMicListeningEnabled = true
                            }
                        }
                        else -> Unit
                    }
                }
            },
            onInterrupted = {
                runOnMain {
                    audioPlayer.stopAndFlush()
                    connectionState = ConnectionState.LISTENING
                    audioRecorderRef?.isMicListeningEnabled = true
                }
            },
            onEmotionChanged = { emotion ->
                runOnMain {
                    robotEmotion = emotion
                }
            },
            onSessionEnded = {
                runOnMain {
                    audioRecorderRef?.stopRecording()
                    sessionEndPending = true
                    if (!audioPlayer.isPlayingOrPending) {
                        finishSessionAfterPlayback()
                    }
                }
            },
            onTurnComplete = {
                runOnMain {
                    audioPlayer.notifyTurnComplete()
                }
            },
            onClarificationRequest = { question, options ->
                runOnMain {
                    if (options.isNotEmpty()) {
                        clarificationRequest = ClarificationRequest(question, options)
                    }
                }
            },
            onLearningCue = { topic, mastered, practice ->
                runOnMain {
                    if (mastered.isNotEmpty() || practice.isNotEmpty()) {
                        activeLearningCue = LearningWordCue(topic, mastered, practice)
                    }
                }
            },
            onDeviceBanned = { reason ->
                runOnMain {
                    isSessionActive = false
                    audioRecorderRef?.stopRecording()
                    audioPlayer.stopAndFlush()
                    bannedMessageDialog = reason
                }
            },
            onCompanionReady = { companion ->
                runOnMain {
                    val selected = mergeCompanionName(currentChosenCompanion, companion)
                    companionInfo = selected
                    saveCachedCompanion(companionPrefs, selected)
                }
            },
            onPlanUpdated = { payload ->
                runOnMain {
                    try {
                        val plan = org.json.JSONObject(payload).optJSONObject("plan")
                        if (plan != null) {
                            if (!plan.optBoolean("is_active", true) || !plan.optBoolean("reminder_enabled", true)) {
                                ReminderScheduler.cancel(context)
                            } else {
                                val days = plan.optJSONArray("days")
                                val weekdays = if (days != null) (0 until days.length()).map { days.optString(it) } else emptyList()
                                ReminderScheduler.schedule(context, weekdays, plan.optString("start_time", "19:00"), companionInfo.name)
                                if (android.os.Build.VERSION.SDK_INT >= 33 &&
                                    ContextCompat.checkSelfPermission(context, Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED
                                ) {
                                    notificationPermissionLauncher.launch(Manifest.permission.POST_NOTIFICATIONS)
                                }
                            }
                        }
                    } catch (e: Exception) {
                        Log.w(TAG, "Could not schedule updated learning plan", e)
                    }
                }
            }
        )
    }

    val lifecycleOwner = LocalLifecycleOwner.current
    val prefs = remember { context.getSharedPreferences(MainActivity.PREFS_NAME, android.content.Context.MODE_PRIVATE) }
    var isEmotionVisionEnabled by remember {
        mutableStateOf(prefs.getBoolean(MainActivity.KEY_EMOTION_VISION_ENABLED, true))
    }
    var showPrivacyInfoDialog by remember { mutableStateOf(false) }

    var isCameraActive by remember { mutableStateOf(false) }
    var isFrontCamera by remember { mutableStateOf(false) }
    var previewViewRef by remember { mutableStateOf<PreviewView?>(null) }
    var childDetectedEmotion by remember { mutableStateOf("neutral") }

    // Quản lý "Đôi Mắt Cảm Xúc" (Edge AI ML Kit Face Detection chạy ngầm Camera trước)
    val faceEmotionManager = remember(client) {
        FaceEmotionManager(context = context) { emotion, confidence ->
            childDetectedEmotion = emotion
            client.sendChildEmotion(emotion, confidence)
        }
    }

    // Quản lý CameraX streaming 1 FPS cho "Mắt Thần Doraemon" (Cloud Multimodal)
    val cameraStreamManager = remember(client) {
        CameraStreamManager(context = context) { jpegBytes ->
            client.sendVideoFrame(jpegBytes)
        }
    }

    // Permission launcher cho Camera
    val cameraPermissionLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.RequestPermission()
    ) { isGranted ->
        if (isGranted) {
            isCameraActive = true
            Toast.makeText(context, "👁️ Đã bật Mắt Thần! Hãy giơ tranh vẽ hoặc đồ vật cho ${companionInfo.name} xem nhé!", Toast.LENGTH_SHORT).show()
        } else {
            Toast.makeText(context, "Cần cấp quyền Camera để ${companionInfo.name} có thể nhìn thấy đồ vật/bài tập của bé!", Toast.LENGTH_SHORT).show()
        }
    }

    // Tự động điều phối giữa Đôi Mắt Cảm Xúc (Edge AI) và Mắt Thần (Cloud Camera)
    LaunchedEffect(isSessionActive, isCameraActive, isEmotionVisionEnabled, isFrontCamera, previewViewRef) {
        val hasCamPerm = ContextCompat.checkSelfPermission(
            context,
            Manifest.permission.CAMERA
        ) == PackageManager.PERMISSION_GRANTED

        val pv = previewViewRef
        if (isCameraActive && pv != null) {
            // Khi bật Mắt Thần Cloud Vision -> tạm dừng Edge AI và bật CameraStreamManager
            faceEmotionManager.stopEmotionAnalysis()
            cameraStreamManager.startCamera(
                lifecycleOwner = lifecycleOwner,
                previewView = pv,
                useFrontCamera = isFrontCamera
            )
        } else {
            // Khi tắt Mắt Thần Cloud Vision -> dừng CameraStreamManager
            cameraStreamManager.stopCamera()
            // Nếu phiên trò chuyện đang hoạt động và người dùng BẬT Đôi Mắt Cảm Xúc -> khởi động phân tích ngầm
            if (isSessionActive && isEmotionVisionEnabled && hasCamPerm) {
                faceEmotionManager.startEmotionAnalysis(lifecycleOwner)
            } else {
                faceEmotionManager.stopEmotionAnalysis()
            }
        }
    }

    // Khởi tạo Audio Recorder với Smart VAD callbacks
    val audioRecorder = remember(client) {
        AudioRecorder(
            context = context,
            onAudioChunk = { chunk ->
                client.sendAudioChunk(chunk)
            },
            onInputVolume = { vol ->
                runOnMain {
                    userVolume = vol
                }
            },
            onSpeechStarted = {
                // Chế độ hybrid: server tự phát hiện bắt đầu lượt, nên không cần gửi
                // activity_start. Ở đây chỉ cần xử lý barge-in cục bộ cho mượt.
                runOnMain {
                    if (connectionState == ConnectionState.SPEAKING || audioPlayer.isPlayingOrPending) {
                        // Barge-in: bé nói xen vào khi Doraemon đang phát -> dừng phát tức thì.
                        audioPlayer.stopAndFlush()
                    }
                    if (connectionState != ConnectionState.SLEEPING) {
                        connectionState = ConnectionState.LISTENING
                        audioRecorderRef?.isMicListeningEnabled = true
                    }
                }
            },
            onSpeechEnded = {
                // Báo hết lượt nói để Gemini finalize NGAY (giảm lag chờ silence).
                client.notifyAudioStreamEnd()
                runOnMain {
                    if (connectionState != ConnectionState.SLEEPING) {
                        connectionState = ConnectionState.THINKING
                        // Giữ mic mở để bé vẫn có thể ngắt lời khi Doraemon trả lời.
                        audioRecorderRef?.isMicListeningEnabled = true
                    }
                }
            }
        ).also { audioRecorderRef = it }
    }

    fun startSession() {
        sessionEndPending = false
        isSessionActive = true
        setSpeakerphoneRouting(true)
        audioPlayer.start(scope)
        client.connect()
        audioRecorder.startRecording(scope)
    }

    fun stopSession() {
        sessionEndPending = false
        isSessionActive = false
        isCameraActive = false
        audioRecorder.stopRecording()
        audioPlayer.stopAndFlush()
        client.disconnect()
        setSpeakerphoneRouting(false)
    }

    // Permission launcher cho Micro & Camera
    val permissionLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.RequestPermission()
    ) { isGranted ->
        if (isGranted) {
            startSession()
        } else {
            Toast.makeText(context, "Cần cấp quyền Micro để trò chuyện với ${companionInfo.name}!", Toast.LENGTH_SHORT).show()
        }
    }

    DisposableEffect(client) {
        onDispose {
            sleepJob?.cancel()
            faceEmotionManager.release()
            cameraStreamManager.release()
            stopSession()
        }
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(
                Brush.verticalGradient(
                    colors = listOf(
                        Color(0xFF38BDF8), // Xanh da trời Doraemon tươi sáng
                        Color(0xFF0284C7),
                        Color(0xFFBAE6FD)  // Xanh mây nhạt ấm áp
                    )
                )
            )
            .padding(horizontal = 20.dp, vertical = 16.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.SpaceBetween
    ) {
        // 1. Header Bầu trời, Chỉ Báo Minh Bạch Camera & Menu Phụ Huynh
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(top = 8.dp),
            verticalArrangement = Arrangement.spacedBy(6.dp),
        ) {
          Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
          ) {
            // Huy hiệu cùng nhân vật với icon ứng dụng và màn trò chuyện.
            Row(
                verticalAlignment = Alignment.CenterVertically,
                modifier = Modifier
                    .weight(1f, fill = false)
                    .clip(RoundedCornerShape(20.dp))
                    .background(Color.White.copy(alpha = 0.25f))
                    .padding(horizontal = 12.dp, vertical = 6.dp)
            ) {
                Image(
                    painter = painterResource(R.drawable.robo_launcher),
                    contentDescription = null,
                    modifier = Modifier.size(24.dp).clip(CircleShape),
                )
                Spacer(modifier = Modifier.width(6.dp))
                Text(
                    text = companionInfo.name.uppercase(),
                    color = Color.White,
                    fontSize = 16.sp,
                    fontWeight = FontWeight.Black,
                    letterSpacing = 1.sp,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                    modifier = Modifier.weight(1f, fill = false),
                )
            }

            // Nhóm nút Phụ Huynh & Cài Đặt Hệ Thống
            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                // Nút Mở "Góc Phụ Huynh"
                Box(
                    modifier = Modifier
                        .clip(RoundedCornerShape(20.dp))
                        .background(Color.White.copy(alpha = 0.25f))
                        .clickable { onOpenParentZone() }
                        .padding(horizontal = 10.dp, vertical = 6.dp),
                    contentAlignment = Alignment.Center
                ) {
                    Text("👨‍👩‍👧 Phụ Huynh", fontSize = 12.sp, color = Color.White, fontWeight = FontWeight.Bold)
                }

                // Nút Cài Đặt (IP Server & Reset)
                Box(
                    modifier = Modifier
                        .size(34.dp)
                        .clip(CircleShape)
                        .background(Color.White.copy(alpha = 0.25f))
                        .clickable { showSettingsMenu = true },
                    contentAlignment = Alignment.Center
                ) {
                    Text("⚙️", fontSize = 15.sp)
                }
            }
          }
          // Camera status stays on a separate line so a chosen name never crowds controls.
          if (isSessionActive && isEmotionVisionEnabled && !isCameraActive) {
              Row(
                  verticalAlignment = Alignment.CenterVertically,
                  modifier = Modifier
                      .clip(RoundedCornerShape(20.dp))
                      .background(Color.White.copy(alpha = 0.35f))
                      .clickable { showPrivacyInfoDialog = true }
                      .padding(horizontal = 10.dp, vertical = 6.dp)
              ) {
                  Box(Modifier.size(8.dp).clip(CircleShape).background(Color(0xFF10B981)))
                  Spacer(modifier = Modifier.width(6.dp))
                  Text(
                      text = when (childDetectedEmotion) {
                          "super_happy" -> "😆 Bé cười rất tươi!"
                          "happy" -> "😊 Bé đang vui"
                          "curious" -> "🤔 Nghiêng đầu tò mò"
                          "attentive" -> "👀 Đang lắng nghe"
                          "focused" -> "✍️ Tập trung học"
                          "distracted" -> "🎈 Đang nhìn quanh"
                          "sleepy" -> "🌙 Bé hơi buồn ngủ"
                          "no_face" -> "🔍 Đang tìm bé..."
                          else -> "👀 Đang lắng nghe"
                      },
                      color = Color.White,
                      fontSize = 11.sp,
                      fontWeight = FontWeight.Bold,
                  )
              }
          }
        }

        // Dialog Giải Thích Quyền Riêng Tư khi chạm vào Chỉ Báo Camera
        if (showPrivacyInfoDialog) {
            AlertDialog(
                onDismissRequest = { showPrivacyInfoDialog = false },
                title = {
                    Text("🔒 Đôi Mắt ${companionInfo.name} & Quyền Riêng Tư", fontWeight = FontWeight.Bold, color = Color.White, fontSize = 16.sp)
                },
                containerColor = Color(0xFF0F172A),
                text = {
                    Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                        Text(
                            text = "${companionInfo.name} đang sử dụng Camera trước để quan sát nụ cười và cảm xúc của bé, giúp bạn robot trò chuyện thấu cảm và thân thiện hơn.",
                            fontSize = 13.sp,
                            color = Color(0xFFE2E8F0)
                        )
                        Box(
                            modifier = Modifier
                                .fillMaxWidth()
                                .clip(RoundedCornerShape(12.dp))
                                .background(Color(0xFF10B981).copy(alpha = 0.15f))
                                .border(1.dp, Color(0xFF10B981).copy(alpha = 0.4f), RoundedCornerShape(12.dp))
                                .padding(10.dp)
                        ) {
                            Text(
                                text = "🛡️ 100% Bảo mật cục bộ: Hình ảnh chỉ được phân tích trực tiếp trên chip điện thoại và giải phóng ngay lập tức trong RAM. Không lưu trữ ảnh và không gửi bất kỳ hình ảnh nào qua Internet.",
                                fontSize = 12.sp,
                                color = Color(0xFF6EE7B7),
                                fontWeight = FontWeight.Medium
                            )
                        }
                    }
                },
                confirmButton = {
                    Button(
                        onClick = { showPrivacyInfoDialog = false },
                        colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF0284C7))
                    ) {
                        Text("Đã hiểu", color = Color.White)
                    }
                }
            )
        }

        // Dialog Thông Báo Thiết Bị Bị Tạm Khóa (Hardware Ban Notice)
        if (bannedMessageDialog != null) {
            AlertDialog(
                onDismissRequest = { bannedMessageDialog = null },
                title = {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text("🚫", fontSize = 22.sp)
                        Spacer(modifier = Modifier.width(8.dp))
                        Text("Tạm Dừng Kết Nối", fontWeight = FontWeight.Bold, color = Color(0xFFEF4444), fontSize = 16.sp)
                    }
                },
                containerColor = Color(0xFF1E1B4B),
                text = {
                    Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                        Text(
                            text = bannedMessageDialog ?: "Thiết bị này đã bị tạm dừng kết nối bởi Quản trị viên hệ thống.",
                            fontSize = 13.sp,
                            color = Color(0xFFE2E8F0)
                        )
                        Text(
                            text = "💡 Mã phần cứng: ${deviceFingerprint.take(16)}...",
                            fontSize = 11.sp,
                            color = Color(0xFF94A3B8),
                            fontFamily = androidx.compose.ui.text.font.FontFamily.Monospace
                        )
                    }
                },
                confirmButton = {
                    Button(
                        onClick = { bannedMessageDialog = null },
                        colors = ButtonDefaults.buttonColors(containerColor = Color(0xFFDC2626))
                    ) {
                        Text("Đã hiểu", color = Color.White)
                    }
                }
            )
        }

        // Dialog Menu Tùy Chọn khi ấn nút ⚙
        if (showSettingsMenu) {
            AlertDialog(
                onDismissRequest = { showSettingsMenu = false },
                title = { Text("⚙️ Cài đặt dành cho Ba Mẹ", fontWeight = FontWeight.Bold, color = Color.White) },
                containerColor = Color(0xFF0F172A),
                text = {
                    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                        // Nút Bật/Tắt Đôi Mắt Cảm Xúc
                        Button(
                            onClick = {
                                val nextState = !isEmotionVisionEnabled
                                isEmotionVisionEnabled = nextState
                                prefs.edit().putBoolean(MainActivity.KEY_EMOTION_VISION_ENABLED, nextState).apply()
                                Toast.makeText(
                                    context,
                                    if (nextState) "Đã BẬT Đôi Mắt Cảm Xúc (Camera trước)" else "Đã TẮT Đôi Mắt Cảm Xúc",
                                    Toast.LENGTH_SHORT
                                ).show()
                            },
                            colors = ButtonDefaults.buttonColors(
                                containerColor = if (isEmotionVisionEnabled) Color(0xFF10B981) else Color(0xFF475569)
                            ),
                            shape = RoundedCornerShape(12.dp),
                            modifier = Modifier.fillMaxWidth()
                        ) {
                            Text(
                                text = if (isEmotionVisionEnabled) "👁️ Đôi Mắt Cảm Xúc: ĐANG BẬT" else "👁️ Đôi Mắt Cảm Xúc: ĐÃ TẮT",
                                color = Color.White,
                                fontWeight = FontWeight.Bold,
                                fontSize = 13.sp
                            )
                        }

                        Button(
                            onClick = {
                                showSettingsMenu = false
                                onOpenServerConfig()
                            },
                            colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF0284C7)),
                            shape = RoundedCornerShape(12.dp),
                            modifier = Modifier.fillMaxWidth()
                        ) {
                            Text("🌐 Đổi IP máy chủ (${displayHostFromWsUrl(serverUrl)})", color = Color.White)
                        }

                        Button(
                            onClick = {
                                showSettingsMenu = false
                                showResetConfirm = true
                            },
                            colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF334155)),
                            shape = RoundedCornerShape(12.dp),
                            modifier = Modifier.fillMaxWidth()
                        ) {
                            Text("👤 Cấu hình lại hồ sơ bé", color = Color.White)
                        }
                    }
                },
                confirmButton = {},
                dismissButton = {
                    TextButton(onClick = { showSettingsMenu = false }) {
                        Text("Đóng", color = Color(0xFF94A3B8))
                    }
                }
            )
        }

        // Dialog xác nhận reset cấu hình
        if (showResetConfirm) {
            AlertDialog(
                onDismissRequest = { showResetConfirm = false },
                containerColor = Color(0xFF0F172A),
                title = { Text("Cấu hình lại hồ sơ bé?", fontWeight = FontWeight.Bold, color = Color.White) },
                text = {
                    Column {
                        Text("Màn hình cấu hình sẽ hiện lại. Dữ liệu trò chuyện vẫn được giữ. Nhập PIN phụ huynh để xác nhận.", color = Color(0xFFCBD5E1))
                        OutlinedTextField(
                            value = resetPin,
                            onValueChange = { resetPin = it },
                            label = { Text("PIN phụ huynh") },
                            visualTransformation = PasswordVisualTransformation(),
                            singleLine = true,
                        )
                    }
                },
                confirmButton = {
                    TextButton(onClick = {
                        showResetConfirm = false
                        onResetSetup(resetPin)
                        resetPin = ""
                    }) {
                        Text("Cấu hình lại", color = Color(0xFFEF4444), fontWeight = FontWeight.Bold)
                    }
                },
                dismissButton = {
                    TextButton(onClick = { showResetConfirm = false }) {
                        Text("Hủy", color = Color(0xFF94A3B8))
                    }
                }
            )
        }

        // 2. Khu vực trung tâm: Doraemon bồng bềnh + Khung Gương Mắt Thần
        Box(
            modifier = Modifier
                .weight(1f)
                .fillMaxWidth(),
            contentAlignment = Alignment.Center
        ) {
            // Avatar nhân vật đồng hành 2D sống động với biểu cảm và hào quang
            CompanionAvatar(
                state = connectionState,
                amplitude = robotAmplitude,
                emotion = robotEmotion,
                companion = companionInfo,
            )

            // Thẻ Từ Vựng Học Tập Nổi Bật (Visual Learning Flashcard Overlay)
            activeLearningCue?.let { cue ->
                LearningWordBadgeOverlay(
                    cue = cue,
                    onDismiss = { activeLearningCue = null },
                    modifier = Modifier.align(Alignment.TopCenter)
                )
            }

            // Khung "Gương Mắt Thần" (Camera Vision Mirror) khi được bật
            if (isCameraActive) {
                Box(
                    modifier = Modifier
                        .align(Alignment.BottomEnd)
                        .padding(bottom = 8.dp, end = 2.dp)
                        .size(width = 135.dp, height = 175.dp)
                        .clip(RoundedCornerShape(20.dp))
                        .background(Color(0xFF0F172A))
                        .border(
                            width = 3.dp,
                            brush = Brush.linearGradient(
                                colors = listOf(Color(0xFFFDE047), Color(0xFFF59E0B), Color(0xFFD97706), Color(0xFFFEF08A))
                            ),
                            shape = RoundedCornerShape(20.dp)
                        )
                ) {
                    AndroidView(
                        factory = { ctx ->
                            PreviewView(ctx).also { pv -> previewViewRef = pv }
                        },
                        modifier = Modifier.fillMaxSize()
                    )

                    // Thanh điều khiển nhỏ trên khung Gương Mắt Thần
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .background(
                                Brush.verticalGradient(
                                    colors = listOf(Color.Black.copy(alpha = 0.65f), Color.Transparent)
                                )
                            )
                            .padding(horizontal = 8.dp, vertical = 6.dp),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Text("👁️", fontSize = 10.sp)
                            Spacer(modifier = Modifier.width(3.dp))
                            Text(
                                text = "Mắt Thần",
                                color = Color(0xFFFDE047),
                                fontSize = 10.sp,
                                fontWeight = FontWeight.Bold
                            )
                        }

                        Row(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                            // Nút lật camera trước/sau
                            Box(
                                modifier = Modifier
                                    .size(22.dp)
                                    .clip(CircleShape)
                                    .background(Color(0xFF0284C7))
                                    .clickable {
                                        isFrontCamera = !isFrontCamera
                                        cameraStreamManager.switchCamera(lifecycleOwner, previewViewRef)
                                    },
                                contentAlignment = Alignment.Center
                            ) {
                                Text("🔄", fontSize = 9.sp)
                            }
                            // Nút đóng camera
                            Box(
                                modifier = Modifier
                                    .size(22.dp)
                                    .clip(CircleShape)
                                    .background(Color(0xFFEF4444))
                                    .clickable { isCameraActive = false },
                                contentAlignment = Alignment.Center
                            ) {
                                Text("✕", color = Color.White, fontSize = 10.sp, fontWeight = FontWeight.Bold)
                            }
                        }
                    }
                }
            }
        }

        // 3. Khung Thoại Manga Hoạt Hình (Comic Speech Bubble)
        MangaSpeechBubble(
            text = getDoraemonSpeechText(connectionState, robotEmotion, isSessionActive, childDetectedEmotion)
                .replace("Doraemon", companionInfo.name),
            state = connectionState,
            emotion = robotEmotion
        )

        // 4. Chip bar cho Encyclopedia / Socratic Mode (khi có gợi ý chủ đề)
        clarificationRequest?.let { req ->
            Spacer(modifier = Modifier.height(10.dp))
            ClarificationChipBar(
                request = req,
                onChoiceSelected = { choice ->
                    client.sendClarificationResponse(choice)
                    clarificationRequest = null
                }
            )
        }

        Spacer(modifier = Modifier.height(16.dp))

        // 5. Thanh Điều Khiển Bảo Bối & Nút Chuông Vàng ở chân trang
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceEvenly,
            verticalAlignment = Alignment.CenterVertically
        ) {
            // Nút Bật/Tắt Gương Mắt Thần 📷
            Box(
                modifier = Modifier
                    .size(58.dp)
                    .clip(CircleShape)
                    .background(if (isCameraActive) Color(0xFFFBBF24) else Color.White.copy(alpha = 0.9f))
                    .border(
                        width = 2.dp,
                        color = if (isCameraActive) Color(0xFFD97706) else Color(0xFF38BDF8),
                        shape = CircleShape
                    )
                    .clickable {
                        if (!isCameraActive) {
                            val hasCamPerm = ContextCompat.checkSelfPermission(
                                context,
                                Manifest.permission.CAMERA
                            ) == PackageManager.PERMISSION_GRANTED
                            if (hasCamPerm) {
                                isCameraActive = true
                            } else {
                                cameraPermissionLauncher.launch(Manifest.permission.CAMERA)
                            }
                        } else {
                            isCameraActive = false
                        }
                    },
                contentAlignment = Alignment.Center
            ) {
                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                    Text(text = if (isCameraActive) "👁️" else "📷", fontSize = 20.sp)
                    Text(
                        text = "Mắt Thần",
                        fontSize = 8.sp,
                        fontWeight = FontWeight.Bold,
                        color = if (isCameraActive) Color(0xFF78350F) else Color(0xFF0284C7)
                    )
                }
            }

            // NÚT CHUÔNG VÀNG THẦN KỲ (MAGIC BELL MIC) Ở TRUNG TÂM
            MagicBellButton(
                state = connectionState,
                isSessionActive = isSessionActive,
                robotAmplitude = robotAmplitude,
                userVolume = userVolume,
                onClick = {
                    if (connectionState == ConnectionState.SLEEPING) {
                        client.wakeUp()
                        startSession()
                    } else if (!isSessionActive) {
                        val hasPermission = ContextCompat.checkSelfPermission(
                            context,
                            Manifest.permission.RECORD_AUDIO
                        ) == PackageManager.PERMISSION_GRANTED

                        if (hasPermission) {
                            startSession()
                        } else {
                            permissionLauncher.launch(Manifest.permission.RECORD_AUDIO)
                        }
                    } else {
                        stopSession()
                    }
                }
            )

            // Nút Khám Phá Chủ Đề / Gợi Ý Vui Nhộn ⭐
            Box(
                modifier = Modifier
                    .size(58.dp)
                    .clip(CircleShape)
                    .background(Color.White.copy(alpha = 0.9f))
                    .border(
                        width = 2.dp,
                        color = Color(0xFFF472B6),
                        shape = CircleShape
                    )
                    .clickable {
                        loadDiscoveryTopics()
                        showTopicSheet = true
                    },
                contentAlignment = Alignment.Center
            ) {
                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                    Text(text = "⭐", fontSize = 20.sp)
                    Text(
                        text = "Khám phá",
                        fontSize = 8.sp,
                        fontWeight = FontWeight.Bold,
                        color = Color(0xFFDB2777)
                    )
                }
            }
        }

        Spacer(modifier = Modifier.height(10.dp))
    }

    // Modal Chiếc Túi Thần Kỳ 🎒 - Menu Thẻ Chủ Đề Khám Phá Động
    if (showTopicSheet) {
        TopicDiscoveryModal(
            topics = discoveryTopics,
            isLoading = isLoadingTopics,
            companionName = companionInfo.name,
            onDismiss = { showTopicSheet = false },
            onRefresh = { loadDiscoveryTopics() },
            onTopicSelected = { topic ->
                showTopicSheet = false
                if (!isSessionActive) {
                    startSession()
                }
                client.selectTopic(topic.title, topic.promptHint)
            }
        )
    }
}

/**
 * Tạo văn bản động cho khung thoại Manga theo trạng thái và cảm xúc của Doraemon.
 */
/** Đọc nhân vật đồng hành đã cache để hiển thị đúng tên/màu trước khi kết nối. */
private fun loadCachedCompanion(prefs: android.content.SharedPreferences): CompanionInfo {
    val name = prefs.getString(MainActivity.KEY_COMPANION_NAME, null)
    if (name.isNullOrBlank() || name.equals("null", ignoreCase = true)) {
        return CompanionInfo(name = "Bạn Robot")
    }
    val paletteRaw = prefs.getString(MainActivity.KEY_COMPANION_PALETTE, null)
    val palette = paletteRaw?.split("|")?.filter { it.isNotBlank() } ?: emptyList()
    return CompanionInfo(
        id = prefs.getString(MainActivity.KEY_COMPANION_ID, "boy_blue") ?: "boy_blue",
        name = name,
        gender = prefs.getString(MainActivity.KEY_COMPANION_GENDER, "male") ?: "male",
        voice = prefs.getString(MainActivity.KEY_COMPANION_VOICE, "Puck") ?: "Puck",
        palette = palette.ifEmpty { listOf("#0288D1", "#4FC3F7", "#FFD54F") },
        accessory = prefs.getString(MainActivity.KEY_COMPANION_ACCESSORY, "cap") ?: "cap",
    )
}

/** Lưu nhân vật đồng hành vào cache cục bộ. */
private fun saveCachedCompanion(prefs: android.content.SharedPreferences, companion: CompanionInfo) {
    prefs.edit()
        .putString(MainActivity.KEY_COMPANION_ID, companion.id)
        .putString(MainActivity.KEY_COMPANION_NAME, companion.name)
        .putString(MainActivity.KEY_COMPANION_GENDER, companion.gender)
        .putString(MainActivity.KEY_COMPANION_VOICE, companion.voice)
        .putString(MainActivity.KEY_COMPANION_PALETTE, companion.palette.joinToString("|"))
        .putString(MainActivity.KEY_COMPANION_ACCESSORY, companion.accessory)
        .apply()
}

private fun getDoraemonSpeechText(
    state: ConnectionState,
    emotion: RobotEmotion,
    isSessionActive: Boolean,
    childEmotion: String = "neutral"
): String {
    if (!isSessionActive) {
        return "Chào bạn nhỏ! Hãy chạm vào Chuông Vàng để chúng mình cùng trò chuyện và khám phá nhé! ✨"
    }
    if (state == ConnectionState.LISTENING) {
        return when (childEmotion) {
            "happy" -> "Doraemon thấy bé đang cười vui lắm nè! Kể cho mình nghe với nha! 😊✨"
            "confused" -> "Đừng lo nhé, có Doraemon ở đây rồi! Có câu hỏi nào khó cứ hỏi mình nha! 💡"
            "sleepy" -> "Bé ơi, bé có thấy mệt không? Cứ thoải mái tâm sự với Doraemon nhé! 🌙"
            "focused" -> "Bé đang chăm chú làm bài ghê! Doraemon luôn ở bên cạnh bé nè! ✍️"
            else -> "Doraemon đang chăm chú lắng nghe bé nói nè! Hãy nói gì đó với mình nhé! 👂"
        }
    }
    return when (state) {
        ConnectionState.SLEEPING -> "Khò khò... Doraemon đang ngủ một lát. Chúc bé ngủ ngon nha! Zzz... 🌙"
        ConnectionState.THINKING -> "Aha, câu hỏi hay quá! Doraemon đang suy nghĩ câu trả lời cho bạn nhỏ nè... 🤔💡"
        ConnectionState.SPEAKING -> {
            when (emotion.emotion) {
                "excited" -> "Woohoo! Tuyệt vời quá bé ơi! Cùng Doraemon khám phá tiếp nào! 🎉"
                "proud" -> "Bé thông minh và giỏi quá! Doraemon tự hào về bé lắm! 🌟"
                "surprised" -> "Ôi ngạc nhiên chưa! Doraemon vừa học thêm một điều thú vị từ bé đấy! 😮"
                "displeased" -> "Hừm, bé trêu Doraemon đấy à? Đùa xíu thôi, Doraemon thương bé nhất! 😋"
                "sad" -> "Đừng buồn nhé, có Doraemon luôn ở bên cạnh bé nè! Cố lên nào! ❤️"
                else -> "Doraemon đang kể cho bé nghe nè, bé lắng nghe nhé! 💬"
            }
        }
        ConnectionState.CONNECTING -> "Đang mở Cửa Thần Kỳ kết nối đến thế giới tương lai... 🚀"
        ConnectionState.ERROR -> "Ôi Cửa Thần Kỳ bị nghẽn một chút, bé thử chạm lại Chuông Vàng nhé! 🔧"
        else -> "Doraemon sẵn sàng rồi! Chúng mình cùng học tiếng Anh và khám phá khoa học nha! 🎈"
    }
}

/**
 * Khung thoại phong cách Manga hoạt hình (Comic Speech Bubble).
 */
@Composable
fun MangaSpeechBubble(
    text: String,
    state: ConnectionState,
    emotion: RobotEmotion,
    modifier: Modifier = Modifier
) {
    val isThinking = state == ConnectionState.THINKING
    val isExcited = emotion.emotion == "excited" || emotion.emotion == "proud"

    val infiniteTransition = rememberInfiniteTransition(label = "thinking_anim")
    val thinkingAlpha by infiniteTransition.animateFloat(
        initialValue = 0.35f,
        targetValue = 1.0f,
        animationSpec = infiniteRepeatable(
            animation = tween(600, easing = FastOutSlowInEasing),
            repeatMode = RepeatMode.Reverse
        ),
        label = "thinking_glow"
    )

    Column(
        modifier = modifier.fillMaxWidth(),
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        // Thân bong bóng thoại bo tròn hoạt hình
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .clip(RoundedCornerShape(22.dp))
                .background(Color.White.copy(alpha = 0.95f))
                .border(
                    width = if (isThinking) 2.5.dp else 2.dp,
                    color = if (isExcited) Color(0xFFF472B6)
                            else if (isThinking) Color(0xFFFBBF24).copy(alpha = thinkingAlpha)
                            else Color(0xFF38BDF8),
                    shape = RoundedCornerShape(22.dp)
                )
                .padding(horizontal = 16.dp, vertical = 12.dp),
            contentAlignment = Alignment.Center
        ) {
            Column(
                horizontalAlignment = Alignment.CenterHorizontally
            ) {
                Text(
                    text = text,
                    color = Color(0xFF0F172A),
                    fontSize = 14.sp,
                    fontWeight = FontWeight.Medium,
                    lineHeight = 20.sp,
                    textAlign = TextAlign.Center
                )
                if (isThinking) {
                    Spacer(modifier = Modifier.height(6.dp))
                    Row(
                        horizontalArrangement = Arrangement.Center,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        repeat(3) { index ->
                            val dotAlpha by infiniteTransition.animateFloat(
                                initialValue = 0.2f,
                                targetValue = 1.0f,
                                animationSpec = infiniteRepeatable(
                                    animation = tween(450, delayMillis = index * 150, easing = FastOutSlowInEasing),
                                    repeatMode = RepeatMode.Reverse
                                ),
                                label = "dot_$index"
                            )
                            Box(
                                modifier = Modifier
                                    .padding(horizontal = 3.dp)
                                    .size(6.dp)
                                    .clip(CircleShape)
                                    .background(Color(0xFFF59E0B).copy(alpha = dotAlpha))
                            )
                        }
                    }
                }
            }
        }
    }
}

/**
 * Nút Chuông Vàng Thần Kỳ (Magic Bell Mic Orb) tỏa sóng âm tương tác trực quan.
 */
@Composable
fun MagicBellButton(
    state: ConnectionState,
    isSessionActive: Boolean,
    robotAmplitude: Float,
    userVolume: Float,
    onClick: () -> Unit
) {
    val infiniteTransition = rememberInfiniteTransition(label = "bell_anim")
    val pulse by infiniteTransition.animateFloat(
        initialValue = 0.95f,
        targetValue = 1.15f,
        animationSpec = infiniteRepeatable(
            animation = tween(900, easing = FastOutSlowInEasing),
            repeatMode = RepeatMode.Reverse
        ),
        label = "bell_pulse"
    )

    Box(
        contentAlignment = Alignment.Center,
        modifier = Modifier.size(96.dp)
    ) {
        // Sóng âm tỏa sáng vòng tròn ngoài khi đang nói hoặc nghe
        if (isSessionActive) {
            Box(
                modifier = Modifier
                    .size(92.dp * pulse)
                    .clip(CircleShape)
                    .background(
                        Brush.radialGradient(
                            colors = listOf(
                                (if (state == ConnectionState.SPEAKING) Color(0xFF38BDF8) else Color(0xFFFBBF24)).copy(alpha = 0.45f),
                                Color.Transparent
                            )
                        )
                    )
            )
        }

        // Quả Chuông Vàng Doraemon 3D
        Box(
            modifier = Modifier
                .size(76.dp)
                .clip(CircleShape)
                .background(
                    if (isSessionActive) {
                        Brush.verticalGradient(
                            colors = listOf(Color(0xFFFEF08A), Color(0xFFF59E0B), Color(0xFFD97706))
                        )
                    } else {
                        Brush.verticalGradient(
                            colors = listOf(Color(0xFFBAE6FD), Color(0xFF0284C7), Color(0xFF0369A1))
                        )
                    }
                )
                .border(
                    width = 3.dp,
                    color = if (isSessionActive) Color(0xFFEF4444) else Color(0xFF38BDF8),
                    shape = CircleShape
                )
                .clickable { onClick() },
            contentAlignment = Alignment.Center
        ) {
            Column(
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.Center
            ) {
                Text(
                    text = when {
                        state == ConnectionState.SLEEPING -> "🌙"
                        isSessionActive -> "🔔"
                        else -> "🎙️"
                    },
                    fontSize = 24.sp
                )
                Text(
                    text = when {
                        state == ConnectionState.SLEEPING -> "ĐÁNH THỨC"
                        isSessionActive -> "DỪNG"
                        else -> "BẮT ĐẦU"
                    },
                    color = Color.White,
                    fontSize = 8.sp,
                    fontWeight = FontWeight.Black,
                    letterSpacing = 0.5.sp
                )
            }
        }
    }
}

/**
 * Data class đại diện cho 1 yêu cầu làm rõ chủ đề từ backend (Encyclopedia Mode).
 */
data class ClarificationRequest(
    val question: String,
    val options: List<String>,
)

/**
 * Thanh chip tương tác Socratic & Encyclopedia dạng viên kẹo phát sáng sinh động.
 */
@Composable
fun ClarificationChipBar(
    request: ClarificationRequest,
    onChoiceSelected: (String) -> Unit,
) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(18.dp))
            .background(Color.White.copy(alpha = 0.9f))
            .padding(12.dp),
        horizontalAlignment = Alignment.Start,
    ) {
        Text(
            text = "🤔 ${request.question}",
            color = Color(0xFF0284C7),
            fontSize = 14.sp,
            fontWeight = FontWeight.Bold,
            modifier = Modifier.padding(bottom = 8.dp),
        )
        LazyRow(
            horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            items(request.options) { option ->
                Box(
                    modifier = Modifier
                        .clip(RoundedCornerShape(50))
                        .background(
                            Brush.horizontalGradient(
                                colors = listOf(Color(0xFF38BDF8), Color(0xFF0284C7))
                            )
                        )
                        .padding(horizontal = 14.dp, vertical = 8.dp)
                        .clickable { onChoiceSelected(option) },
                    contentAlignment = Alignment.Center,
                ) {
                    Text(
                        text = option,
                        color = Color.White,
                        fontSize = 14.sp,
                        fontWeight = FontWeight.Bold,
                    )
                }
            }
        }
    }
}

/**
 * Dữ liệu cho thẻ từ vựng học tập / recasting nổi bật.
 */
data class LearningWordCue(
    val topic: String,
    val masteredWords: List<String>,
    val needsPractice: List<String>,
)

/**
 * Thẻ từ vựng bảo bối nổi bật trên màn hình khi Doraemon sửa lỗi hoặc ghi nhận từ mới (Multimodal Visual Scaffolding).
 */
@Composable
fun LearningWordBadgeOverlay(
    cue: LearningWordCue,
    onDismiss: () -> Unit,
    modifier: Modifier = Modifier
) {
    Box(
        modifier = modifier
            .padding(top = 8.dp, start = 12.dp, end = 12.dp)
            .clip(RoundedCornerShape(20.dp))
            .background(
                Brush.linearGradient(
                    colors = listOf(
                        Color(0xFF0F172A).copy(alpha = 0.95f),
                        Color(0xFF1E293B).copy(alpha = 0.95f)
                    )
                )
            )
            .border(
                width = 2.dp,
                brush = Brush.linearGradient(
                    colors = listOf(Color(0xFF38BDF8), Color(0xFF10B981), Color(0xFFFBBF24))
                ),
                shape = RoundedCornerShape(20.dp)
            )
            .clickable { onDismiss() }
            .padding(horizontal = 16.dp, vertical = 10.dp)
    ) {
        Column(
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(6.dp)
        ) {
            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(6.dp)
            ) {
                Text("🌟", fontSize = 14.sp)
                Text(
                    text = "BẢO BỐI TỪ VỰNG: ${cue.topic.uppercase()}",
                    color = Color(0xFF38BDF8),
                    fontSize = 11.sp,
                    fontWeight = FontWeight.Black,
                    letterSpacing = 0.5.sp
                )
                Text("✨", fontSize = 14.sp)
            }

            if (cue.masteredWords.isNotEmpty()) {
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(6.dp)
                ) {
                    Text("👍", fontSize = 13.sp)
                    cue.masteredWords.forEach { word ->
                        Box(
                            modifier = Modifier
                                .clip(RoundedCornerShape(10.dp))
                                .background(Color(0xFF10B981))
                                .padding(horizontal = 10.dp, vertical = 4.dp)
                        ) {
                            Text(
                                text = word,
                                color = Color.White,
                                fontSize = 13.sp,
                                fontWeight = FontWeight.Bold
                            )
                        }
                    }
                }
            }

            if (cue.needsPractice.isNotEmpty()) {
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(6.dp)
                ) {
                    Text("🎯", fontSize = 13.sp)
                    cue.needsPractice.forEach { word ->
                        Box(
                            modifier = Modifier
                                .clip(RoundedCornerShape(10.dp))
                                .background(Color(0xFFF59E0B))
                                .padding(horizontal = 10.dp, vertical = 4.dp)
                        ) {
                            Text(
                                text = word,
                                color = Color.White,
                                fontSize = 13.sp,
                                fontWeight = FontWeight.Bold
                            )
                        }
                    }
                }
            }
        }
    }
}

/**
 * Chiếc Túi Thần Kỳ 🎒: Hộp thoại chọn thẻ chủ đề khám phá động
 */
@Composable
fun TopicDiscoveryModal(
    topics: List<DiscoveryTopic>,
    isLoading: Boolean,
    companionName: String,
    onDismiss: () -> Unit,
    onRefresh: () -> Unit,
    onTopicSelected: (DiscoveryTopic) -> Unit
) {
    Dialog(
        onDismissRequest = onDismiss,
        properties = DialogProperties(usePlatformDefaultWidth = false)
    ) {
        Box(
            modifier = Modifier
                .fillMaxSize()
                .background(Color.Black.copy(alpha = 0.55f))
                .clickable { onDismiss() }
                .padding(16.dp),
            contentAlignment = Alignment.Center
        ) {
            Surface(
                modifier = Modifier
                    .fillMaxWidth()
                    .clip(RoundedCornerShape(24.dp))
                    .border(3.dp, Color(0xFF38BDF8), RoundedCornerShape(24.dp))
                    .clickable(enabled = false) {}, // Ngăn click lọt ra ngoài nền
                color = Color(0xFFF0F9FF),
                shadowElevation = 8.dp
            ) {
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(18.dp)
                ) {
                    // Header
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Text(text = "🎒", fontSize = 28.sp)
                            Spacer(modifier = Modifier.width(8.dp))
                            Column {
                                Text(
                                    text = "Chiếc Túi Thần Kỳ",
                                    fontSize = 18.sp,
                                    fontWeight = FontWeight.Bold,
                                    color = Color(0xFF0284C7)
                                )
                                Text(
                                    text = "Bé muốn cùng $companionName khám phá gì nào?",
                                    fontSize = 11.sp,
                                    color = Color(0xFF64748B)
                                )
                            }
                        }

                        // Nút đóng
                        Box(
                            modifier = Modifier
                                .size(32.dp)
                                .clip(CircleShape)
                                .background(Color(0xFFE2E8F0))
                                .clickable { onDismiss() },
                            contentAlignment = Alignment.Center
                        ) {
                            Text(text = "✕", fontSize = 14.sp, fontWeight = FontWeight.Bold, color = Color(0xFF475569))
                        }
                    }

                    Spacer(modifier = Modifier.height(14.dp))

                    if (isLoading) {
                        Box(
                            modifier = Modifier
                                .fillMaxWidth()
                                .height(260.dp),
                            contentAlignment = Alignment.Center
                        ) {
                            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                                CircularProgressIndicator(color = Color(0xFF0284C7))
                                Spacer(modifier = Modifier.height(10.dp))
                                Text(
                                    text = "$companionName đang mở túi thần kỳ... ✨",
                                    fontSize = 12.sp,
                                    color = Color(0xFF0284C7),
                                    fontWeight = FontWeight.Medium
                                )
                            }
                        }
                    } else {
                        // Grid 2 cột các thẻ chủ đề
                        LazyVerticalGrid(
                            columns = GridCells.Fixed(2),
                            modifier = Modifier
                                .fillMaxWidth()
                                .height(380.dp),
                            horizontalArrangement = Arrangement.spacedBy(10.dp),
                            verticalArrangement = Arrangement.spacedBy(10.dp)
                        ) {
                            items(topics) { topic ->
                                val cardColor = try {
                                    Color(android.graphics.Color.parseColor(topic.colorHex))
                                } catch (e: Exception) {
                                    Color(0xFF38BDF8)
                                }

                                Card(
                                    modifier = Modifier
                                        .fillMaxWidth()
                                        .clip(RoundedCornerShape(16.dp))
                                        .border(2.dp, cardColor.copy(alpha = 0.6f), RoundedCornerShape(16.dp))
                                        .clickable { onTopicSelected(topic) },
                                    colors = CardDefaults.cardColors(containerColor = Color.White),
                                    elevation = CardDefaults.cardElevation(defaultElevation = 3.dp)
                                ) {
                                    Column(
                                        modifier = Modifier
                                            .fillMaxWidth()
                                            .padding(12.dp)
                                    ) {
                                        Row(
                                            modifier = Modifier.fillMaxWidth(),
                                            horizontalArrangement = Arrangement.SpaceBetween,
                                            verticalAlignment = Alignment.CenterVertically
                                        ) {
                                            Text(text = topic.emoji, fontSize = 26.sp)
                                            Box(
                                                modifier = Modifier
                                                    .clip(RoundedCornerShape(8.dp))
                                                    .background(cardColor.copy(alpha = 0.15f))
                                                    .padding(horizontal = 6.dp, vertical = 2.dp)
                                            ) {
                                                Text(
                                                    text = topic.tag,
                                                    fontSize = 9.sp,
                                                    fontWeight = FontWeight.Bold,
                                                    color = cardColor
                                                )
                                            }
                                        }

                                        Spacer(modifier = Modifier.height(6.dp))

                                        Text(
                                            text = topic.title,
                                            fontSize = 13.sp,
                                            fontWeight = FontWeight.Bold,
                                            color = Color(0xFF1E293B),
                                            maxLines = 1
                                        )
                                        Text(
                                            text = topic.titleEn,
                                            fontSize = 10.sp,
                                            color = Color(0xFF94A3B8),
                                            fontWeight = FontWeight.Medium,
                                            maxLines = 1
                                        )

                                        Spacer(modifier = Modifier.height(4.dp))

                                        Text(
                                            text = topic.description,
                                            fontSize = 10.sp,
                                            color = Color(0xFF64748B),
                                            lineHeight = 13.sp,
                                            maxLines = 2
                                        )

                                        Spacer(modifier = Modifier.height(8.dp))

                                        Row(
                                            modifier = Modifier.fillMaxWidth(),
                                            horizontalArrangement = Arrangement.End,
                                            verticalAlignment = Alignment.CenterVertically
                                        ) {
                                            Text(
                                                text = "Khám phá ✨",
                                                fontSize = 10.sp,
                                                fontWeight = FontWeight.Bold,
                                                color = cardColor
                                            )
                                        }
                                    }
                                }
                            }
                        }
                    }

                    Spacer(modifier = Modifier.height(12.dp))

                    // Nút Đổi chủ đề khác (Refresh)
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.Center
                    ) {
                        Button(
                            onClick = onRefresh,
                            colors = ButtonDefaults.buttonColors(containerColor = Color(0xFFE0F2FE)),
                            shape = RoundedCornerShape(12.dp),
                            contentPadding = PaddingValues(horizontal = 16.dp, vertical = 6.dp)
                        ) {
                            Text(
                                text = "🎲 Đổi chủ đề khác",
                                fontSize = 12.sp,
                                fontWeight = FontWeight.Bold,
                                color = Color(0xFF0369A1)
                            )
                        }
                    }
                }
            }
        }
    }
}

