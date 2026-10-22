# Plan: Sửa câu đáp ngắn và trạng thái Luna

1. **Ranh giới lời nói**: kiểm thử và chuyển đường đi âm thanh sang manual VAD của Gemini; điện thoại phát tín hiệu bắt đầu/kết thúc, giữ gửi `audio_stream_end` để tương thích backend cũ. Điều chỉnh cổng nhận câu ngắn ngay sau loa nhưng giữ cổng chống vọng lúc loa đang chạy. Chạy unit test Android/backend.
2. **Nhịp phản hồi**: kiểm thử trạng thái chờ câu trả lời; ngăn proactive nudge khi lời bé chưa được phản hồi. Nhãn camera không được gửi như một lượt text riêng vào Gemini. Chạy backend tests và phiên im lặng thật.
3. **Phản hồi giao diện**: chỉ chuyển sang “đang nghĩ” sau xác nhận nhận dạng từ Gemini; `tired` không đồng nghĩa ngủ. Chạy Android unit tests và build.
4. **Kiểm tra thật**: review diff; cài APK, triển khai backend với khả năng quay về bản trước, mở phiên trên điện thoại và đối chiếu log không chứa nội dung hội thoại. Người dùng xác nhận chất lượng nghe câu ngắn.
