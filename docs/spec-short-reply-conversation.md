# Spec: Giữ mạch trò chuyện với câu đáp ngắn

## Objective

Luna phải nghe được câu đáp ngắn sau lời khơi chuyện và chờ xử lý lượt nói đó trước khi tự mở chủ đề khác. Trạng thái trên màn hình phải phản ánh đúng việc đang nghe, đang nghĩ và đang nói; năng lượng thấp không được khiến Luna nhắm mắt suốt buổi.

## Tech stack and commands

- Android: Kotlin/Jetpack Compose, Silero VAD 2.0.10; `cd android; .\gradlew.bat :app:testDebugUnitTest :app:assembleDebug`.
- Backend: Python, Google GenAI Live API; `python -m unittest discover -s backend/tests`.
- Kiểm tra thật: cài APK debug lên Samsung SM-A235F, đọc log Android và VPS theo thời gian, không xuất nội dung lời nói của trẻ.

## Structure and code style

- `android/app/src/main/java/com/example/digitalhuman/audio/`: thu âm và chốt lượt nói.
- `android/app/src/main/java/com/example/digitalhuman/ui/`: trạng thái và biểu cảm Luna.
- `backend/main.py`: cấu hình Live API và nhịp khơi chuyện.
- Kiểm thử ở `android/app/src/test/` và `backend/tests/`. Giữ hàm nhỏ, chú thích tiếng Việt cho logic hội thoại.

## Success criteria

1. Câu đáp ngắn sau khi Luna dứt lời được gửi với ranh giới bắt đầu/kết thúc lượt rõ ràng; câu dài vẫn hoạt động. Chống vọng khi Luna còn nói không bị bỏ đi.
2. Trong khi chờ Gemini xử lý lời bé, bộ hẹn giờ không phát lời khơi chuyện khác. Sau khi Luna hoàn tất phản hồi, nhịp chủ động mới có thể tiếp tục.
3. App không hiển thị “đang nghĩ” chỉ vì bộ VAD cục bộ vừa kết thúc; phải có tín hiệu nội dung đầu vào đã được Gemini nhận dạng.
4. Năng lượng `tired` không làm Luna nhắm mắt khi nghe/nói; trạng thái ngủ thực sự vẫn có mắt nhắm.
5. Nhãn cảm xúc từ camera không tự tạo lượt Gemini khi bé im lặng; camera vẫn có thể cập nhật trạng thái tại thiết bị.
6. Unit test Android/backend, build APK và kiểm tra trạng thái mắt/log trên điện thoại đều đạt. Kết quả nghe hiểu câu ngắn cần người dùng nói thật để xác nhận.

## Boundaries

- Always: giữ an toàn trẻ em, chống vọng, reconnect và quyền riêng tư của bản ghi âm.
- Ask first: đổi giọng/model, lưu hoặc tải bản ghi âm lên ngoài luồng hiện có.
- Never: ghi nội dung hội thoại vào log mới hoặc xóa dữ liệu người dùng.

## Decision

Người dùng đã duyệt hướng sửa cả bốn điểm sau phiên thử ngày 22/10/2026.
