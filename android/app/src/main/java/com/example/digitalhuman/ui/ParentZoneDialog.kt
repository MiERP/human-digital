package com.example.digitalhuman.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import com.example.digitalhuman.network.BadgeItem
import com.example.digitalhuman.network.ChildProfileData
import com.example.digitalhuman.network.DailyDigestData
import com.example.digitalhuman.network.ProfileApi
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

/**
 * Giao diện "Góc Phụ Huynh" (In-App Parent Portal) chuẩn thương mại:
 * - Bảo vệ bằng Parental Gate (Mã PIN 4 số của gia đình)
 * - Tab 1: Báo Cáo Tiến Trình Học Tập (Streak, Từ vựng, Huy hiệu, Lời khuyên sư phạm)
 * - Tab 2: Chỉnh Sửa Hồ Sơ Cá Nhân Hóa Của Bé
 * - Tab 3: Bảo Mật, Đổi Mã PIN & Quyền Riêng Tư (COPPA/GDPR)
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ParentZoneDialog(
    childId: String,
    serverUrl: String,
    onDismiss: () -> Unit,
    onProfileUpdated: () -> Unit = {}
) {
    val coroutineScope = rememberCoroutineScope()
    val profileApi = remember(serverUrl) { ProfileApi(serverUrl) }
    val context = androidx.compose.ui.platform.LocalContext.current

    var isUnlocked by remember { mutableStateOf(false) }
    var enteredPin by remember { mutableStateOf("") }
    var pinError by remember { mutableStateOf<String?>(null) }
    var isCheckingPin by remember { mutableStateOf(false) }

    var currentTab by remember { mutableIntStateOf(0) } // 0: Báo cáo, 1: Hồ sơ, 2: Bảo mật

    var digestData by remember { mutableStateOf<DailyDigestData?>(null) }
    var profileData by remember { mutableStateOf<ChildProfileData?>(null) }
    var isLoadingData by remember { mutableStateOf(false) }
    var statusMessage by remember { mutableStateOf<String?>(null) }

    // State chỉnh sửa hồ sơ
    var editName by remember { mutableStateOf("") }
    var editAge by remember { mutableIntStateOf(6) }
    var editGender by remember { mutableStateOf("Nam") }
    var editHobbies by remember { mutableStateOf("") }
    var editPersonality by remember { mutableStateOf("") }
    var editLevel by remember { mutableStateOf("Starters") }
    var editCompanionId by remember { mutableStateOf("boy_blue") }
    var editCompanionName by remember { mutableStateOf("") }

    // State đổi mã PIN
    var oldPinInput by remember { mutableStateOf("") }
    var newPinInput by remember { mutableStateOf("") }
    var pinChangeMsg by remember { mutableStateOf<String?>(null) }

    fun loadData() {
        isLoadingData = true
        coroutineScope.launch(Dispatchers.IO) {
            val digest = profileApi.getDailyDigest(childId)
            val profile = profileApi.getProfile(childId, enteredPin)
            withContext(Dispatchers.Main) {
                digestData = digest
                profileData = profile
                if (profile != null) {
                    editName = profile.name
                    editAge = profile.age
                    editGender = profile.gender
                    editHobbies = profile.hobbies.joinToString(", ")
                    editPersonality = profile.personality
                    editLevel = profile.learningLevel
                    if (profile.companionPersona.isNotBlank()) editCompanionId = profile.companionPersona
                    editCompanionName = profile.companionName
                }
                // Lên lịch nhắc nhở theo kế hoạch học tập (nếu có).
                val plan = digest?.learningPlan
                if (plan != null && plan.isActive && plan.reminderEnabled) {
                    val name = profile?.companionName?.takeIf { it.isNotBlank() }
                        ?: companionDefaultName(editCompanionId)
                    ReminderScheduler.schedule(context, plan.days, plan.startTime, name)
                } else if (digest != null) {
                    ReminderScheduler.cancel(context)
                }
                isLoadingData = false
            }
        }
    }

    Dialog(
        onDismissRequest = onDismiss,
        properties = DialogProperties(usePlatformDefaultWidth = false)
    ) {
        Card(
            modifier = Modifier
                .fillMaxWidth(0.95f)
                .fillMaxHeight(0.92f)
                .padding(8.dp),
            shape = RoundedCornerShape(24.dp),
            colors = CardDefaults.cardColors(containerColor = Color(0xFF0F172A))
        ) {
            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(16.dp)
            ) {
                // Header
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Column {
                        Text(
                            text = "👨‍👩‍👧 Góc Phụ Huynh",
                            fontSize = 20.sp,
                            fontWeight = FontWeight.Black,
                            color = Color(0xFF38BDF8)
                        )
                        Text(
                            text = "Mã bé: $childId",
                            fontSize = 11.sp,
                            color = Color(0xFF94A3B8)
                        )
                    }
                    IconButton(onClick = onDismiss) {
                        Text("✕", fontSize = 18.sp, color = Color(0xFF94A3B8), fontWeight = FontWeight.Bold)
                    }
                }

                Spacer(modifier = Modifier.height(12.dp))

                if (!isUnlocked) {
                    // ==================== MÀN HÌNH KHÓA PHỤ HUYNH (PARENTAL GATE) ====================
                    Column(
                        modifier = Modifier
                            .fillMaxSize()
                            .padding(16.dp),
                        horizontalAlignment = Alignment.CenterHorizontally,
                        verticalArrangement = Arrangement.Center
                    ) {
                        Box(
                            modifier = Modifier
                                .size(64.dp)
                                .clip(CircleShape)
                                .background(Color(0xFF1E293B)),
                            contentAlignment = Alignment.Center
                        ) {
                            Text("🔒", fontSize = 32.sp)
                        }

                        Spacer(modifier = Modifier.height(16.dp))

                        Text(
                            text = "Xác Thực Phụ Huynh",
                            fontSize = 18.sp,
                            fontWeight = FontWeight.Bold,
                            color = Color.White
                        )
                        Text(
                            text = "Nhập mã PIN 4 số của gia đình để truy cập Báo cáo & Cài đặt:",
                            fontSize = 13.sp,
                            color = Color(0xFF94A3B8),
                            textAlign = TextAlign.Center,
                            modifier = Modifier.padding(horizontal = 24.dp, vertical = 8.dp)
                        )

                        OutlinedTextField(
                            value = enteredPin,
                            onValueChange = { if (it.length <= 6) enteredPin = it },
                            placeholder = { Text("Mã PIN (Mặc định: 1234)", color = Color(0xFF64748B)) },
                            visualTransformation = PasswordVisualTransformation(),
                            singleLine = true,
                            colors = OutlinedTextFieldDefaults.colors(
                                focusedTextColor = Color.White,
                                unfocusedTextColor = Color.White,
                                focusedBorderColor = Color(0xFF38BDF8),
                                unfocusedBorderColor = Color(0xFF334155),
                                focusedContainerColor = Color(0xFF1E293B),
                                unfocusedContainerColor = Color(0xFF1E293B)
                            ),
                            shape = RoundedCornerShape(12.dp),
                            modifier = Modifier.fillMaxWidth(0.7f)
                        )

                        if (pinError != null) {
                            Spacer(modifier = Modifier.height(6.dp))
                            Text(pinError ?: "", color = Color(0xFFF87171), fontSize = 12.sp)
                        }

                        Spacer(modifier = Modifier.height(16.dp))

                        Button(
                            onClick = {
                                if (enteredPin.isBlank()) {
                                    pinError = "Vui lòng nhập mã PIN!"
                                    return@Button
                                }
                                isCheckingPin = true
                                pinError = null
                                coroutineScope.launch(Dispatchers.IO) {
                                    val (ok, msg) = profileApi.verifyParentPin(childId, enteredPin)
                                    withContext(Dispatchers.Main) {
                                        isCheckingPin = false
                                        if (ok) {
                                            isUnlocked = true
                                            loadData()
                                        } else {
                                            pinError = msg
                                        }
                                    }
                                }
                            },
                            enabled = !isCheckingPin,
                            colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF0284C7)),
                            shape = RoundedCornerShape(12.dp),
                            modifier = Modifier.fillMaxWidth(0.7f).height(46.dp)
                        ) {
                            if (isCheckingPin) {
                                CircularProgressIndicator(modifier = Modifier.size(20.dp), color = Color.White, strokeWidth = 2.dp)
                            } else {
                                Text("Mở Khóa", fontWeight = FontWeight.Bold)
                            }
                        }

                        Spacer(modifier = Modifier.height(12.dp))
                        Text("💡 Mã PIN mặc định khi mới cài đặt là 1234", fontSize = 11.sp, color = Color(0xFF64748B))
                    }
                } else {
                    // ==================== GIAO DIỆN QUẢN TRỊ KHI ĐÃ MỞ KHÓA ====================
                    // Thanh Tabs
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .clip(RoundedCornerShape(12.dp))
                            .background(Color(0xFF1E293B))
                            .padding(4.dp),
                        horizontalArrangement = Arrangement.SpaceAround
                    ) {
                        TabButton(title = "📊 Báo Cáo", isSelected = currentTab == 0) { currentTab = 0 }
                        TabButton(title = "⚙️ Hồ Sơ Bé", isSelected = currentTab == 1) { currentTab = 1 }
                        TabButton(title = "🔒 Bảo Mật", isSelected = currentTab == 2) { currentTab = 2 }
                    }

                    Spacer(modifier = Modifier.height(12.dp))

                    if (isLoadingData) {
                        Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                            CircularProgressIndicator(color = Color(0xFF38BDF8))
                        }
                    } else {
                        when (currentTab) {
                            0 -> DashboardTab(digestData, onRefresh = { loadData() })
                            1 -> ProfileTab(
                                editName = editName, onNameChange = { editName = it },
                                editAge = editAge, onAgeChange = { editAge = it },
                                editGender = editGender, onGenderChange = { editGender = it },
                                editHobbies = editHobbies, onHobbiesChange = { editHobbies = it },
                                editPersonality = editPersonality, onPersonalityChange = { editPersonality = it },
                                editLevel = editLevel, onLevelChange = { editLevel = it },
                                companionId = editCompanionId, onCompanionChange = { nextId ->
                                    if (editCompanionName.isBlank() ||
                                        editCompanionName == companionDefaultName(editCompanionId)) {
                                        editCompanionName = companionDefaultName(nextId)
                                    }
                                    editCompanionId = nextId
                                },
                                companionName = editCompanionName, onCompanionNameChange = { editCompanionName = it },
                                onSave = {
                                    coroutineScope.launch(Dispatchers.IO) {
                                        val hobbiesList = editHobbies.split(",").map { it.trim() }.filter { it.isNotEmpty() }
                                        val companionGender = COMPANION_OPTIONS
                                            .firstOrNull { it.first == editCompanionId }?.third ?: ""
                                        val (ok, msg) = profileApi.updateProfileWithPin(
                                            childId = childId,
                                            pin = enteredPin,
                                            name = editName,
                                            age = editAge,
                                            gender = editGender,
                                            hobbies = hobbiesList,
                                            personality = editPersonality,
                                            learningLevel = editLevel,
                                            companionPersona = editCompanionId,
                                            companionName = editCompanionName,
                                            companionGender = companionGender
                                        )
                                        withContext(Dispatchers.Main) {
                                            statusMessage = msg
                                            if (ok) onProfileUpdated()
                                        }
                                    }
                                },
                                statusMessage = statusMessage
                            )
                            2 -> SecurityTab(
                                childId = childId,
                                oldPin = oldPinInput, onOldPinChange = { oldPinInput = it },
                                newPin = newPinInput, onNewPinChange = { newPinInput = it },
                                pinChangeMsg = pinChangeMsg,
                                onChangePin = {
                                    coroutineScope.launch(Dispatchers.IO) {
                                        val (ok, msg) = profileApi.setParentPin(childId, oldPinInput, newPinInput)
                                        withContext(Dispatchers.Main) {
                                            pinChangeMsg = msg
                                            if (ok) {
                                                enteredPin = newPinInput
                                                oldPinInput = ""
                                                newPinInput = ""
                                            }
                                        }
                                    }
                                },
                                onDeleteData = {
                                    coroutineScope.launch(Dispatchers.IO) {
                                        val (ok, msg) = profileApi.deleteChildDataWithPin(childId, enteredPin)
                                        withContext(Dispatchers.Main) {
                                            pinChangeMsg = msg
                                            if (ok) {
                                                onProfileUpdated()
                                                onDismiss()
                                            }
                                        }
                                    }
                                }
                            )
                        }
                    }
                }
            }
        }
    }
}

@Composable
fun TabButton(title: String, isSelected: Boolean, onClick: () -> Unit) {
    Box(
        modifier = Modifier
            .clip(RoundedCornerShape(8.dp))
            .background(if (isSelected) Color(0xFF0284C7) else Color.Transparent)
            .clickable(onClick = onClick)
            .padding(horizontal = 14.dp, vertical = 8.dp),
        contentAlignment = Alignment.Center
    ) {
        Text(
            text = title,
            fontSize = 13.sp,
            fontWeight = if (isSelected) FontWeight.Bold else FontWeight.Normal,
            color = if (isSelected) Color.White else Color(0xFF94A3B8)
        )
    }
}

@Composable
fun DashboardTab(digest: DailyDigestData?, onRefresh: () -> Unit) {
    if (digest == null) {
        Column(modifier = Modifier.fillMaxSize(), horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.Center) {
            Text("Chưa có dữ liệu học tập.", color = Color.Gray)
            Button(onClick = onRefresh, modifier = Modifier.padding(top = 8.dp)) { Text("Tải lại") }
        }
        return
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
    ) {
        // Grid 4 thẻ thống kê
        Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            StatCard(modifier = Modifier.weight(1f), icon = "🔥", value = "${digest.streakDays} ngày", label = "Chuỗi học", color = Color(0xFFF59E0B))
            StatCard(modifier = Modifier.weight(1f), icon = "💬", value = "${digest.totalSessions}", label = "Buổi học", color = Color(0xFF38BDF8))
            StatCard(modifier = Modifier.weight(1f), icon = "⭐", value = "${digest.masteredWordsCount}", label = "Từ làm chủ", color = Color(0xFF10B981))
            StatCard(modifier = Modifier.weight(1f), icon = "⏱️", value = "${digest.totalDurationSeconds / 60}p", label = "Thời lượng", color = Color(0xFFA855F7))
        }

        Spacer(modifier = Modifier.height(14.dp))

        // Kế hoạch học tập đã thống nhất + mức tuân thủ
        digest.learningPlan?.let { plan ->
            Card(
                modifier = Modifier.fillMaxWidth(),
                colors = CardDefaults.cardColors(containerColor = Color(0xFF1E293B)),
                shape = RoundedCornerShape(16.dp)
            ) {
                Column(modifier = Modifier.padding(14.dp)) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text("📅", fontSize = 18.sp)
                        Spacer(modifier = Modifier.width(6.dp))
                        Text("Kế Hoạch Học Tập", fontWeight = FontWeight.Bold, color = Color(0xFF38BDF8), fontSize = 14.sp)
                    }
                    Spacer(modifier = Modifier.height(6.dp))
                    val dayLabels = plan.days.joinToString(", ") { vnWeekday(it) }
                    Text("Lịch: $dayLabels lúc ${plan.startTime} (~${plan.durationMinutes} phút)", color = Color(0xFFE2E8F0), fontSize = 13.sp)
                    if (plan.weeklyGoal.isNotBlank()) {
                        Text("Mục tiêu: ${plan.weeklyGoal}", color = Color(0xFFE2E8F0), fontSize = 13.sp)
                    }
                    if (plan.focusTopics.isNotEmpty()) {
                        Text("Chủ đề: ${plan.focusTopics.joinToString(", ")}", color = Color(0xFFE2E8F0), fontSize = 13.sp)
                    }
                    digest.planAdherence?.let { ad ->
                        Spacer(modifier = Modifier.height(6.dp))
                        Text(
                            "Tuần này: ${ad.done}/${ad.planned} buổi đã hoàn thành",
                            color = Color(0xFF10B981),
                            fontSize = 13.sp,
                            fontWeight = FontWeight.SemiBold
                        )
                    }
                }
            }
            Spacer(modifier = Modifier.height(14.dp))
        }

        // Lời khuyên sư phạm từ nhân vật đồng hành
        Card(
            modifier = Modifier.fillMaxWidth(),
            colors = CardDefaults.cardColors(containerColor = Color(0xFF1E293B)),
            shape = RoundedCornerShape(16.dp)
        ) {
            Column(modifier = Modifier.padding(14.dp)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text("💡", fontSize = 18.sp)
                    Spacer(modifier = Modifier.width(6.dp))
                    Text("Lời Nhắn Sư Phạm Của Doraemon", fontWeight = FontWeight.Bold, color = Color(0xFF38BDF8), fontSize = 14.sp)
                }
                Spacer(modifier = Modifier.height(6.dp))
                Text(
                    text = digest.pedagogicalAdvice,
                    color = Color(0xFFE2E8F0),
                    fontSize = 13.sp,
                    lineHeight = 18.sp
                )
            }
        }

        Spacer(modifier = Modifier.height(14.dp))

        // Từ vựng đã làm chủ & cần ôn tập
        Text("📚 Tiến Trình Từ Vựng Tiếng Anh", fontWeight = FontWeight.Bold, color = Color.White, fontSize = 14.sp)
        Spacer(modifier = Modifier.height(6.dp))

        if (digest.masteredWords.isNotEmpty()) {
            Text("✅ Đã phát âm & nhớ chuẩn:", fontSize = 12.sp, color = Color(0xFF10B981), fontWeight = FontWeight.SemiBold)
            Spacer(modifier = Modifier.height(4.dp))
            Row(modifier = Modifier.fillMaxWidth()) {
                Text(digest.masteredWords.joinToString(", "), fontSize = 12.sp, color = Color(0xFFCBD5E1))
            }
            Spacer(modifier = Modifier.height(8.dp))
        }

        if (digest.needsPracticeWords.isNotEmpty()) {
            Text("🎯 Đang luyện tập thêm:", fontSize = 12.sp, color = Color(0xFFF59E0B), fontWeight = FontWeight.SemiBold)
            Spacer(modifier = Modifier.height(4.dp))
            Row(modifier = Modifier.fillMaxWidth()) {
                Text(digest.needsPracticeWords.joinToString(", "), fontSize = 12.sp, color = Color(0xFFCBD5E1))
            }
            Spacer(modifier = Modifier.height(8.dp))
        }

        Spacer(modifier = Modifier.height(10.dp))

        // Huy hiệu bảo bối
        Text("🏅 Bộ Sưu Tập Huy Hiệu Bảo Bối", fontWeight = FontWeight.Bold, color = Color.White, fontSize = 14.sp)
        Spacer(modifier = Modifier.height(8.dp))

        for (badge in digest.badges) {
            BadgeRow(badge)
            Spacer(modifier = Modifier.height(6.dp))
        }
    }
}

@Composable
fun StatCard(modifier: Modifier, icon: String, value: String, label: String, color: Color) {
    Card(
        modifier = modifier,
        colors = CardDefaults.cardColors(containerColor = color.copy(alpha = 0.15f)),
        shape = RoundedCornerShape(12.dp)
    ) {
        Column(
            modifier = Modifier.padding(8.dp).fillMaxWidth(),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            Text(icon, fontSize = 16.sp)
            Text(value, fontSize = 14.sp, fontWeight = FontWeight.Black, color = color)
            Text(label, fontSize = 10.sp, color = Color(0xFF94A3B8))
        }
    }
}

@Composable
fun BadgeRow(badge: BadgeItem) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(10.dp))
            .background(if (badge.unlocked) Color(0xFF1E293B) else Color(0xFF141E33))
            .padding(8.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Text(
            text = badge.icon,
            fontSize = 24.sp,
            modifier = Modifier.alpha(if (badge.unlocked) 1f else 0.3f)
        )
        Spacer(modifier = Modifier.width(10.dp))
        Column(modifier = Modifier.weight(1f)) {
            Text(
                text = badge.title,
                fontWeight = FontWeight.Bold,
                fontSize = 13.sp,
                color = if (badge.unlocked) Color.White else Color.Gray
            )
            Text(text = badge.description, fontSize = 11.sp, color = Color(0xFF94A3B8))
        }
        if (badge.unlocked) {
            Text("ĐÃ ĐẠT", fontSize = 10.sp, color = Color(0xFF10B981), fontWeight = FontWeight.Black)
        }
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
fun ProfileTab(
    editName: String, onNameChange: (String) -> Unit,
    editAge: Int, onAgeChange: (Int) -> Unit,
    editGender: String, onGenderChange: (String) -> Unit,
    editHobbies: String, onHobbiesChange: (String) -> Unit,
    editPersonality: String, onPersonalityChange: (String) -> Unit,
    editLevel: String, onLevelChange: (String) -> Unit,
    companionId: String, onCompanionChange: (String) -> Unit,
    companionName: String, onCompanionNameChange: (String) -> Unit,
    onSave: () -> Unit,
    statusMessage: String?
) {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(bottom = 16.dp)
    ) {
        Text("Tên hoặc Biệt danh của bé:", fontSize = 12.sp, color = Color(0xFF94A3B8), fontWeight = FontWeight.SemiBold)
        OutlinedTextField(
            value = editName, onValueChange = onNameChange,
            modifier = Modifier.fillMaxWidth().padding(top = 4.dp, bottom = 10.dp),
            colors = customTextFieldColors()
        )

        Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Column(modifier = Modifier.weight(1f)) {
                Text("Tuổi của bé:", fontSize = 12.sp, color = Color(0xFF94A3B8), fontWeight = FontWeight.SemiBold)
                OutlinedTextField(
                    value = editAge.toString(),
                    onValueChange = { onAgeChange(it.toIntOrNull() ?: editAge) },
                    modifier = Modifier.fillMaxWidth().padding(top = 4.dp, bottom = 10.dp),
                    colors = customTextFieldColors()
                )
            }
            Column(modifier = Modifier.weight(1f)) {
                Text("Giới tính:", fontSize = 12.sp, color = Color(0xFF94A3B8), fontWeight = FontWeight.SemiBold)
                OutlinedTextField(
                    value = editGender, onValueChange = onGenderChange,
                    modifier = Modifier.fillMaxWidth().padding(top = 4.dp, bottom = 10.dp),
                    colors = customTextFieldColors()
                )
            }
        }

        Text("Sở thích (ngăn cách bằng dấu phẩy):", fontSize = 12.sp, color = Color(0xFF94A3B8), fontWeight = FontWeight.SemiBold)
        OutlinedTextField(
            value = editHobbies, onValueChange = onHobbiesChange,
            placeholder = { Text("vd: Khủng long, Bơi lội, Vẽ tranh...", color = Color(0xFF64748B)) },
            modifier = Modifier.fillMaxWidth().padding(top = 4.dp, bottom = 10.dp),
            colors = customTextFieldColors()
        )

        Text("Tính cách & Phong cách của bé:", fontSize = 12.sp, color = Color(0xFF94A3B8), fontWeight = FontWeight.SemiBold)
        OutlinedTextField(
            value = editPersonality, onValueChange = onPersonalityChange,
            placeholder = { Text("vd: Thích vui nhộn, hơi nhút nhát, thích khen...", color = Color(0xFF64748B)) },
            modifier = Modifier.fillMaxWidth().padding(top = 4.dp, bottom = 10.dp),
            colors = customTextFieldColors()
        )

        Text("Trình độ Tiếng Anh:", fontSize = 12.sp, color = Color(0xFF94A3B8), fontWeight = FontWeight.SemiBold)
        OutlinedTextField(
            value = editLevel, onValueChange = onLevelChange,
            placeholder = { Text("Starters / Movers / Flyers", color = Color(0xFF64748B)) },
            modifier = Modifier.fillMaxWidth().padding(top = 4.dp, bottom = 14.dp),
            colors = customTextFieldColors()
        )

        // Nhân vật đồng hành (avatar dựng sẵn) + tên riêng
        Text("Nhân vật đồng hành:", fontSize = 12.sp, color = Color(0xFF94A3B8), fontWeight = FontWeight.SemiBold)
        FlowRow(
            modifier = Modifier.fillMaxWidth().padding(top = 6.dp, bottom = 8.dp),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            COMPANION_OPTIONS.forEach { (id, label, _) ->
                FilterChip(
                    selected = id == companionId,
                    onClick = { onCompanionChange(id) },
                    label = { Text(label, fontSize = 12.sp) }
                )
            }
        }
        OutlinedTextField(
            value = companionName, onValueChange = onCompanionNameChange,
            placeholder = { Text("Tên nhân vật bé đặt", color = Color(0xFF64748B)) },
            modifier = Modifier.fillMaxWidth().padding(top = 4.dp, bottom = 14.dp),
            colors = customTextFieldColors()
        )

        if (statusMessage != null) {
            Text(statusMessage, color = Color(0xFF38BDF8), fontSize = 12.sp, modifier = Modifier.padding(bottom = 8.dp))
        }

        Button(
            onClick = onSave,
            colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF10B981)),
            shape = RoundedCornerShape(12.dp),
            modifier = Modifier.fillMaxWidth().height(48.dp)
        ) {
            Text("💾 Lưu Thay Đổi Lên Server", fontWeight = FontWeight.Bold, fontSize = 14.sp)
        }
    }
}

@Composable
fun SecurityTab(
    childId: String,
    oldPin: String, onOldPinChange: (String) -> Unit,
    newPin: String, onNewPinChange: (String) -> Unit,
    pinChangeMsg: String?,
    onChangePin: () -> Unit,
    onDeleteData: () -> Unit
) {
    var showDeleteConfirm by remember { mutableStateOf(false) }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(bottom = 16.dp)
    ) {
        Text("🔐 Đổi Mã PIN Phụ Huynh Mới", fontWeight = FontWeight.Bold, color = Color.White, fontSize = 14.sp)
        Spacer(modifier = Modifier.height(8.dp))

        OutlinedTextField(
            value = oldPin, onValueChange = onOldPinChange,
            placeholder = { Text("Mã PIN hiện tại (vd: 1234)", color = Color(0xFF64748B)) },
            visualTransformation = PasswordVisualTransformation(),
            modifier = Modifier.fillMaxWidth().padding(bottom = 8.dp),
            colors = customTextFieldColors()
        )

        OutlinedTextField(
            value = newPin, onValueChange = onNewPinChange,
            placeholder = { Text("Mã PIN mới (4 - 6 số)", color = Color(0xFF64748B)) },
            visualTransformation = PasswordVisualTransformation(),
            modifier = Modifier.fillMaxWidth().padding(bottom = 10.dp),
            colors = customTextFieldColors()
        )

        if (pinChangeMsg != null) {
            Text(pinChangeMsg, color = Color(0xFF38BDF8), fontSize = 12.sp, modifier = Modifier.padding(bottom = 8.dp))
        }

        Button(
            onClick = onChangePin,
            colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF0284C7)),
            shape = RoundedCornerShape(10.dp),
            modifier = Modifier.fillMaxWidth().height(44.dp)
        ) {
            Text("Cập Nhật Mã PIN", fontWeight = FontWeight.Bold)
        }

        Spacer(modifier = Modifier.height(24.dp))

        Text("🛡️ Quyền Riêng Tư Dữ Liệu Trẻ Em (COPPA)", fontWeight = FontWeight.Bold, color = Color(0xFFEF4444), fontSize = 14.sp)
        Text("Bạn có toàn quyền yêu cầu xóa sạch toàn bộ giọng nói, kỷ niệm và tiến độ học tập của bé khỏi máy chủ.", fontSize = 12.sp, color = Color(0xFF94A3B8), modifier = Modifier.padding(vertical = 4.dp))

        Spacer(modifier = Modifier.height(8.dp))

        Button(
            onClick = { showDeleteConfirm = true },
            colors = ButtonDefaults.buttonColors(containerColor = Color(0xFFDC2626)),
            shape = RoundedCornerShape(10.dp),
            modifier = Modifier.fillMaxWidth().height(44.dp)
        ) {
            Text("🗑️ Xóa Vĩnh Viễn Dữ Liệu Của Bé", fontWeight = FontWeight.Bold)
        }

        if (showDeleteConfirm) {
            AlertDialog(
                onDismissRequest = { showDeleteConfirm = false },
                title = { Text("Xác Nhận Xóa Dữ Liệu") },
                text = { Text("Toàn bộ dữ liệu bộ nhớ, tiến trình học tập và sở thích của bé sẽ bị xóa vĩnh viễn trên Server. Hành động này không thể hoàn tác.") },
                confirmButton = {
                    TextButton(onClick = {
                        showDeleteConfirm = false
                        onDeleteData()
                    }) {
                        Text("Xóa Ngay", color = Color.Red, fontWeight = FontWeight.Bold)
                    }
                },
                dismissButton = {
                    TextButton(onClick = { showDeleteConfirm = false }) {
                        Text("Hủy")
                    }
                }
            )
        }
    }
}

@Composable
fun customTextFieldColors() = OutlinedTextFieldDefaults.colors(
    focusedTextColor = Color.White,
    unfocusedTextColor = Color.White,
    focusedBorderColor = Color(0xFF38BDF8),
    unfocusedBorderColor = Color(0xFF334155),
    focusedContainerColor = Color(0xFF1E293B),
    unfocusedContainerColor = Color(0xFF1E293B)
)

/** Bộ nhân vật đồng hành: (id, nhãn hiển thị, giới tính) — đồng bộ với backend. */
private val COMPANION_OPTIONS = listOf(
    Triple("boy_blue", "🧢 Dora", "male"),
    Triple("boy_green", "🧢 Siro", "male"),
    Triple("girl_pink", "🎀 Miu", "female"),
    Triple("girl_purple", "🎀 Luna", "female"),
)

/** Tên mặc định của nhân vật theo id (dùng cho thông báo nhắc nhở). */
private fun companionDefaultName(personaId: String): String = when (personaId) {
    "boy_green" -> "Siro"
    "girl_pink" -> "Miu"
    "girl_purple" -> "Luna"
    else -> "Dora"
}

/** Chuyển mã thứ trong tuần (mon..sun) sang nhãn tiếng Việt. */
private fun vnWeekday(code: String): String = when (code.lowercase().take(3)) {
    "mon" -> "Thứ Hai"
    "tue" -> "Thứ Ba"
    "wed" -> "Thứ Tư"
    "thu" -> "Thứ Năm"
    "fri" -> "Thứ Sáu"
    "sat" -> "Thứ Bảy"
    "sun" -> "Chủ Nhật"
    else -> code
}
