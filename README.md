# 🤖 Digital Human AI English Tutor for Kids (Android + Gemini Live)

Dự án trợ lý ảo Digital Human 2D Robot dạy tiếng Anh tương tác thời gian thực cho trẻ em, tích hợp **Google Gemini Multimodal Live API** qua kết nối WebSocket 2 chiều trực tiếp (không cần LiveKit hay dịch vụ trung gian đắt tiền).

---

## 🏗️ Kiến trúc Hệ thống

```
[Điện thoại Android (Kotlin/Compose)]
  │ • AudioRecord (16kHz PCM)
  │ • 2D Robot Canvas (Lip-sync real-time theo âm lượng)
  │ • AudioTrack (24kHz PCM playback)
  │
  │ ▲ WebSocket 2 chiều (WSS)
  ▼ │
[Backend FastAPI Proxy (Python)]
  │ • Giữ an toàn GEMINI_API_KEY
  │ • Cấu hình System Prompt sư phạm cho trẻ em
  │
  │ ▲ WebSocket Stream
  ▼ │
[Google Gemini Multimodal Live API]
    • Xử lý Speech-to-Speech trực tiếp
    • Hỗ trợ song ngữ Anh - Việt, sửa lỗi ngữ pháp khéo léo (Recasting)
    • Giọng bản xứ (Puck/Aoede) vui tươi, ngắt lời tự nhiên (Barge-in)
```

---

## 📁 Cấu trúc Thư mục

```
human-digital/
├── backend/
│   ├── main.py              # FastAPI WebSocket Proxy kết nối Gemini Live
│   ├── requirements.txt     # Thư viện Python (google-genai, fastapi, uvicorn...)
│   └── .env.example         # File mẫu chứa GEMINI_API_KEY
└── android/
    └── app/src/main/
        ├── AndroidManifest.xml
        └── java/com/example/digitalhuman/
            ├── audio/
            │   ├── AudioRecorder.kt   # Thu âm 16kHz PCM từ micro
            │   └── AudioPlayer.kt     # Phát âm 24kHz PCM + tính Lip-sync
            ├── network/
            │   └── GeminiLiveClient.kt # OkHttp WebSocket Client
            └── ui/
                ├── RobotAvatar.kt      # 2D Robot vẽ bằng Jetpack Compose
                └── MainActivity.kt     # Giao diện chính học tiếng Anh
```

---

## 🚀 Hướng dẫn Cài đặt & Chạy Thử

### 1. Khởi động Backend Server

1. Cài đặt Python 3.10+:
   ```bash
   cd backend
   pip install -r requirements.txt
   ```
2. Tạo file `.env` từ `.env.example`:
   ```bash
   copy .env.example .env
   ```
3. Mở file `.env` và điền `GEMINI_API_KEY` (Lấy miễn phí tại [Google AI Studio](https://aistudio.google.com/)).
4. Chạy server:
   ```bash
   python main.py
   ```
   *Server sẽ lắng nghe tại: `http://localhost:8000` (WebSocket tại `ws://localhost:8000/ws/live`)*

---

### 2. Cài đặt & Chạy trên Android

1. Mở thư mục `android/` bằng **Android Studio**.
2. Trong file [`MainActivity.kt`](android/app/src/main/java/com/example/digitalhuman/ui/MainActivity.kt), cập nhật địa chỉ IP của máy tính:
   * Nếu chạy trên **Android Emulator**: giữ nguyên `"ws://10.0.2.2:8000/ws/live"`.
   * Nếu chạy trên **điện thoại thật cắm cáp/Wifi**: đổi thành IP mạng nội bộ của máy tính, ví dụ `"ws://192.168.1.15:8000/ws/live"`.
3. Bấm **Run** trên Android Studio để cài app lên điện thoại.
4. Nhấn nút **"Bắt đầu nói chuyện với Robo"**, cấp quyền Micro và bắt đầu trò chuyện bằng tiếng Anh hoặc tiếng Việt!
