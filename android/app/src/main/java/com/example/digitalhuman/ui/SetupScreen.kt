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

/**
 * Màn hình cấu hình hồ sơ bé — chỉ hiện 1 lần khi bắt đầu sử dụng app
 * hoặc sau khi reset cấu hình. Dữ liệu này là nguồn cá nhân hóa cho Doraemon.
 *
 * - Tên: textbox
 * - Tuổi & giới tính: dropdown
 * - Sở thích & tính cách: ô text (gõ + dấu phẩy để tạo thẻ) + thẻ gợi ý chọn nhiều
 */
@OptIn(ExperimentalLayoutApi::class)
@Composable
fun SetupScreen(
    onComplete: (String, Int, String, List<String>, String) -> Unit,
    isSubmitting: Boolean,
    submitError: String?,
) {
    var name by remember { mutableStateOf("") }
    var age by remember { mutableStateOf(6) }
    var gender by remember { mutableStateOf("") }
    var hobbiesText by remember { mutableStateOf("") }
    var personalityText by remember { mutableStateOf("") }

    val gradient = Brush.verticalGradient(
        colors = listOf(Color(0xFF0F172A), Color(0xFF1E293B), Color(0xFF0284C7))
    )

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(gradient)
            .verticalScroll(rememberScrollState())
            .padding(24.dp),
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        Spacer(modifier = Modifier.height(24.dp))

        Text(
            text = "CHÀO BÉ!",
            color = Color.White,
            fontSize = 26.sp,
            fontWeight = FontWeight.Bold,
            letterSpacing = 2.sp
        )
        Spacer(modifier = Modifier.height(8.dp))
        Text(
            text = "Doraemon muốn làm quen với bé. Bố mẹ hãy điền giúp bé nhé!",
            color = Color(0xFFE2E8F0),
            fontSize = 14.sp,
            textAlign = TextAlign.Center
        )

        Spacer(modifier = Modifier.height(20.dp))

        Card(
            modifier = Modifier.fillMaxWidth(),
            shape = RoundedCornerShape(18.dp),
            colors = CardDefaults.cardColors(containerColor = Color(0xFF1E293B).copy(alpha = 0.9f))
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
                GenderDropdown(gender = gender, onGenderChange = { gender = it })

                // 4. Sở thích: ô text + thẻ
                SectionLabel("4. Sở thích của bé (gõ + dấu phẩy hoặc chọn thẻ)")
                TagInputField(
                    value = hobbiesText,
                    onValueChange = { hobbiesText = it },
                    placeholder = "Ví dụ: khủng long, vẽ tranh",
                    presetOptions = HOBBY_OPTIONS
                )

                // 5. Tính cách: ô text + thẻ
                SectionLabel("5. Tính cách của bé (gõ + dấu phẩy hoặc chọn thẻ)")
                TagInputField(
                    value = personalityText,
                    onValueChange = { personalityText = it },
                    placeholder = "Ví dụ: hoạt bát, tò mò",
                    presetOptions = PERSONALITY_OPTIONS
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
        }

        Spacer(modifier = Modifier.height(20.dp))

        val canSubmit = name.isNotBlank() && age in 3..15 && gender.isNotBlank()

        Button(
            onClick = {
                val hobbies = hobbiesText
                    .split(",")
                    .map { it.trim() }
                    .filter { it.isNotEmpty() }
                    .distinct()
                onComplete(name.trim(), age, gender, hobbies, personalityText.trim())
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
                text = if (isSubmitting) "Đang lưu..." else "Bắt đầu trò chuyện với Doraemon",
                fontSize = 18.sp,
                fontWeight = FontWeight.Bold,
                color = Color.White
            )
        }

        Spacer(modifier = Modifier.height(24.dp))
    }
}

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
                        text = { Text("$option tuổi", color = Color(0xFFE2E8F0)) },
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
            Column(modifier = Modifier.background(Color(0xFF1E293B))) {
                options.forEach { (value, label) ->
                    DropdownMenuItem(
                        text = { Text(label, color = Color(0xFFE2E8F0)) },
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
            placeholder = { Text(placeholder, color = Color(0xFF64748B)) },
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
                        label = { Text(tag, color = Color.White, fontSize = 13.sp) },
                        trailingIcon = {
                            Text(
                                text = "×",
                                color = Color(0xFF94A3B8),
                                fontWeight = FontWeight.Bold,
                                fontSize = 14.sp
                            )
                        },
                        colors = InputChipDefaults.inputChipColors(
                            containerColor = Color(0xFF06B6D4).copy(alpha = 0.25f),
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
                    label = { Text(option) },
                    colors = FilterChipDefaults.filterChipColors(
                        containerColor = Color(0xFF0F172A),
                        labelColor = Color(0xFFE2E8F0),
                        selectedContainerColor = Color(0xFF06B6D4).copy(alpha = 0.35f),
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
        color = Color(0xFFFBBF24),
        fontSize = 15.sp,
        fontWeight = FontWeight.SemiBold
    )
}

@Composable
private fun textFieldColors() = OutlinedTextFieldDefaults.colors(
    focusedBorderColor = Color(0xFF06B6D4),
    unfocusedBorderColor = Color(0xFF475569),
    focusedTextColor = Color.White,
    unfocusedTextColor = Color.White,
    cursorColor = Color(0xFF06B6D4)
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
