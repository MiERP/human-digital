# 🤖 Digital Human — bạn robot trò chuyện cùng trẻ (Android + Gemini Live)

Dự án bạn đồng hành AI cho trẻ em từ 5–12 tuổi. Trò chuyện, lắng nghe và cùng khám phá là trải nghiệm chính; học tiếng Anh, kiến thức và kế hoạch học là tính năng phụ khi bé hoặc phụ huynh chủ động chọn. Ứng dụng tích hợp **Google Gemini Multimodal Live API** qua kết nối WebSocket 2 chiều trực tiếp.

## 🎯 Trò chuyện trước, khám phá theo nhu cầu

Robot đi theo câu chuyện và cảm xúc của bé, không tự biến mỗi lượt nói thành bài học hay câu đố. Khi bé hỏi một câu kiến thức, robot có thể tra cứu và trả lời ngắn gọn; khi bé muốn luyện tiếng Anh, robot hỗ trợ tự nhiên trong cuộc trò chuyện.

Các khả năng phụ vẫn có: tra cứu kiến thức qua `search` với bộ lọc an toàn `ChildSafetyGuard`, hỗ trợ tiếng Anh, trí nhớ sở thích/kỷ niệm chung, theo dõi tiến độ học và kế hoạch học trong Góc Phụ Huynh. Câu hỏi chỉ cần làm rõ khi thực sự có nhiều cách hiểu khác nhau.

Màn hình trò chuyện chỉ giữ các điều khiển chính. Bé có thể hỏi bất kỳ chủ đề khám phá nào bằng giọng nói, không cần nút hay chế độ riêng.

---

## ⚙️ Cấu hình Backend (biến môi trường)

| Biến | Mặc định | Mô tả |
| --- | --- | --- |
| `GEMINI_VOICE` | `Aoede` | Giọng prebuilt Gemini Live (Puck/Charon/Kore/Fenrir/Aoede/Leda) |
| `ENABLE_TRANSCRIPTION` | `true` | Bật transcript input/output để đo lường & debug điểm cắt lượt |
| `VAD_START_SENSITIVITY` | `high` | Ngưỡng nhận diện bắt đầu nói (`high` = ít nhiễu hơn) |
| `VAD_END_SENSITIVITY` | `low` | Ngưỡng kết thúc nói (`low` = kết thúc lượt nhanh hơn) |
| `VAD_SILENCE_DURATION_MS` | `1000` | Khoảng im lặng để server kết thúc lượt |
| `VAD_PREFIX_PADDING_MS` | `200` | Padding trước điểm bắt đầu nói |
| `ADMIN_API_KEY` | _(bắt buộc)_ | Khóa quản trị để phụ huynh cấu hình hồ sơ bé. Không đặt → endpoint admin bị tắt (fail-closed). |
| `GOOGLE_CSE_ID` | _(rỗng)_ | ID của Google Programmable Search Engine (Encyclopedia Mode) |
| `GOOGLE_CSE_KEY` | _(rỗng)_ | API key cho Custom Search API (Encyclopedia Mode) |

### 🔍 Cách bật Google CSE cho Encyclopedia Mode (tùy chọn)

Mặc định backend tự động dùng **Wikipedia Simple English** làm nguồn dữ liệu (miễn phí, không cần key). Nếu muốn kết quả phong phú hơn, hãy bật Google Programmable Search Engine:

**Bước 1 — Tạo Search Engine** tại https://programmablesearchengine.google.com/ :
- Tick **"Search the entire web"**
- Ở mục **"Sites to search"**, thêm các domain giáo dục an toàn cho trẻ em:
  - `*wikipedia.org`, `simple.wikipedia.org`, `*britannica.com`
  - `*kids.nationalgeographic.com`, `*kiddle.co`
  - `*duckduckgo.com`, `duckduckgo.com/html`, `*bbc.co.uk`
- Lưu lại, copy **Search engine ID** (cx).

**Bước 2 — Tạo API key** tại https://console.cloud.google.com/ :
- APIs & Services → **Enable "Custom Search API"**
- Credentials → Create credentials → API key
- Copy **API key** vừa tạo.

**Bước 3 — Điền vào `backend/.env`**:
```bash
GOOGLE_CSE_ID=your_cx_id_here
GOOGLE_CSE_KEY=your_api_key_here
```

**Quota**: 100 query/ngày (free). Nếu vượt quota, backend tự động fallback về Wikipedia. Cache 1 giờ giúp giảm số lần gọi CSE cho câu hỏi lặp lại.

```
[Điện thoại Android (Kotlin/Compose)]
  │ • AudioRecord (16kHz PCM)
  │ • Silero VAD on-device (phát hiện nói/không nói)
  │ • 2D Doraemon Canvas (Lip-sync real-time theo âm lượng)
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
│   ├── search_engine.py     # ⭐ Knowledge search (CSE + Wikipedia) cho Encyclopedia Mode
│   ├── safety_guard.py      # Child safety + SSRF protection
│   ├── vietnamese_history.py# Curated history/science knowledge base
│   ├── memory_manager.py    # SQLite cho profile, episodic memory, learning progress
│   ├── static/
│   │   ├── index.html       # Trang test giọng nói trực tiếp
│   │   └── config.html      # ⭐ Trang cấu hình cá nhân hóa hồ sơ bé (phụ huynh)
│   ├── requirements.txt     # Thư viện Python (google-genai, fastapi, uvicorn...)
│   └── .env.example         # File mẫu chứa GEMINI_API_KEY + GOOGLE_CSE_ID/KEY
└── android/
    └── app/src/main/
        ├── AndroidManifest.xml
        └── java/com/example/digitalhuman/
            ├── audio/
            │   ├── AudioRecorder.kt   # Thu âm 16kHz PCM từ micro
            │   └── AudioPlayer.kt     # Phát âm 24kHz PCM + tính Lip-sync
            ├── network/
            │   └── GeminiLiveClient.kt # OkHttp WebSocket Client (+ clarification events)
            └── ui/
                ├── DoraemonAvatar.kt   # Doraemon vẽ bằng Jetpack Compose
                └── MainActivity.kt     # ⭐ UI chính + ClarificationChipBar (Encyclopedia chip)
```

## 🧒 Cá nhân hóa từng bé

Mỗi bé là một hồ sơ riêng (tên, tuổi, sở thích, gia đình, **tính cách**). Doraemon dùng hồ sơ này để điều chỉnh giọng điệu và cách động viên cho đúng từng bé.

- Phụ huynh mở trang **`http://<backend>:8000/config`**, nhập `ADMIN_API_KEY` + `child_id`, điền hồ sơ và bấm **Lưu**.
- Android app truyền `child_id` qua WebSocket URL (`ws://<backend>:8000/ws/live?child_id=...`) để gắn đúng hồ sơ.
- Trường `personality` (tính cách / phong cách giao tiếp) được đưa vào system prompt để Doraemon "hiểu" bé.

## 🎤 Lưu ý VAD on-device

Android hiện dùng **Silero VAD on-device** (`com.github.gkonovalov.android-vad:silero`) để gate luồng audio — chỉ gửi âm thanh lên server khi thực sự có giọng nói, giảm nhiễu, giảm độ trễ và cải thiện khả năng barge-in.

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

### Triển khai cập nhật lên VPS đang chạy

Chỉ dùng khi `/opt/human-digital` đã là Git checkout của `MiERP/human-digital`, có `.env` riêng và container `backend` đang chạy với volume `/app/data`:

```bash
cd /opt/human-digital
old_commit=$(git rev-parse HEAD)
git pull --ff-only origin main
PREVIOUS_COMMIT="$old_commit" bash deploy_vps.sh
```

Script chỉ rebuild service `backend` (`--no-deps`), sao lưu dữ liệu vào `/opt/backups/human-digital/`, rồi kiểm tra `/health` và `/api/companions`. Nó không sửa Nginx, firewall, `.env` hay service havsAI. Nếu điều kiện ban đầu không đúng, script dừng; **không chạy installer cũ hoặc `docker compose down` để khắc phục**. Khi cần quay lại mã nguồn trước đó, lấy SHA từ `previous-commit.txt` trong thư mục sao lưu và chỉ rebuild `backend` ở SHA đó. Khôi phục dữ liệu cần đánh giá riêng vì bản mới có thể đã ghi dữ liệu sau lúc sao lưu.

---

### 2. Cài đặt & Chạy trên Android

1. Mở thư mục `android/` bằng **Android Studio**.
2. Trong file [`MainActivity.kt`](android/app/src/main/java/com/example/digitalhuman/ui/MainActivity.kt), cập nhật địa chỉ IP của máy tính:
   * Nếu chạy trên **Android Emulator**: giữ nguyên `"ws://10.0.2.2:8000/ws/live"`.
   * Nếu chạy trên **điện thoại thật cắm cáp/Wifi**: đổi thành IP mạng nội bộ của máy tính, ví dụ `"ws://192.168.1.15:8000/ws/live"`.
3. Bấm **Run** trên Android Studio để cài app lên điện thoại.
4. Nhấn nút **"BẮT ĐẦU"**, cấp quyền Micro và bắt đầu trò chuyện bằng tiếng Anh hoặc tiếng Việt!
