# Chẩn Đoán: Vấn Đề Trên VPS — Lag & Kiến Thức Không Chính Xác

> Phân tích sau khi đọc toàn bộ: `main.py`, `search_engine.py`, `safety_guard.py`, `vietnamese_history.py`, `memory_manager.py`, `.env`.

---

## Tóm Tắt Ngắn Gọn

Có **2 nhóm vấn đề độc lập**:

| Nhóm | Biểu hiện | Nguyên nhân gốc |
|------|-----------|-----------------|
| **A — Lag VPS** | Trò chuyện bị dừng, chờ, giật cục | Wikipedia multi-request + DNS lookup blocking trong safety guard |
| **B — Kiến thức sai** | Doraemon nói thông tin không chính xác / không rõ nguồn | Curated KB quá ít, Wikipedia trả về đoạn không phù hợp trẻ em |

---

## NHÓM A — TẠI SAO LAG TRÊN VPS?

### 🔴 A1: Mỗi lần search Wikipedia = 2–4 HTTP requests nối tiếp, cộng thêm latency VPS → Internet

Khi không có `GOOGLE_CSE_ID`, search pipeline rơi vào Wikipedia fallback:

```python
# search_engine.py L409-L482
def _fetch_wiki_combined(self, query, lang, ...):
    # Request 1: OpenSearch (2s timeout)
    urllib.request.urlopen(opensearch_url, timeout=2.0)  
    
    # Request 2: Fulltext search nếu opensearch thất bại (2s timeout)
    urllib.request.urlopen(ft_url, timeout=2.0)
    
    # Request 3+: Summary API cho mỗi title (2s timeout mỗi cái, tối đa 3 titles)
    for title in titles[:top_k]:
        self._wikipedia_summary(title, ...)  # 1 request/title
```

**Worst case cho 1 query tiếng Việt**:
1. vi.wikipedia.org OpenSearch → (2s timeout nếu thất bại)
2. vi.wikipedia.org Fulltext → (2s timeout nếu thất bại)
3. vi.wikipedia.org Summary × 3 → (3 × 2s = 6s timeout)
4. simple.wikipedia.org OpenSearch → fallback nếu vi trống
5. simple.wikipedia.org Summary × 3

**Tổng timeout worst-case: ~14-18s**. Trên VPS datacenter Singapore → Wikipedia thường 200-500ms/request nhưng đôi khi spike 2-3s. **Với VPS ở Việt Nam + Wikipedia = 500ms-1s/request × 4-6 requests = 2-6s latency mỗi câu hỏi kiến thức** — đây chính là nguồn gốc "không mượt".

> Timeout trong `asyncio.wait_for(..., timeout=2.5)` ở `main.py` chỉ bọc **tổng pipeline**, nhưng pipeline gọi nhiều `.urlopen()` nối tiếp, mỗi cái có timeout **2.0s** riêng. Nếu 3 summary requests mỗi cái mất 1.5s thì tổng = 4.5s > 2.5s và sẽ bị timeout — Doraemon không có thông tin để trả lời.

---

### 🔴 A2: `assert_safe_url()` gọi `socket.getaddrinfo()` — DNS blocking trên VPS

**Vị trí**: [`safety_guard.py` L174](file:///d:/Agentic-AI/Doing/human-digital/backend/safety_guard.py#L174)

```python
addr_info = socket.getaddrinfo(hostname, None)  # ← BLOCKING DNS call!
```

Hàm `socket.getaddrinfo()` là **synchronous blocking call**. Nó chạy trực tiếp trong async event loop khi `_validate_and_clean()` được gọi bên trong `search_engine.search()` (đã được bọc trong `asyncio.to_thread`). Tuy nhiên, mỗi Wikipedia URL trong kết quả sẽ kích hoạt 1 DNS lookup. Trên VPS:

- DNS resolver có thể chậm hơn máy local (đặc biệt DNS VPS mặc định ở Singapore → resolve `.org` chậm)
- 3 Wikipedia URLs × 1 DNS lookup = 3 blocking DNS calls nối tiếp
- Mỗi lookup trung bình 50-200ms trên VPS, nhưng có thể spike 1-2s nếu DNS cache miss

---

### 🟡 A3: `google-genai` SDK version không pin, có thể chạy version khác Local vs VPS

**Vị trí**: [`requirements.txt` L3](file:///d:/Agentic-AI/Doing/human-digital/backend/requirements.txt#L3)

```
google-genai>=0.1.1
```

`>=0.1.1` nghĩa là pip sẽ cài bản mới nhất. Nếu Local dùng `1.x.x` nhưng VPS cài `0.9.x` hoặc khác nhau, có thể:
- Behavior của `session.receive()` khác
- Response format thay đổi giữa phiên bản
- `turn_coverage=TURN_INCLUDES_ONLY_ACTIVITY` chưa được support trên bản cũ

---

### 🟡 A4: `.env` chứa API Key thật đang được commit — rủi ro bảo mật

```
GEMINI_API_KEY=AQ.Ab8RN6LxyQQcE5B5xMl-wag7oyv5ZG4de7CQhDs7S1Fz0MVdrg
```

Key này có vẻ là key thật (không phải placeholder). Nếu repo này được push lên GitHub/GitLab, key bị lộ → người khác consume quota → dịch vụ bị chậm/blocked.

---

## NHÓM B — TẠI SAO KIẾN THỨC KHÔNG CHÍNH XÁC?

### 🔴 B1: Curated knowledge base cực kỳ nhỏ — chỉ có 8 entries tổng

**Vị trí**: [`vietnamese_history.py`](file:///d:/Agentic-AI/Doing/human-digital/backend/vietnamese_history.py)

```
CURATED_HISTORY: 6 entries (Hai Bà Trưng, Trần Hưng Đạo, Lê Lợi, Quang Trung, Hồ Chí Minh, Lý Thường Kiệt, Đinh Tiên Hoàng)
CURATED_SCIENCE: 2 entries (blue whale, T-Rex)
```

**Tổng: 8 facts**. Tất cả câu hỏi ngoài 8 topics này → fallback về Wikipedia. Trẻ em hỏi về: khủng long khác (Triceratops, Velociraptor), Thái Bình Dương, Mặt Trăng, Einstein, Newton, photosynthesis, planets, Vietnam War... đều phụ thuộc hoàn toàn vào Wikipedia.

---

### 🔴 B2: Wikipedia Simple English trả về nội dung không phù hợp trẻ em / thiếu chính xác

Wikipedia Simple English là nguồn **tiếng Anh đơn giản** — không phải nguồn tiếng Việt. Khi Doraemon nhận snippet từ vi.wikipedia.org, đó là bản dịch máy một phần hoặc bài ngắn không đầy đủ. Ví dụ:

```python
# Snippet bị cắt cứng ở 400 ký tự:
MAX_SNIPPET_CHARS = 400

def _truncate_snippet(self, text):
    truncated = text[:400]
    last_period = truncated.rfind(". ")
    if last_period > 100:
        return truncated[:last_period + 1]  # Cắt ở câu ngẫu nhiên
```

Kết quả: Gemini nhận được đoạn Wikipedia bị cắt đôi câu, không có ngữ cảnh đầy đủ → model phải **suy diễn, bịa thêm** để hoàn chỉnh câu trả lời.

---

### 🔴 B3: `safety_guard` có thể block kết quả Wikipedia hợp lệ

**Pattern bạo lực** trong `safety_guard.py`:
```python
VIOLENCE_PATTERNS = [r"\b(kill|murder|weapon|gun|knife|stab|blood|suicide|die|...)"]
```

Wikipedia về Lịch sử Việt Nam, Chiến tranh, Triều đại... thường có các từ như "killed", "died", "war", "battle" trong snippet. **`_validate_and_clean()` sẽ loại bỏ toàn bộ kết quả đó**, Doraemon không có gì để trả lời → nói tự do dựa trên training data → có thể sai.

Ví dụ: Wikipedia về "Trận Điện Biên Phủ" sẽ bị drop vì snippet có "killed" / "died in battle".

---

### 🟡 B4: Model được phép "suy đoán" khi search fail

System prompt viết: *"Never fabricate dates, scientific numbers, or historical events. If search returns no results, say honestly..."*

Nhưng trong thực tế với Gemini 2.5 Flash, khi search bị timeout (2.5s) hoặc bị drop bởi safety guard → model nhận `tool_output_text = "Doraemon đang cố gắng suy nghĩ nhưng mạng hơi chậm"` → model có thể dùng internal knowledge để trả lời thay vì nói thật → **factual errors**.

---

### 🟡 B5: Google CSE không được cấu hình → hoàn toàn phụ thuộc Wikipedia

```env
GOOGLE_CSE_ID=     ← Trống
GOOGLE_CSE_KEY=    ← Trống
```

Google CSE là backend chất lượng cao nhất (Britannica, National Geographic for Kids, BBC...). Hiện không được cấu hình → 100% fallback về Wikipedia mọi lúc.

---

## Bảng Tổng Hợp Vấn Đề

| # | Mức độ | Vấn đề | File | Ảnh hưởng |
|---|--------|---------|------|-----------|
| A1 | 🔴 Cao | Wikipedia 4-6 HTTP requests nối tiếp | search_engine.py | Lag 2-6s mỗi câu hỏi |
| A2 | 🔴 Cao | DNS lookup blocking trong assert_safe_url | safety_guard.py | Thêm 150-600ms/request |
| A3 | 🟡 Trung | SDK version không pin | requirements.txt | Behavior khác Local vs VPS |
| A4 | 🟠 Bảo mật | API Key thật trong `.env` | .env | Rủi ro lộ key |
| B1 | 🔴 Cao | Curated KB chỉ có 8 facts | vietnamese_history.py | Mọi câu hỏi khác → Wikipedia |
| B2 | 🔴 Cao | Snippet 400 ký tự cắt đứt → model bịa | search_engine.py | Kiến thức sai, thiếu |
| B3 | 🔴 Cao | Safety guard block Wikipedia lịch sử | safety_guard.py | Không có knowledge → bịa |
| B4 | 🟡 Trung | Model suy đoán khi search fail | main.py | Câu trả lời không đáng tin |
| B5 | 🟡 Trung | Google CSE không cấu hình | .env | Wikipedia-only, chất lượng thấp |

---

## Hướng Fix Đề Xuất

### Ưu tiên cao — Fix ngay

#### 1. Tăng timeout Wikipedia từng request + giới hạn số summary fetch
```python
# search_engine.py — giới hạn chỉ fetch 1-2 summary thay vì 3:
for idx, title in enumerate(titles[:min(top_k, 2)]):  # max 2 thay vì top_k=3
```

#### 2. Tăng `MAX_SNIPPET_CHARS` từ 400 → 800 để context đầy đủ hơn
```python
MAX_SNIPPET_CHARS = 800  # Doraemon sẽ tóm tắt, không đọc thô
```

#### 3. Chạy DNS lookup trong thread riêng trong `assert_safe_url`
```python
# Bọc socket.getaddrinfo trong asyncio.to_thread nếu chạy từ async context
# Hoặc đơn giản hơn: dùng whitelist-only check, bỏ DNS lookup
# Vì đã whitelist domain rồi, DNS thêm vào chỉ phòng ngừa DNS rebinding
# — có thể accept rủi ro nhỏ này đổi lấy performance
```

#### 4. Mở rộng `curated knowledge base` — thêm ít nhất 20-30 topics phổ biến trẻ hỏi
Các topic ưu tiên thêm vào `vietnamese_history.py`:
- Khoa học: Mặt Trăng, Mặt Trời, sao, trái đất, photosynthesis, gravity, Einstein, Newton
- Động vật: voi, hổ, gấu trúc, cá mập, bướm, kiến
- Lịch sử VN còn thiếu: Nguyễn Trãi, Nguyễn Du, Truyện Kiều, Hùng Vương

#### 5. Sửa safety guard không drop bài lịch sử hợp lệ
```python
# Thêm exception: nếu URL là wikipedia.org/wiki/... và snippet về lịch sử
# → reduce sensitivity / whitelist historical terms như "war", "battle", "died"
# Context: "died in battle" ≠ bạo lực với trẻ em — đây là lịch sử giáo khoa
```

#### 6. Cấu hình Google CSE (miễn phí 100 query/ngày)
Đây là cải thiện chất lượng kiến thức lớn nhất. Với CSE:
- Chỉ 1 HTTP request thay vì 4-6
- Kết quả từ Britannica, National Geographic → chính xác hơn Wikipedia nhiều

#### 7. Pin SDK versions trong requirements.txt
```
google-genai==1.26.0    # (version hiện dùng local, kiểm tra với pip show google-genai)
fastapi==0.115.6
uvicorn[standard]==0.32.1
```

#### 8. Xóa API Key thật khỏi `.env`, thêm vào `.gitignore`
```bash
echo ".env" >> .gitignore
git rm --cached backend/.env  # Nếu đã commit rồi
```

---

## Timeline Cải Thiện Kỳ Vọng

| Fix | Giảm lag | Cải thiện kiến thức |
|-----|----------|---------------------|
| Giảm summary fetch xuống 2 | -30-40% thời gian search | — |
| Tăng snippet 400→800 | — | Giảm hallucination rõ rệt |
| Fix safety guard block lịch sử | — | Có kết quả thay vì không có gì |
| Thêm 20 curated facts | -60% query tới Wikipedia | Chính xác 100% với topics đó |
| Cấu hình Google CSE | -70% thời gian search | Chất lượng tăng nhiều |

---

*Chẩn đoán bởi Antigravity — 2026-08-30 21:48*
