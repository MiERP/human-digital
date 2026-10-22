# Spec: Bạn đồng hành trò chuyện trước tiên

## Objective

Luna và các nhân vật khác là người bạn AI để trẻ trò chuyện tự nhiên, kể chuyện, đùa vui và chia sẻ cảm xúc. Không mặc định biến cuộc hội thoại thành tiết học, bài kiểm tra hoặc lịch luyện tiếng Anh. Kiến thức và học tập chỉ được hỗ trợ khi trẻ hỏi, chọn chủ đề, hoặc phụ huynh chủ động dùng tính năng đó.

## Assumptions to validate

- Giữ các rào an toàn cho trẻ và quyền quản lý/xóa dữ liệu của phụ huynh.
- Giữ dữ liệu và tính năng kế hoạch học/báo cáo tiến độ như lựa chọn phụ trong Góc Phụ Huynh.
- Học là một dạng khám phá trong trò chuyện, không phải nhiệm vụ mặc định của mọi phiên.
- Màn hình chính ưu tiên bắt đầu trò chuyện; bỏ nút Khám phá riêng, bé vẫn có thể hỏi bằng giọng nói.

## Success criteria

- Lời chào và ít nhất ba lượt trò chuyện đời thường không tự lái sang bài học, từ vựng, câu đố, kế hoạch học hay câu hỏi gợi mở liên tục.
- Khi trẻ kể chuyện hoặc nói buồn, nhân vật phản hồi nội dung/cảm xúc trước; có thể chia sẻ, đùa nhẹ hoặc im lặng ngắn, không buộc phải kết thúc bằng câu hỏi.
- Khi trẻ tự hỏi kiến thức, muốn học tiếng Anh hoặc chọn chủ đề khám phá, nhân vật vẫn giúp ngắn gọn và chính xác, rồi trở lại nhịp trò chuyện tự nhiên.
- Các tính năng an toàn, trí nhớ cá nhân và phụ huynh không bị mất.
- Header hiển thị trạng thái camera (như “Đang tìm bé...”) cùng hàng với tên nhân vật, không chiếm hàng riêng; Góc Phụ Huynh nằm trong menu Cài đặt.
- Thanh điều khiển không còn nút Khám phá.
- Khi dừng ngay lúc khởi tạo audio, micro không được bật lại sau thao tác dừng.
- Ngắt lời cục bộ và xác nhận từ server chỉ xóa audio của lượt cũ một lần.
- Reconnect tự động dùng handle khôi phục và đúng Gemini API key của phiên cũ; mở phiên mới không dùng lại handle cũ.
- Nếu handle không còn hợp lệ, ứng dụng bỏ handle và có thể kết nối lại như phiên mới.

## Tech stack and commands

- Backend: Python, Gemini Live; Android: Kotlin/Jetpack Compose.
- Backend tests: `python -m unittest discover -s backend/tests` từ gốc repository.
- Android build/test: `cd android; .\gradlew.bat :app:testDebugUnitTest :app:assembleDebug`.
- Device verification: cài APK debug bằng `adb install -r android/app/build/outputs/apk/debug/app-debug.apk`, thử trên thiết bị được kết nối.

## Project structure and likely scope

- `backend/main.py`: system prompt, knowledge mode, greeting và quy tắc kết thúc phiên.
- `backend/personas.py`: bản sắc nhân vật.
- `backend/memory_manager.py`: ngữ cảnh trí nhớ/kế hoạch học tùy chọn.
- `android/app/src/main/java/com/example/digitalhuman/ui/MainActivity.kt`: lời dẫn và nhãn ở màn trò chuyện.
- `backend/tests/`: kiểm tra prompt và các tình huống hội thoại.

## Code style

Giữ hàm nhỏ, tên rõ nghĩa, chú thích tiếng Việt cho hành vi sản phẩm; không thêm tầng cấu hình mới nếu chỉ cần sửa quy tắc hiện hữu. Ví dụ:

```python
def build_companion_prompt(persona: dict) -> str:
    """Bản sắc bạn đồng hành, không gợi học khi bé chỉ muốn tâm sự."""
```

## Testing strategy

- Test các quy tắc prompt tĩnh: ưu tiên trò chuyện, học theo yêu cầu, an toàn không đổi.
- Test hồi quy các API/kế hoạch học nếu còn giữ.
- Kiểm tra thủ công trên điện thoại với ít nhất ba lời mở đầu đời thường, một câu hỏi kiến thức và một tình huống chia sẻ cảm xúc. Đánh giá nội dung bằng câu trả lời thực tế, không chỉ bằng test chuỗi.

## Boundaries

- Always: giữ an toàn trẻ em, tôn trọng lựa chọn của bé, không bịa ký ức hay kiến thức.
- Ask first: xóa kế hoạch học/báo cáo, đổi dữ liệu lưu trữ, hoặc bỏ tính năng phụ huynh.
- Never: chuyển dữ liệu trẻ ra ngoài phạm vi hiện có, bỏ rào an toàn để câu chuyện có vẻ tự nhiên hơn.

## Decision

Người dùng đã xác nhận: giữ kế hoạch học và báo cáo như tính năng phụ; cuộc trò chuyện và sự khám phá tự nhiên là bản chất sản phẩm.
