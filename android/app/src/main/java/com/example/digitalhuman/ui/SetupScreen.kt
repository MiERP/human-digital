package com.example.digitalhuman.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ExposedDropdownMenuDefaults
import androidx.compose.material3.FilterChip
import androidx.compose.material3.FilterChipDefaults
import androidx.compose.material3.InputChip
import androidx.compose.material3.InputChipDefaults
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.width
import androidx.compose.material3.TextButton
import androidx.compose.ui.draw.clip
import com.example.digitalhuman.network.CompanionInfo

/**
 * Màn hình cấu hình hồ sơ bé — chỉ hiện 1 lần khi bắt đầu sử dụng app
 * hoặc sau khi reset cấu hình. Dữ liệu này là nguồn cá nhân hóa cho nhân vật đồng hành.
 *
 * - Tên: textbox
 * - Tuổi & giới tính: dropdown
 * - Nhân vật đồng hành: chọn từ bộ avatar dựng sẵn + đặt tên riêng
 * - Sở thích & tính cách: ô text (gõ + dấu phẩy để tạo thẻ) + thẻ gợi ý chọn nhiều
 */
@OptIn(ExperimentalLayoutApi::class)
@Composable
fun SetupScreen(
    onComplete: (String, Int, String, List<String>, String, String, String, String, String) -> Unit,
    isSubmitting: Boolean,
    submitError: String?,
    serverUrl: String = "",
    onOpenServerConfig: () -> Unit = {},
) {
    var name by remember { mutableStateOf("") }
    var age by remember { mutableStateOf(6) }
    var gender by remember { mutableStateOf("") }
    var hobbiesText by remember { mutableStateOf("") }
    var personalityText by remember { mutableStateOf("") }
    var parentPin by remember { mutableStateOf("1234") }
    var companionId by remember { mutableStateOf("boy_blue") }
    var companionName by remember { mutableStateOf("") }
    var companionNameCustomized by remember { mutableStateOf(false) }
    var companionTouched by remember { mutableStateOf(false) }

    val selectedCompanion = COMPANION_CHOICES.firstOrNull { it.id == companionId }
        ?: COMPANION_CHOICES.first()

    val hostDisplay = remember(serverUrl) {
        serverUrl
            .removePrefix("ws://")
            .removePrefix("wss://")
            .substringBefore("/ws/live")
            .ifBlank { "Chưa đặt" }
    }

    val gradient = Brush.verticalGradient(
        colors = listOf(
            Color(0xFF38BDF8),
            Color(0xFF0284C7),
            Color(0xFFBAE6FD)
        )
    )

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(gradient)
            .verticalScroll(rememberScrollState())
            .padding(20.dp),
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        Spacer(modifier = Modifier.height(8.dp))

        // Badge cấu hình IP máy chủ ở đầu màn hình
        Row(
            modifier = Modifier
                .clip(RoundedCornerShape(20.dp))
                .background(Color.White.copy(alpha = 0.25f))
                .clickable { onOpenServerConfig() }
                .padding(horizontal = 14.dp, vertical = 6.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text(
                text = "🌐 $hostDisplay",
                color = Color.White,
                fontSize = 12.sp,
                fontWeight = FontWeight.Bold
            )
            Spacer(modifier = Modifier.width(6.dp))
            Text(
                text = "⚙ Đổi IP",
                color = Color(0xFFFEF08A),
                fontSize = 12.sp,
                fontWeight = FontWeight.Bold
            )
        }

        Spacer(modifier = Modifier.height(14.dp))

        Text(
            text = "CHÀO BẠN NHỎ! 🐱",
            color = Color.White,
            fontSize = 24.sp,
            fontWeight = FontWeight.Black,
            letterSpacing = 1.sp
        )
        Spacer(modifier = Modifier.height(6.dp))
        Text(
            text = "Nhân vật đồng hành rất muốn làm bạn với bé. Bố mẹ hãy điền thông tin giúp bé nhé!",
            color = Color.White.copy(alpha = 0.95f),
            fontSize = 13.sp,
            textAlign = TextAlign.Center
        )

        Spacer(modifier = Modifier.height(18.dp))

        Card(
            modifier = Modifier.fillMaxWidth(),
            shape = RoundedCornerShape(22.dp),
            colors = CardDefaults.cardColors(containerColor = Color.White.copy(alpha = 0.95f))
        ) {
            Column(
                modifier = Modifier.padding(20.dp),
                verticalArrangement = Arrangement.spacedBy(14.dp)
            ) {
                // 1. Tên (textbox)
                SectionLabel("1. Tên của bé")
                OutlinedTextField(
                    value = name,
                    onValueChange = { name = it },
                    modifier = Modifier.fillMaxWidth(),
                    placeholder = { Text("Ví dụ: Minh", color = Color(0xFF64748B)) },
                    singleLine = true,
                    colors = textFieldColors()
                )

                // 2. Tuổi (dropdown)
                SectionLabel("2. Tuổi của bé")
                AgeDropdown(age = age, onAgeChange = { age = it })

                // 3. Giới tính (dropdown)
                SectionLabel("3. Giới tính")
                GenderDropdown(
                    gender = gender,
                    onGenderChange = { newGender ->
                        gender = newGender
                        // Tự gợi ý nhân vật theo giới tính nếu phụ huynh chưa tự chọn.
                        if (!companionTouched) {
                            companionId = if (newGender == "female") "girl_pink" else "boy_blue"
                        }
                    }
                )

                // 4. Nhân vật đồng hành (bộ avatar dựng sẵn + tên riêng)
                SectionLabel("4. Chọn nhân vật đồng hành cho bé")
                CompanionPicker(
                    choices = COMPANION_CHOICES,
                    selectedId = companionId,
                    onSelect = { companion ->
                        companionTouched = true
                        companionId = companion.id
                        companionName = nameAfterCompanionChoice(
                            companionName, companionNameCustomized, companion.name,
                        )
                    }
                )
                Spacer(modifier = Modifier.height(8.dp))
                OutlinedTextField(
                    value = companionName,
                    onValueChange = {
                        companionName = it
                        companionNameCustomized = it.isNotBlank()
                    },
                    modifier = Modifier.fillMaxWidth(),
                    placeholder = { Text("Tên nhân vật (bé tự đặt, vd: ${selectedCompanion.name})", color = Color(0xFF64748B)) },
                    singleLine = true,
                    colors = textFieldColors()
                )

                // 5. Sở thích: ô text + thẻ
                SectionLabel("5. Sở thích của bé (gõ + dấu phẩy hoặc chọn thẻ)")
                TagInputField(
                    value = hobbiesText,
                    onValueChange = { hobbiesText = it },
                    placeholder = "Ví dụ: khủng long, vẽ tranh",
                    presetOptions = HOBBY_OPTIONS
                )

                // 6. Tính cách: ô text + thẻ
                SectionLabel("6. Tính cách của bé (gõ + dấu phẩy hoặc chọn thẻ)")
                TagInputField(
                    value = personalityText,
                    onValueChange = { personalityText = it },
                    placeholder = "Ví dụ: hoạt bát, tò mò",
                    presetOptions = PERSONALITY_OPTIONS
                )
            }
        }

        Spacer(modifier = Modifier.height(14.dp))

        // Card 4: Mã PIN phụ huynh để bảo vệ Góc Phụ Huynh
        Card(
            modifier = Modifier.fillMaxWidth(),
            shape = RoundedCornerShape(20.dp),
            colors = CardDefaults.cardColors(containerColor = Color.White)
        ) {
            Column(modifier = Modifier.padding(18.dp)) {
                SectionLabel("🔐 MÃ PIN PHỤ HUYNH (ĐỂ TRUY CẬP BÁO CÁO & CÀI ĐẶT)")
                Spacer(modifier = Modifier.height(8.dp))
                OutlinedTextField(
                    value = parentPin,
                    onValueChange = { if (it.length <= 6) parentPin = it },
                    placeholder = { Text("4 số (mặc định: 1234)", color = Color.Gray) },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                    colors = textFieldColors()
                )
                Text(
                    text = "Dùng để mở Góc Phụ Huynh xem tiến độ học tập và chỉnh sửa hồ sơ sau này.",
                    fontSize = 11.sp,
                    color = Color(0xFF64748B),
                    modifier = Modifier.padding(top = 4.dp)
                )
            }
        }

        if (submitError != null) {
            Spacer(modifier = Modifier.height(12.dp))
            Text(
                text = submitError,
                color = Color(0xFFFCA5A5),
                fontSize = 13.sp,
                textAlign = TextAlign.Center
            )
            Spacer(modifier = Modifier.height(6.dp))
            TextButton(onClick = onOpenServerConfig) {
                Text(
                    text = "⚙ Đổi IP / Cổng máy chủ ($hostDisplay)",
                    color = Color(0xFF38BDF8),
                    fontSize = 13.sp,
                    fontWeight = FontWeight.SemiBold
                )
            }
        }

        Spacer(modifier = Modifier.height(20.dp))

        val canSubmit = name.isNotBlank() && age in 3..15 && gender.isNotBlank() && parentPin.length >= 4

        Button(
            onClick = {
                val hobbies = hobbiesText
                    .split(",")
                    .map { it.trim() }
                    .filter { it.isNotEmpty() }
                    .distinct()
                onComplete(
                    name.trim(), age, gender, hobbies, personalityText.trim(), parentPin.trim(),
                    companionId, companionName.trim(), selectedCompanion.gender
                )
            },
            enabled = canSubmit && !isSubmitting,
            modifier = Modifier
                .fillMaxWidth()
                .height(60.dp),
            shape = RoundedCornerShape(30.dp),
            colors = ButtonDefaults.buttonColors(
                containerColor = Color(0xFF10B981),
                disabledContainerColor = Color(0xFF334155)
            )
        ) {
            Text(
                text = if (isSubmitting) "Đang lưu..." else "Bắt đầu trò chuyện với ${companionName.ifBlank { selectedCompanion.name }}",
                fontSize = 18.sp,
                fontWeight = FontWeight.Bold,
                color = Color.White
            )
        }

        Spacer(modifier = Modifier.height(24.dp))
    }
}

internal fun nameAfterCompanionChoice(
    currentName: String,
    isCustomized: Boolean,
    presetName: String,
): String = if (isCustomized) currentName else presetName

/**
 * Dropdown tuổi 3-15. Dùng Box + DropdownMenu với nền tối và chữ sáng,
 * tránh lỗi chữ trắng trên nền trắng của menu mặc định.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun AgeDropdown(age: Int, onAgeChange: (Int) -> Unit) {
    var expanded by remember { mutableStateOf(false) }

    Box(modifier = Modifier.fillMaxWidth()) {
        OutlinedTextField(
            value = "$age tuổi",
            onValueChange = {},
            readOnly = true,
            modifier = Modifier.fillMaxWidth(),
            trailingIcon = {
                ExposedDropdownMenuDefaults.TrailingIcon(expanded = expanded)
            },
            colors = textFieldColors()
        )
        Box(
            modifier = Modifier
                .matchParentSize()
                .clickable(
                    interactionSource = remember { MutableInteractionSource() },
                    indication = null
                ) { expanded = !expanded }
        )
        DropdownMenu(
            expanded = expanded,
            onDismissRequest = { expanded = false },
            modifier = Modifier.fillMaxWidth(0.85f)
        ) {
            Column(modifier = Modifier.background(Color(0xFF1E293B))) {
                (3..15).forEach { option ->
                    DropdownMenuItem(
                        text = { Text("$option tuổi", color = Color(0xFF0F172A), fontWeight = FontWeight.Medium) },
                        onClick = {
                            onAgeChange(option)
                            expanded = false
                        }
                    )
                }
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun GenderDropdown(gender: String, onGenderChange: (String) -> Unit) {
    var expanded by remember { mutableStateOf(false) }
    val options = listOf(
        "male" to "Bé trai",
        "female" to "Bé gái",
    )

    Box(modifier = Modifier.fillMaxWidth()) {
        OutlinedTextField(
            value = options.firstOrNull { it.first == gender }?.second ?: "Chọn giới tính",
            onValueChange = {},
            readOnly = true,
            modifier = Modifier.fillMaxWidth(),
            trailingIcon = {
                ExposedDropdownMenuDefaults.TrailingIcon(expanded = expanded)
            },
            colors = textFieldColors()
        )
        Box(
            modifier = Modifier
                .matchParentSize()
                .clickable(
                    interactionSource = remember { MutableInteractionSource() },
                    indication = null
                ) { expanded = !expanded }
        )
        DropdownMenu(
            expanded = expanded,
            onDismissRequest = { expanded = false },
            modifier = Modifier.fillMaxWidth(0.85f)
        ) {
            Column(modifier = Modifier.background(Color.White)) {
                options.forEach { (value, label) ->
                    DropdownMenuItem(
                        text = { Text(label, color = Color(0xFF0F172A), fontWeight = FontWeight.Medium) },
                        onClick = {
                            onGenderChange(value)
                            expanded = false
                        }
                    )
                }
            }
        }
    }
}

/**
 * Ô text dạng thẻ: gõ dữ liệu rồi thêm dấu phẩy -> tạo thẻ (chip).
 * Chọn thẻ gợi ý cũng tự điền vào ô text. Thẻ hiện dưới ô và bấm vào để xóa.
 */
@OptIn(ExperimentalLayoutApi::class, ExperimentalMaterial3Api::class)
@Composable
private fun TagInputField(
    value: String,
    onValueChange: (String) -> Unit,
    placeholder: String,
    presetOptions: List<String>,
) {
    val tags = parseTags(value)

    Column(modifier = Modifier.fillMaxWidth()) {
        OutlinedTextField(
            value = value,
            onValueChange = onValueChange,
            modifier = Modifier.fillMaxWidth(),
            placeholder = { Text(placeholder, color = Color(0xFF94A3B8)) },
            minLines = 1,
            colors = textFieldColors()
        )

        // Thẻ đã tạo (gõ + dấu phẩy, hoặc chọn từ gợi ý). Bấm thẻ để xóa.
        if (tags.isNotEmpty()) {
            Spacer(modifier = Modifier.height(8.dp))
            FlowRow(
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                tags.forEach { tag ->
                    InputChip(
                        selected = false,
                        onClick = { onValueChange(removeTag(value, tag)) },
                        label = { Text(tag, color = Color(0xFF0369A1), fontSize = 13.sp, fontWeight = FontWeight.SemiBold) },
                        trailingIcon = {
                            Text(
                                text = "×",
                                color = Color(0xFF0369A1),
                                fontWeight = FontWeight.Bold,
                                fontSize = 14.sp
                            )
                        },
                        colors = InputChipDefaults.inputChipColors(
                            containerColor = Color(0xFFBAE6FD),
                        )
                    )
                }
            }
        }

        // Thẻ gợi ý chọn nhiều
        Spacer(modifier = Modifier.height(8.dp))
        FlowRow(
            horizontalArrangement = Arrangement.spacedBy(8.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            presetOptions.forEach { option ->
                val isSelected = option in tags
                FilterChip(
                    selected = isSelected,
                    onClick = {
                        onValueChange(
                            if (isSelected) removeTag(value, option) else addTag(value, option)
                        )
                    },
                    label = { Text(option, fontSize = 12.sp) },
                    colors = FilterChipDefaults.filterChipColors(
                        containerColor = Color(0xFFF1F5F9),
                        labelColor = Color(0xFF334155),
                        selectedContainerColor = Color(0xFF0284C7),
                        selectedLabelColor = Color.White,
                    )
                )
            }
        }
    }
}

/** Các đoạn đã kết thúc bằng dấu phẩy là thẻ hoàn chỉnh; đoạn cuối chưa có
 *  dấu phẩy là đang gõ dở, chưa thành thẻ. */
private fun parseTags(text: String): List<String> {
    val parts = text.split(",")
    val complete = if (text.trimEnd().endsWith(",")) parts else parts.dropLast(1)
    return complete.map { it.trim() }.filter { it.isNotEmpty() }.distinct()
}

private fun addTag(text: String, tag: String): String {
    val tags = parseTags(text)
    if (tag in tags) return text
    val base = text.trimEnd().trimEnd(',')
    return if (base.isBlank()) "$tag, " else "$base, $tag, "
}

private fun removeTag(text: String, tag: String): String {
    val tags = parseTags(text).filter { it != tag }
    val draft = if (text.trimEnd().endsWith(",")) "" else text.split(",").last().trim()
    val base = tags.joinToString(", ")
    return when {
        base.isBlank() -> draft
        draft.isBlank() -> "$base, "
        else -> "$base, $draft"
    }
}

@Composable
private fun SectionLabel(text: String) {
    Text(
        text = text,
        color = Color(0xFF0369A1),
        fontSize = 14.sp,
        fontWeight = FontWeight.Bold
    )
}

@Composable
private fun textFieldColors() = OutlinedTextFieldDefaults.colors(
    focusedBorderColor = Color(0xFF0284C7),
    unfocusedBorderColor = Color(0xFFCBD5E1),
    focusedTextColor = Color(0xFF0F172A),
    unfocusedTextColor = Color(0xFF0F172A),
    cursorColor = Color(0xFF0284C7)
)

private val HOBBY_OPTIONS = listOf(
    "Vẽ tranh",
    "Khủng long",
    "Bơi lội",
    "Đọc truyện",
    "Ca hát",
    "Nhảy múa",
    "Siêu anh hùng",
    "Công chúa",
    "Động vật",
    "Xếp Lego",
)

private val PERSONALITY_OPTIONS = listOf(
    "Hoạt bát",
    "Nhút nhát",
    "Hài hước",
    "Hiếu động",
    "Tò mò",
    "Tình cảm",
    "Nghịch ngợm",
    "Điềm tĩnh",
    "Thích được khen",
    "Bướng bỉnh",
)

/** Bộ nhân vật đồng hành dựng sẵn (đồng bộ với backend /api/companions). */
private val COMPANION_CHOICES = listOf(
    CompanionInfo("boy_blue", "Dora", "male", "Puck", listOf("#0288D1", "#4FC3F7", "#FFD54F"), "cap"),
    CompanionInfo("boy_green", "Siro", "male", "Charon", listOf("#2E7D32", "#66BB6A", "#FFCA28"), "cap"),
    CompanionInfo("girl_pink", "Miu", "female", "Aoede", listOf("#EC4899", "#F9A8D4", "#FDE68A"), "bow"),
    CompanionInfo("girl_purple", "Luna", "female", "Kore", listOf("#8B5CF6", "#C4B5FD", "#FDE68A"), "bow"),
)

/**
 * Bộ chọn nhân vật đồng hành: hiển thị các avatar dựng sẵn cho phụ huynh/bé chọn.
 */
@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun CompanionPicker(
    choices: List<CompanionInfo>,
    selectedId: String,
    onSelect: (CompanionInfo) -> Unit,
) {
    FlowRow(
        horizontalArrangement = Arrangement.spacedBy(10.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp)
    ) {
        choices.forEach { companion ->
            val selected = companion.id == selectedId
            val accent = parseCompanionColor(companion.palette.firstOrNull()) ?: Color(0xFF0284C7)
            Column(
                horizontalAlignment = Alignment.CenterHorizontally,
                modifier = Modifier
                    .clip(RoundedCornerShape(16.dp))
                    .background(if (selected) accent.copy(alpha = 0.18f) else Color(0xFFF1F5F9))
                    .clickable { onSelect(companion) }
                    .padding(horizontal = 14.dp, vertical = 10.dp)
            ) {
                Text(if (companion.gender == "female") "🎀" else "🧢", fontSize = 22.sp)
                Spacer(modifier = Modifier.height(4.dp))
                Text(
                    text = companion.name,
                    color = if (selected) accent else Color(0xFF334155),
                    fontWeight = if (selected) FontWeight.Bold else FontWeight.Medium,
                    fontSize = 13.sp
                )
                Text(
                    text = if (companion.gender == "female") "Bé gái" else "Bé trai",
                    color = Color(0xFF64748B),
                    fontSize = 10.sp
                )
            }
        }
    }
}

private fun parseCompanionColor(hex: String?): Color? {
    if (hex.isNullOrBlank()) return null
    return try {
        val clean = hex.trim().removePrefix("#")
        when (clean.length) {
            6 -> Color(0xFF000000L or clean.toLong(16))
            8 -> Color(clean.toLong(16))
            else -> null
        }
    } catch (e: Exception) {
        null
    }
}
