package com.example.digitalhuman.ui

import android.Manifest
import android.content.pm.PackageManager
import android.os.Bundle
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
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
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
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
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.ContextCompat
import com.example.digitalhuman.audio.AudioPlayer
import com.example.digitalhuman.audio.AudioRecorder
import com.example.digitalhuman.network.ConnectionState
import com.example.digitalhuman.network.GeminiLiveClient

class MainActivity : ComponentActivity() {

    // Đổi IP này thành IP máy tính chạy Backend Server (ví dụ: 192.168.1.x hoặc 10.0.2.2 nếu dùng Android Emulator)
    private val BACKEND_WS_URL = "ws://10.0.2.2:8000/ws/live"

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            MaterialTheme {
                Surface(
                    modifier = Modifier.fillMaxSize(),
                    color = Color(0xFF0F172A)
                ) {
                    TutorScreen(serverUrl = BACKEND_WS_URL)
                }
            }
        }
    }
}

@Composable
fun TutorScreen(serverUrl: String) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()

    var connectionState by remember { mutableStateOf(ConnectionState.DISCONNECTED) }
    var robotAmplitude by remember { mutableFloatStateOf(0f) }
    var userVolume by remember { mutableFloatStateOf(0f) }
    var isSessionActive by remember { mutableStateOf(false) }

    // Khởi tạo Audio Player
    val audioPlayer = remember {
        AudioPlayer(
            onOutputAmplitude = { amp ->
                robotAmplitude = amp
            }
        )
    }

    // Khởi tạo Client WebSocket
    val client = remember {
        GeminiLiveClient(
            serverUrl = serverUrl,
            onAudioReceived = { audioBytes ->
                audioPlayer.enqueueAudio(audioBytes)
            },
            onStateChanged = { newState ->
                connectionState = newState
            },
            onInterrupted = {
                audioPlayer.stopAndFlush()
            }
        )
    }

    // Khởi tạo Audio Recorder
    val audioRecorder = remember {
        AudioRecorder(
            onAudioChunk = { chunk ->
                client.sendAudioChunk(chunk)
            },
            onInputVolume = { vol ->
                userVolume = vol
            }
        )
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
            Toast.makeText(context, "Cần cấp quyền Micro để trò chuyện với bạn Robo!", Toast.LENGTH_SHORT).show()
        }
    }

    DisposableEffect(Unit) {
        onDispose {
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
        horizontalAlignment = Alignment.CenterAlignmentHorizontally,
        verticalArrangement = Arrangement.SpaceBetween
    ) {
        // 1. Header: Trạng thái kết nối
        Column(horizontalAlignment = Alignment.CenterAlignmentHorizontally) {
            Text(
                text = "ROBO ENGLISH BUDDY",
                color = Color.White,
                fontSize = 22.sp,
                fontWeight = FontWeight.Bold,
                letterSpacing = 2.sp
            )
            Spacer(modifier = Modifier.height(8.dp))
            StatusPill(state = connectionState)
        }

        // 2. Avatar Robot 2D ở trung tâm
        Box(
            modifier = Modifier
                .weight(1f)
                .fillMaxWidth(),
            contentAlignment = Alignment.Center
        ) {
            RobotAvatar(
                state = connectionState,
                amplitude = robotAmplitude
            )
        }

        // 3. Khung hướng dẫn & Nút tương tác
        Column(
            modifier = Modifier.fillMaxWidth(),
            horizontalAlignment = Alignment.CenterAlignmentHorizontally
        ) {
            InstructionCard(state = connectionState)

            Spacer(modifier = Modifier.height(20.dp))

            // Nút Bắt đầu / Kết thúc buổi học
            Button(
                onClick = {
                    if (!isSessionActive) {
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
                    text = if (isSessionActive) "Dừng trò chuyện" else "Bắt đầu nói chuyện với Robo",
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
        ConnectionState.DISCONNECTED -> Triple(Color(0xFF475569), Color.White, "Chưa kết nối")
        ConnectionState.CONNECTING -> Triple(Color(0xFFF59E0B), Color.Black, "Đang kết nối...")
        ConnectionState.CONNECTED -> Triple(Color(0xFF10B981), Color.White, "Đã sẵn sàng")
        ConnectionState.LISTENING -> Triple(Color(0xFF06B6D4), Color.Black, "Đang lắng nghe bé nói...")
        ConnectionState.THINKING -> Triple(Color(0xFF8B5CF6), Color.White, "Robo đang suy nghĩ...")
        ConnectionState.SPEAKING -> Triple(Color(0xFF10B981), Color.White, "Robo đang nói chuyện")
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

@Composable
fun InstructionCard(state: ConnectionState) {
    val hint = when (state) {
        ConnectionState.DISCONNECTED -> "Nhấn nút màu xanh bên dưới để bắt đầu luyện nói tiếng Anh nhé!"
        ConnectionState.LISTENING -> "Bé hãy nói tiếng Anh hoặc tiếng Việt bất kỳ, Robo luôn lắng nghe!"
        ConnectionState.SPEAKING -> "Robo đang trả lời, bé có thể nói chen ngang bất cứ lúc nào."
        ConnectionState.THINKING -> "Chờ Robo một chút xíu nhé..."
        else -> "Hãy cùng nhau học những từ vựng thật vui nào!"
    }

    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(18.dp),
        colors = CardDefaults.cardColors(containerColor = Color(0xFF1E293B).copy(alpha = 0.85f))
    ) {
        Text(
            text = hint,
            color = Color(0xFFE2E8F0),
            fontSize = 14.sp,
            textAlign = TextAlign.Center,
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp)
        )
    }
}
