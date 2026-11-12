# Plan: Trò chuyện là chính

1. **Prompt và lời chào** — sửa bản sắc, prompt nền, hướng dẫn tìm kiếm và ngữ cảnh kế hoạch học để không chủ động dạy khi bé chỉ muốn trò chuyện. Giữ công cụ học/tra cứu cho yêu cầu rõ ràng. Kiểm tra bằng test prompt và backend tests.
2. **Màn hình chính** — đưa trạng thái camera lên cùng hàng tên nhân vật; chuyển Góc Phụ Huynh vào menu Cài đặt; bỏ nút Khám phá khỏi thanh điều khiển và lời dẫn mang giọng “học bài”. Build Android và kiểm tra trên Samsung SM-A235F.
3. **Kiểm tra cuối** — chạy backend tests, Android unit tests/build, kiểm tra diff và ảnh chụp thiết bị. Backend chỉ có hiệu lực sau khi triển khai máy chủ; không coi việc cài APK là đã triển khai prompt.

Giữ nguyên hệ thống an toàn, dữ liệu học tập, API phụ huynh và các thay đổi avatar đang có trong worktree.
