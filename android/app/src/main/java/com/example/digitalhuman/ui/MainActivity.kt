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
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.ContextCompat
import com.example.digitalhuman.audio.AudioPlayer
import com.example.digitalhuman.audio.AudioRecorder
import com.example.digitalhuman.network.ConnectionState
import com.example.digitalhuman.network.GeminiLiveClient
import com.example.digitalhuman.network.ProfileApi
import com.example.digitalhuman.network.RobotEmotion
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.util.UUID

class MainActivity : ComponentActivity() {

    companion object {
        // For Android Emulator use "ws://10.0.2.2:8000/ws/live"
        // For physical device use your computer's LAN IP, e.g. "ws://192.168.1.15:8000/ws/live"
        private const val BACKEND_WS_URL = "ws://192.168.100.194:8000/ws/live"

        // Mỗi bé có hồ sơ cá nhân hóa riêng (memory, tiến độ, search cache tách biệt).
        // child_id được sinh ngẫu nhiên 1 lần trên mỗi máy (xem resolveChildId),
        // nên 2 điện thoại = 2 bé = 2 bộ dữ liệu riêng trên cùng 1 server.

        private const val PREFS_NAME = "robo_setup_prefs"
        private const val KEY_SETUP_DONE = "setup_done"
        private const val KEY_CHILD_ID = "child_id"
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

        val prefs = getSharedPreferences(PREFS_NAME, MODE_PRIVATE)
        val localSetupDone = prefs.getBoolean(KEY_SETUP_DONE, false)
        val childId = resolveChildId(prefs)

        setContent {
            MaterialTheme {
                Surface(
                    modifier = Modifier.fillMaxSize(),
                    color = Color(0xFF0F172A)
                ) {
                    AppRoot(
                        serverUrl = BACKEND_WS_URL,
                        childId = childId,
                        localSetupDone = localSetupDone,
                        onSetupDone = { prefs.edit().putBoolean(KEY_SETUP_DONE, true).apply() },
                        onSetupReset = { prefs.edit().putBoolean(KEY_SETUP_DONE, false).apply() },
                    )
                }
            }
        }
    }
}

/**
 * Gốc điều hướng: quyết định hiện màn cấu hình lần đầu hay màn trò chuyện.
 * - Cờ local (SharedPreferences) giúp không phải gọi API mỗi lần mở app.
 * - Nếu local chưa xong nhưng backend đã có hồ sơ (vd. app bị cài lại),
 *   tự bỏ qua màn setup và đánh dấu local đã xong.
 */
@Composable
fun AppRoot(
    serverUrl: String,
    childId: String,
    localSetupDone: Boolean,
    onSetupDone: () -> Unit,
    onSetupReset: () -> Unit,
) {
    val scope = rememberCoroutineScope()
    var setupDone by remember { mutableStateOf(localSetupDone) }
    var isCheckingBackend by remember { mutableStateOf(!localSetupDone) }
    var isSubmitting by remember { mutableStateOf(false) }
    var submitError by remember { mutableStateOf<String?>(null) }

    val profileApi = remember { ProfileApi(serverUrl) }

    // Kiểm tra backend: nếu đã có hồ sơ hoàn chỉnh (app cài lại/đổi máy),
    // không bắt phụ huynh điền lại từ đầu.
    LaunchedEffect(Unit) {
        if (!setupDone) {
            val backendDone = withContext(Dispatchers.IO) {
                profileApi.isSetupCompleted(childId)
            }
            if (backendDone) {
                setupDone = true
                onSetupDone()
            }
            isCheckingBackend = false
        }
    }

    if (setupDone) {
        TutorScreen(
            serverUrl = serverUrl,
            childId = childId,
            onResetSetup = {
                scope.launch {
                    withContext(Dispatchers.IO) { profileApi.resetSetup(childId) }
                    setupDone = false
                    onSetupReset()
                }
            }
        )
    } else {
        Box(modifier = Modifier.fillMaxSize()) {
            SetupScreen(
                onComplete = { name, age, gender, hobbies, personality ->
                    isSubmitting = true
                    submitError = null
                    scope.launch {
                        val ok = withContext(Dispatchers.IO) {
                            profileApi.submitSetup(childId, name, age, gender, hobbies, personality)
                        }
                        if (ok) {
                            setupDone = true
                            onSetupDone()
                        } else {
                            isSubmitting = false
                            submitError = "Không lưu được hồ sơ. Kiểm tra kết nối với máy chủ rồi thử lại."
                        }
                    }
                },
                isSubmitting = isSubmitting,
                submitError = submitError,
            )

            // Nút reset cấu hình (ẩn ở góc khi đang màn setup không cần thiết)
            if (isCheckingBackend) {
                Box(
                    modifier = Modifier
                        .fillMaxSize()
                        .background(Color(0xFF0F172A).copy(alpha = 0.6f)),
                    contentAlignment = Alignment.Center
                ) {
                    Text(
                        text = "Đang kiểm tra hồ sơ...",
                        color = Color.White,
                        fontSize = 14.sp
                    )
                }
            }
        }
    }
}

@Composable
fun TutorScreen(serverUrl: String, childId: String, onResetSetup: () -> Unit = {}) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()

    // Doraemon ngủ 120s chờ wake word; hết giờ không ai gọi → thoát app hoàn toàn.
    val SLEEP_TIMEOUT_MS = 120_000L
    val TAG = "TutorScreen"

    var connectionState by remember { mutableStateOf(ConnectionState.DISCONNECTED) }
    var robotAmplitude by remember { mutableFloatStateOf(0f) }
    var userVolume by remember { mutableFloatStateOf(0f) }
    var isSessionActive by remember { mutableStateOf(false) }

    // Đồng hồ ngủ: sau session_ended, đếm 120s chờ wake word rồi thoát app.
    var sleepJob by remember { mutableStateOf<Job?>(null) }

    // Trạng thái cảm xúc + năng lượng của Doraemon (do backend EmotionEngine đẩy về).
    var robotEmotion by remember { mutableStateOf(RobotEmotion()) }

    // Encyclopedia Mode: state cho chip bar hỏi chủ đề
    var clarificationRequest by remember { mutableStateOf<ClarificationRequest?>(null) }

    // Xác nhận reset cấu hình (chống bé bấm nhầm khi đang chơi)
    var showResetConfirm by remember { mutableStateOf(false) }

    var audioRecorderRef by remember { mutableStateOf<AudioRecorder?>(null) }

    // Khởi tạo Audio Player với tracking trạng thái phát thực tế
    val audioPlayer = remember {
        AudioPlayer(
            onOutputAmplitude = { amp ->
                robotAmplitude = amp
            },
            onPlaybackStateChanged = { isPlaying ->
                audioRecorderRef?.isPlaybackActive = isPlaying
                if (!isPlaying && isSessionActive && connectionState == ConnectionState.SPEAKING) {
                    connectionState = ConnectionState.LISTENING
                }
            }
        )
    }

    // Khởi tạo Client WebSocket
    val client = remember {
        GeminiLiveClient(
            serverUrl = serverUrl,
            childId = childId,
            onAudioReceived = { audioBytes ->
                connectionState = ConnectionState.SPEAKING
                audioRecorderRef?.onPlaybackChunkReceived()
                audioPlayer.enqueueAudio(audioBytes)
            },
            onStateChanged = { newState ->
                when (newState) {
                    ConnectionState.CONNECTED -> connectionState = ConnectionState.LISTENING
                    ConnectionState.SLEEPING -> connectionState = ConnectionState.SLEEPING
                    ConnectionState.DISCONNECTED, ConnectionState.ERROR -> connectionState = newState
                    else -> Unit
                }
            },
            onInterrupted = {
                audioPlayer.stopAndFlush()
                connectionState = ConnectionState.LISTENING
            },
            onEmotionChanged = { emotion ->
                robotEmotion = emotion
            },
            onSessionEnded = {
                // Doraemon đã chào tạm biệt xong: tắt mic + loa, avatar chuyển "ngủ".
                // Giữ màn "ngủ" 120s — bé muốn nói tiếp thì bấm nút "Đánh thức Doraemon";
                // hết giờ không bấm → app tự thoát hoàn toàn (như bấm Dừng trò chuyện).
                audioRecorderRef?.stopRecording()
                audioPlayer.stopAndFlush()
                isSessionActive = false
                sleepJob?.cancel()
                sleepJob = scope.launch {
                    delay(SLEEP_TIMEOUT_MS)
                    Log.i(TAG, "Doraemon slept ${SLEEP_TIMEOUT_MS}ms — exiting app.")
                    (context as? Activity)?.finishAndRemoveTask()
                }
            },
            onClarificationRequest = { question, options ->
                // Hiển thị chip bar trên UI để bé chọn chủ đề.
                // Tự động ẩn chip bar cũ (nếu có) trước khi hiện chip mới.
                if (options.isNotEmpty()) {
                    clarificationRequest = ClarificationRequest(question, options)
                }
            }
        )
    }

    // Khởi tạo Audio Recorder với Smart VAD callbacks
    val audioRecorder = remember {
        AudioRecorder(
            context = context,
            onAudioChunk = { chunk ->
                client.sendAudioChunk(chunk)
            },
            onInputVolume = { vol ->
                userVolume = vol
            },
            onSpeechStarted = {
                // Client-side VAD: báo cho Gemini biết user bắt đầu nói.
                // Phải gửi TRƯỚC khi audio chunks của utterance này được stream lên.
                // Khi Doraemon đang ngủ: vẫn gửi audio lên (tai mở) nhưng không đổi UI —
                // chỉ backend quyết định có phải wake word không (event woke_up).
                client.notifyActivityStart()
                if (connectionState != ConnectionState.SPEAKING &&
                    connectionState != ConnectionState.SLEEPING
                ) {
                    connectionState = ConnectionState.LISTENING
                }
            },
            onSpeechEnded = {
                // Client-side VAD: báo cho Gemini biết user đã nói xong,
                // Gemini sẽ finalize turn và generate response.
                client.notifyActivityEnd()
                if (connectionState != ConnectionState.SPEAKING &&
                    connectionState != ConnectionState.SLEEPING
                ) {
                    connectionState = ConnectionState.THINKING
                }
            }
        ).also { audioRecorderRef = it }
    }

    // Permission launcher
    val permissionLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.RequestPermission()
    ) { isGranted ->
        if (isGranted) {
            isSessionActive = true
            audioPlayer.start(scope)
            client.connect()
            audioRecorder.startRecording(scope)
        } else {
            Toast.makeText(context, "Cần cấp quyền Micro để trò chuyện với Doraemon!", Toast.LENGTH_SHORT).show()
        }
    }

    DisposableEffect(Unit) {
        onDispose {
            sleepJob?.cancel()
            audioRecorder.stopRecording()
            audioPlayer.release()
            client.disconnect()
        }
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(
                Brush.verticalGradient(
                    colors = listOf(Color(0xFF0F172A), Color(0xFF1E293B), Color(0xFF0284C7))
                )
            )
            .padding(24.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.SpaceBetween
    ) {
        // 1. Header: Trạng thái kết nối
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.Center
            ) {
                Text(
                    text = "DORAEMON",
                    color = Color.White,
                    fontSize = 24.sp,
                    fontWeight = FontWeight.Bold,
                    letterSpacing = 2.sp
                )
                Spacer(modifier = Modifier.width(8.dp))
                TextButton(onClick = { showResetConfirm = true }) {
                    Text(
                        text = "⚙",
                        color = Color(0xFF94A3B8),
                        fontSize = 16.sp
                    )
                }
            }
            Spacer(modifier = Modifier.height(8.dp))
            StatusPill(state = connectionState)
        }

        // Dialog xác nhận reset cấu hình
        if (showResetConfirm) {
            androidx.compose.material3.AlertDialog(
                onDismissRequest = { showResetConfirm = false },
                title = { Text("Cấu hình lại hồ sơ bé?") },
                text = { Text("Màn hình cấu hình tên, tuổi, sở thích sẽ hiện lại. Dữ liệu trò chuyện hiện tại vẫn được giữ.") },
                confirmButton = {
                    TextButton(onClick = {
                        showResetConfirm = false
                        onResetSetup()
                    }) {
                        Text("Cấu hình lại", color = Color(0xFFEF4444))
                    }
                },
                dismissButton = {
                    TextButton(onClick = { showResetConfirm = false }) {
                        Text("Hủy")
                    }
                }
            )
        }

        // 2. Avatar Doraemon 2D ở trung tâm
        Box(
            modifier = Modifier
                .weight(1f)
                .fillMaxWidth(),
            contentAlignment = Alignment.Center
        ) {
            DoraemonAvatar(
                state = connectionState,
                amplitude = robotAmplitude,
                emotion = robotEmotion,
            )
        }

        // 3. Nút tương tác
        Column(
            modifier = Modifier.fillMaxWidth(),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            // Chip bar cho Encyclopedia Mode (chỉ hiện khi có clarification request)
            clarificationRequest?.let { req ->
                Spacer(modifier = Modifier.height(12.dp))
                ClarificationChipBar(
                    request = req,
                    onChoiceSelected = { choice ->
                        client.sendClarificationResponse(choice)
                        // Ẩn chip bar ngay sau khi tap
                        clarificationRequest = null
                    }
                )
            }

            Spacer(modifier = Modifier.height(20.dp))

            // Nút Bắt đầu / Đánh thức Doraemon / Kết thúc buổi học
            Button(
                onClick = {
                    if (connectionState == ConnectionState.SLEEPING) {
                        // Doraemon đang ngủ — đánh thức để trò chuyện tiếp.
                        client.wakeUp()
                        isSessionActive = true
                        audioPlayer.start(scope)
                        client.connect()
                        audioRecorder.startRecording(scope)
                    } else if (!isSessionActive) {
                        val hasPermission = ContextCompat.checkSelfPermission(
                            context,
                            Manifest.permission.RECORD_AUDIO
                        ) == PackageManager.PERMISSION_GRANTED

                        if (hasPermission) {
                            isSessionActive = true
                            audioPlayer.start(scope)
                            client.connect()
                            audioRecorder.startRecording(scope)
                        } else {
                            permissionLauncher.launch(Manifest.permission.RECORD_AUDIO)
                        }
                    } else {
                        isSessionActive = false
                        audioRecorder.stopRecording()
                        audioPlayer.stopAndFlush()
                        client.disconnect()
                    }
                },
                modifier = Modifier
                    .fillMaxWidth()
                    .height(60.dp),
                shape = RoundedCornerShape(30.dp),
                colors = ButtonDefaults.buttonColors(
                    containerColor = if (isSessionActive) Color(0xFFEF4444) else Color(0xFF10B981)
                )
            ) {
                Text(
                    text = when {
                        connectionState == ConnectionState.SLEEPING -> "Đánh thức Doraemon"
                        isSessionActive -> "DỪNG"
                        else -> "BẮT ĐẦU"
                    },
                    fontSize = 18.sp,
                    fontWeight = FontWeight.Bold,
                    color = Color.White
                )
            }
        }
    }
}

@Composable
fun StatusPill(state: ConnectionState) {
    val (bgColor, textColor, label) = when (state) {
        ConnectionState.IDLE -> Triple(Color(0xFF475569), Color.White, "Chưa kết nối")
        ConnectionState.DISCONNECTED -> Triple(Color(0xFF475569), Color.White, "Chưa kết nối")
        ConnectionState.CONNECTING -> Triple(Color(0xFFF59E0B), Color.Black, "Đang kết nối...")
        ConnectionState.CONNECTED -> Triple(Color(0xFF10B981), Color.White, "Đã sẵn sàng")
        ConnectionState.LISTENING -> Triple(Color(0xFF06B6D4), Color.Black, "Doraemon đang lắng nghe...")
        ConnectionState.THINKING -> Triple(Color(0xFF8B5CF6), Color.White, "Doraemon đang suy nghĩ...")
        ConnectionState.SPEAKING -> Triple(Color(0xFF10B981), Color.White, "Doraemon đang nói chuyện")
        ConnectionState.SLEEPING -> Triple(Color(0xFF6366F1), Color.White, "Doraemon đang ngủ...")
        ConnectionState.ERROR -> Triple(Color(0xFFEF4444), Color.White, "Lỗi kết nối")
    }

    Row(
        modifier = Modifier
            .clip(RoundedCornerShape(16.dp))
            .background(bgColor)
            .padding(horizontal = 14.dp, vertical = 6.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Box(
            modifier = Modifier
                .size(8.dp)
                .clip(CircleShape)
                .background(textColor)
        )
        Spacer(modifier = Modifier.width(8.dp))
        Text(
            text = label,
            color = textColor,
            fontSize = 13.sp,
            fontWeight = FontWeight.SemiBold
        )
    }
}

/**
 * Data class đại diện cho 1 yêu cầu làm rõ chủ đề từ backend.
 * Dùng cho Encyclopedia Mode: khi câu hỏi của bé mơ hồ, Robo hỏi lại
 * và Android hiển thị danh sách chip chủ đề để bé chọn.
 */
data class ClarificationRequest(
    val question: String,
    val options: List<String>,
)

/**
 * Composable hiển thị 1 thanh chip ngang với các lựa chọn chủ đề.
 * Tap vào chip → gửi choice về backend qua GeminiLiveClient.
 * Thiết kế đơn giản, dễ hiểu cho trẻ em: chữ to, nền cyan, border rõ ràng.
 */
@Composable
fun ClarificationChipBar(
    request: ClarificationRequest,
    onChoiceSelected: (String) -> Unit,
) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 4.dp),
        horizontalAlignment = Alignment.Start,
    ) {
        Text(
            text = "🤔 ${request.question}",
            color = Color(0xFFFBBF24),
            fontSize = 15.sp,
            fontWeight = FontWeight.SemiBold,
            modifier = Modifier.padding(start = 4.dp, bottom = 8.dp),
        )
        LazyRow(
            horizontalArrangement = Arrangement.spacedBy(8.dp),
            contentPadding = androidx.compose.foundation.layout.PaddingValues(horizontal = 4.dp),
        ) {
            items(request.options) { option ->
                Box(
                    modifier = Modifier
                        .clip(RoundedCornerShape(50))
                        .background(Color(0xFF06B6D4).copy(alpha = 0.18f))
                        .background(
                            Brush.horizontalGradient(
                                colors = listOf(
                                    Color(0xFF0E7490).copy(alpha = 0.4f),
                                    Color(0xFF06B6D4).copy(alpha = 0.4f),
                                )
                            )
                        )
                        .padding(horizontal = 16.dp, vertical = 10.dp)
                        .clickable { onChoiceSelected(option) },
                    contentAlignment = Alignment.Center,
                ) {
                    Text(
                        text = option,
                        color = Color.White,
                        fontSize = 15.sp,
                        fontWeight = FontWeight.Bold,
                    )
                }
            }
        }
    }
}
