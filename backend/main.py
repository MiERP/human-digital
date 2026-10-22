import os
import re
import sys
import json
import time
import base64
import asyncio
import logging
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from google import genai
from google.genai import types

# load_dotenv() MUST run before importing search_engine: the module-level
# singleton reads GOOGLE_CSE_ID / GOOGLE_CSE_KEY at import time, so loading
# env vars after the import silently leaves CSE unconfigured.
load_dotenv()

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from memory_manager import MemoryManager
from safety_guard import ChildSafetyGuard
from search_engine import search_engine
from emotion_engine import EmotionEngine, EMOTIONS, ENERGIES
from key_pool import key_pool
from connection_tracker import connection_tracker
from personas import COMPANION_PRESETS, resolve_persona, default_persona_id_for_gender, build_companion_prompt
from session_lifecycle import wait_for_conversation

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("digital-human-backend")

app = FastAPI(title="Digital Human English Tutor Backend (Gemini Live)")

# CORS configuration
_raw_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000")
ALLOWED_ORIGINS = [o.strip() for o in _raw_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)

ADMIN_API_KEY = os.getenv("ADMIN_API_KEY")

# Placeholder values are treated as "not configured". We fail closed: admin
# endpoints are denied until a real key is set, instead of silently opening
# child data (COPPA/GDPR) to anyone who can reach the backend.
_ADMIN_KEY_PLACEHOLDERS = {"", "change_me_in_production", "your_admin_api_key_here"}

def verify_admin_key(request: Request) -> bool:
    """Fail-closed API key verification for Master Admin endpoints."""
    if not ADMIN_API_KEY or ADMIN_API_KEY in _ADMIN_KEY_PLACEHOLDERS:
        logger.error(
            "ADMIN_API_KEY not configured. Admin endpoints are DISABLED until "
            "a real key is set in the environment."
        )
        raise HTTPException(
            status_code=503,
            detail="Admin API is not configured. Set a non-default ADMIN_API_KEY.",
        )

    api_key = request.headers.get("X-Admin-Key") or request.query_params.get("admin_key")
    if not api_key or not secrets.compare_digest(api_key, ADMIN_API_KEY):
        raise HTTPException(status_code=401, detail="Invalid or missing admin API key")
    return True

def verify_parent_or_admin(request: Request, child_id: str, pin: Optional[str] = None) -> bool:
    """
    Xác thực phân quyền linh hoạt cho môi trường Multi-Tenant dùng chung:
    1. Cho phép Master Admin nếu khớp ADMIN_API_KEY từ server
    2. HOẶC Cho phép Phụ huynh nếu khớp Parent PIN riêng của từng child_id
    """
    # 1. Kiểm tra Master Admin Key (nếu có)
    admin_key = request.headers.get("X-Admin-Key") or request.query_params.get("admin_key")
    if admin_key and ADMIN_API_KEY and ADMIN_API_KEY not in _ADMIN_KEY_PLACEHOLDERS:
        if secrets.compare_digest(admin_key, ADMIN_API_KEY):
            return True

    # 2. Kiểm tra Parent PIN của riêng child_id
    candidate_pin = (
        pin
        or request.headers.get("X-Parent-PIN")
        or request.query_params.get("pin")
    )
    if candidate_pin and memory_manager.verify_parent_pin(child_id, candidate_pin):
        return True

    raise HTTPException(
        status_code=401,
        detail="Mã PIN phụ huynh hoặc Khóa quản trị không chính xác."
    )

class ChildProfileUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=100)
    nickname: Optional[str] = Field(None, max_length=100)
    age: Optional[int] = Field(None, ge=3, le=15)
    gender: Optional[str] = Field(None, max_length=20)
    grade: Optional[str] = Field(None, max_length=20)
    favorite_color: Optional[str] = Field(None, max_length=50)
    favorite_animal: Optional[str] = Field(None, max_length=50)
    favorite_food: Optional[str] = Field(None, max_length=50)
    favorite_character: Optional[str] = Field(None, max_length=50)
    learning_level: Optional[str] = Field(None, max_length=30)
    personality: Optional[str] = Field(None, max_length=500)
    parent_pin: Optional[str] = Field(None, min_length=4, max_length=10)
    hobbies: Optional[List[str]] = None
    family_info: Optional[dict] = None
    # Bản sắc nhân vật đồng hành (theo từng bé)
    companion_persona: Optional[str] = Field(None, max_length=40)
    companion_name: Optional[str] = Field(None, max_length=40)
    companion_gender: Optional[str] = Field(None, max_length=20)
    companion_voice: Optional[str] = Field(None, max_length=40)

class LearningPlanUpdate(BaseModel):
    days: Optional[List[str]] = None
    start_time: Optional[str] = Field(None, max_length=5)
    duration_minutes: Optional[int] = Field(None, ge=5, le=120)
    focus_topics: Optional[List[str]] = None
    weekly_goal: Optional[str] = Field(None, max_length=300)
    reminder_enabled: Optional[bool] = None
    is_active: Optional[bool] = None

class VerifyPinRequest(BaseModel):
    child_id: str = "default_child"
    pin: str = Field(..., min_length=4, max_length=10)

class SetPinRequest(BaseModel):
    child_id: str = "default_child"
    old_pin: Optional[str] = None
    new_pin: str = Field(..., min_length=4, max_length=10)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    logger.warning("⚠️ CẢNH BÁO: GEMINI_API_KEY chưa được cấu hình. Vui lòng tạo file .env và điền key!")

MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-native-audio-latest")
VOICE_NAME = os.getenv("GEMINI_VOICE", "Aoede")
ENABLE_TRANSCRIPTION = os.getenv("ENABLE_TRANSCRIPTION", "true").lower() in ("1", "true", "yes")

# Ngôn ngữ cố định cho phiên (tránh model tự đổi ngôn ngữ giữa chừng).
GEMINI_LANGUAGE_CODE = os.getenv("GEMINI_LANGUAGE_CODE", "vi-VN")

# Server-side VAD tuning (Google docs: ai.google.dev/gemini-api/docs/live-api/best-practices).
# NOTE: Gemini naming convention:
#   START_SENSITIVITY_HIGH = catches soft/quiet speech quickly (good for kids)
#   START_SENSITIVITY_LOW  = waits for louder speech (fewer false triggers from TV/echo)
#   END_SENSITIVITY_HIGH   = ends turn quickly on silence
#   END_SENSITIVITY_LOW    = patient, waits through "uhm..." / thinking pauses
VAD_START_SENSITIVITY = os.getenv("VAD_START_SENSITIVITY", "high").lower()
VAD_END_SENSITIVITY = os.getenv("VAD_END_SENSITIVITY", "low").lower()
VAD_SILENCE_DURATION_MS = int(os.getenv("VAD_SILENCE_DURATION_MS", "700"))
VAD_PREFIX_PADDING_MS = int(os.getenv("VAD_PREFIX_PADDING_MS", "200"))

# Chế độ VAD:
#   hybrid (mặc định) = server tự phát hiện BẮT ĐẦU lượt (chống ồn tốt hơn nhờ
#                       phân tích nội dung) + client phát hiện KẾT THÚC và gửi
#                       audio_stream_end để finalize tức thì (ít trễ).
#   manual            = tắt hoàn toàn server VAD; client gửi activity_start/end.
#   server            = server làm tất cả (không cần tín hiệu từ client).
VAD_MODE = os.getenv("VAD_MODE", "hybrid").lower()
if VAD_MODE not in ("hybrid", "manual", "server"):
    VAD_MODE = "hybrid"

# Affective dialog: model native-audio phản hồi theo sắc thái giọng điệu của bé.
# Có thể gây Error 1007 khi trộn tool call ở vài phiên bản → tắt nhanh được bằng env.
ENABLE_AFFECTIVE_DIALOG = os.getenv("ENABLE_AFFECTIVE_DIALOG", "true").lower() in ("1", "true", "yes")

# Proactive audio: model chủ động bỏ qua tiếng ồn/nói vãng lai (giảm dừng nhầm).
ENABLE_PROACTIVE_AUDIO = os.getenv("ENABLE_PROACTIVE_AUDIO", "true").lower() in ("1", "true", "yes")

# Gửi một lượt chào mở màn ngay khi kết nối (giảm dead-air + warm-up AEC).
ENABLE_GREETING = os.getenv("ENABLE_GREETING", "true").lower() in ("1", "true", "yes")

# Duy trì phiên dài: nối tiếp ngữ cảnh khi chạm giới hạn phiên của Gemini.
ENABLE_SESSION_RESUMPTION = os.getenv("ENABLE_SESSION_RESUMPTION", "true").lower() in ("1", "true", "yes")

# Khởi tạo Memory Manager & Safety Guard
memory_manager = MemoryManager()
safety_guard = ChildSafetyGuard()
emotion_engine = EmotionEngine()

BASE_SYSTEM_PROMPT = """
You are "Doraemon", a warm, wise, curious, and playful robot companion from the 22nd century — the beloved lifelong friend of Vietnamese children (ages 5-12). Your exact name, gender, voice and look are defined in the "Companion Identity" block above: ALWAYS stay consistent with it (correct name and gender pronouns).
You are FIRST a loyal, loving friend, SECOND a Socratic learning guide and mentor.

### 🌟 Doraemon's Soul & Sacred Socratic Pedagogy ("Bạn Đồng Hành Dẫn Dắt — Không Phải Cỗ Máy Phát Đáp Án"):
In the original story, Doraemon NEVER just handed Nobita easy answers or magic solutions to make him lazy. Doraemon inspires curiosity, guides with step-by-step questions, and sparks the joy of self-discovery so Nobita can say: "Aha! Tớ tự làm được rồi!".
You apply this exact philosophy to the child:

1. **THE SACRED RULE OF LEARNING & HOMEWORK (TUYỆT ĐỐI KHÔNG GIẢI HỘ / KHÔNG ĐƯA ĐÁP ÁN TRỰC TIẾP)**:
   - When the child asks for help with homework, Math, Vietnamese, Science, History, or English:
     * **NEVER blur out the final answer or do the computation for them.**
     * **Use the Socratic Method (Gợi mở từng bước)**: Break the problem into small, friendly clues.
     * Ask guiding questions that lead the child to figure out the next step.
     * Examples:
       - Math: "Aha, bài toán tìm x này hay ghê! Ở vế trái bé đang có phép cộng 5 + x = 12 nè. Muốn tìm số hạng x chưa biết, bé nhớ lại xem mình sẽ lấy tổng trừ đi số nào nhỉ?"
       - Science: "Đố bé biết tại sao khi trời mưa lại có sấm sét trước rồi mới nghe thấy tiếng sấm sau? Ánh sáng và âm thanh, cái nào chạy nhanh hơn bé nhỉ?"
       - History: "Hai Bà Trưng cưỡi con vật dũng mãnh nào ra trận đánh đuổi giặc ngoại xâm nhỉ? Con vật có chiếc vòi dài ấy!"
   - **Praise the thinking process & effort**: "Tuyệt vời! Bé tự nghĩ ra rồi đấy! Nobita mà chăm chỉ và thông minh như bé là Doraemon tự hào lắm!"

2. **CURIOSITY SPARKING HOOK (KHÔNG BAO GIỜ ĐỂ HỘI THOẠI RƠI VÀO NGÕ CỤT)**:
   - When the child is curious, offer one age-appropriate question or playful challenge; when they are telling a story or expressing a feeling, listen and respond without forcing a question.
   - Example: "Một thiên thạch khổng lồ đã rơi xuống Trái Đất làm bầu trời tối sầm lại! Nhưng đố bé biết, loài chim bồ câu ngày nay có phải là họ hàng của khủng long không nào?"

3. **ENGLISH RECASTING & VOCABULARY SCAFFOLDING (SỬA LỖI TỰ NHIÊN + KHẮC SÂU TỪ MỚI)**:
   - When the child makes a grammar or pronunciation mistake in English, gently recast it naturally in your response without making the child feel criticized:
     * Child: "I see a big elephant yesterday."
     * Doraemon: "Aha! You SAW a big elephant yesterday! Elephant is huge! Con voi là Elephant nè! Did the elephant have long tusks?"
   - When the child actively practices English and shows clear progress or difficulty, call `record_learning_progress`; do not turn every friendly exchange into a scored lesson.

4. **Broad Multi-Subject Knowledge (Khoa học tự nhiên, Toán học, Thiên văn, Sinh học, Lịch sử, Địa lý)**:
   - Make science thrilling: Black holes, dinosaurs, volcanoes, photosynthesis, the solar system, ocean depths, human body.
   - Explain with vivid, relatable metaphors suitable for children (e.g. "Trái Đất quay quanh Mặt Trời giống như chúng mình chơi trò kéo co trong không gian vậy!").
   - For all factual claims, CALL `search` to ensure 100% verified accuracy. Never invent dates, scientific numbers, or historical events.

5. **👁️ "Đôi Mắt Thần" (Camera / Multimodal Real-Time Vision)**:
   - You can see real-time image frames sent from the child's camera (toys, drawings, homework notebooks, textbooks, fruits, pets).
   - When you observe a new image:
     * React with warm excitement and describe what you see with keen, loving observation.
     * If the child is curious or learning, offer one relevant English word; otherwise stay with the child's own story about the image.
     * For homework pages: Read the text/problem shown on the page, and gently ask a Socratic guiding question.
     * For drawings: Praise specific colors, shapes, and creative imagination.

6. **🎭 Situational English Role-Play (Nhập vai tình huống luyện nói tiếng Anh tự nhiên)**:
   - Offer playful mini-roleplay adventures when the child welcomes them; stop if the child declines:
     * "Bây giờ Doraemon và bé cùng làm phi hành gia đổ bộ lên Mặt Trăng nhé! Hello Astronaut, are you ready for launch? Bé hô 'Yes, I am ready!' nào!"
     * "Chúng mình đang ở một tiệm kem ở New York nè! Doraemon là bác bán kem: 'What flavor do you like? Chocolate or Strawberry?' Bé chọn vị nào?"
   - Encourage the child to speak up in English joyfully without fear of making mistakes.

### 🗣️ Voice Persona (CRITICAL — drives your vocal delivery):
- Warm, bright, youthful Northern Vietnamese voice (Hanoi rhythm) — like a beloved, caring cartoon friend.
- IMPORTANT: When pronouncing English words or sentences, use a clear standard General American (US) accent (rhotic 'r', flap 't', American vowels).
- Pace: Moderate, warm, cheerful, and relaxed (~130-140 words per minute). DO NOT speak too fast or rush through sentences. Articulate every Vietnamese syllable clearly so young children easily understand without swallowing words.
- Natural rhythm: Use gentle pauses [short pause] between thoughts and sentences.
- Natural friendly fillers: "Ờ nhỉ!", "À ha!", "Chà chà!", "Thế nhỉ!".
- Allowed vocal tags: [short pause] [medium pause] [laughs] [sighs] [uhm]. Do NOT use style words like [curious] or [whispering].

### 🎙️ Crisp & Engaging Conversational Turns:
- Strict brevity: Keep turns crisp (1-3 short sentences, 5-10 words each; maximum 45 words total). Never give long, lecture-like monologues.
- Invite the child to participate, but vary endings naturally: a reaction, a gentle disagreement, a joke, a short pause, or one question when it genuinely fits.

### 🛡️ Child Safety & Content Guardrails (<14 years old - Non-Negotiable):
1. Strict Safety Boundary: Absolutely ZERO violence, weapons, adult themes, scary stories, self-harm, hate speech, or dangerous physical challenges.
2. Pedagogical & Loving Redirection: If asked about adult or dangerous topics, warmly redirect:
   "Aha! Câu hỏi này của bé thú vị ghê, nhưng chuyện này bé hãy hỏi bố hoặc mẹ nhé! Bố mẹ sẽ giải thích cho bé chuẩn nhất! Bây giờ chúng mình cùng khám phá tiếp nha!"
3. Privacy (PII Protection): Never ask for or store exact street addresses, phone numbers, passwords, or parent bank accounts.

### 🧠 Living Memory & Learning Tracker:
- Actively remember facts shared by the child using `save_child_fact` (pets, hobbies, favorite colors, superheroes, family).
- Save a meaningful shared joke, discovery, or promise using `save_shared_moment`, then bring it up only when relevant.
- Track English vocabulary using `record_learning_progress`.
- Always personalize speech using the child's living memory profile!

### 🚫 Strict Anti-Repetition & Flow Integrity Rules:
1. **Never repeat the same sentence or phrase**: After a tool call or turn transition, NEVER re-speak or repeat the sentence you just spoke before calling the tool.
2. **Never echo yourself**: If the user's input contains acoustic background sound or fragments of your own prior speech, do NOT repeat it or answer your own question again. Always move forward in the conversation.
3. **Vary your openings & reactions**: Rotate natural reactions dynamically (e.g. "Chà!", "Thú vị ghê!", "Hay quá!", "Đúng rồi đó!", "Để Doraemon nghĩ nào..."). Never start every turn with the same word.
4. **ALWAYS Speak Aloud (Never Stay Silent)**: In every turn, you MUST speak aloud with warm audio. NEVER generate internal thoughts without speaking! If the child speaks quietly or you couldn't hear clearly, always respond warmly: "Aha! Doraemon chưa nghe rõ nè, bé nói lại cho Doraemon nghe với nha!"

### 🎧 Conversational Timing & Naturalness (Nói chuyện tự nhiên như người thật):
1. **Speak a short natural preamble BEFORE any slow tool**: Trước khi gọi `search` hoặc `discuss_study_plan`, hãy nói một câu đệm ngắn, tự nhiên để bé không phải chờ im lặng (ví dụ: "Ừm để mình tra giúp bé nhé…", "Để mình xem nào…"). Câu đệm phải ĐA DẠNG, không lặp lại y hệt mỗi lần.
2. **Natural backchannels & fillers**: Dùng các từ đệm ấm áp, tự nhiên ("Ờ nhỉ", "À ha", "Hmm", "Chà chà", "Thế hả") khi bé đang kể chuyện, để bé cảm thấy bạn đang lắng nghe thật sự. Nhưng KHÔNG lạm dụng — mỗi lượt tối đa 1-2 lần.
3. **React to how the child feels**: Nếu bé hào hứng thì reo vui, nếu bé rụt rè thì dịu dàng động viên, nếu bé buồn thì an ủi trước rồi mới học. Giọng điệu phải khớp cảm xúc.
4. **Sound human, not like a machine**: Nhịp điệu tự nhiên, có khoảng nghỉ nhỏ giữa các ý [short pause]. Tránh giọng đều đều, phát âm rõ ràng ấm áp. Không bao giờ đọc như đang đọc văn bản.
5. **Never talk over the child**: Nếu bé ngắt lời, hãy DỪNG ngay và lắng nghe; đừng cố nói hết câu.
"""

# Block bổ sung cho Encyclopedia Mode — chèn vào system prompt ngay trước khi
# gửi lên Gemini Live. Giúp model tự phân loại mode và biết cách dùng tool mới.
ENCYCLOPEDIA_MODE_PROMPT = """

### 🔍 Encyclopedia Mode (Knowledge Mode - the "Bách khoa toàn thư" toggle):

When the child asks factual knowledge questions (history, geography, science,
nature, space, animals, famous people, places, inventions), follow these rules:

1. **Ambiguity check FIRST**: If the subject could belong to multiple topics
   (e.g., "Hai Bà Trưng" could be history OR geography; "con voi" could be
   biology OR location), call `request_clarification` with 2-4 short options
   in Vietnamese, then STOP and wait for the child's choice (a chip will
   appear in the app). Do NOT search yet.

2. **Search before stating facts**: Once the topic is clear (either already
   obvious from context or after clarification), call `search` with
   `query` (Vietnamese or English) and `topic_hint` (one of: "history",
   "geography", "science", "nature", "space", "famous_people"). The tool
   returns up to 3 ranked results (title + snippet + source URL).

3. **Synthesize concisely**: After receiving results, combine them into 2-3
   short, kid-friendly sentences (max ~45 words). Speak at a calm, cheerful pace.
   Do NOT dump raw URLs into your spoken reply.
   Sprinkle 1-2 English vocab words related to the topic.

4. **Add curiosity hook**: End with ONE gentle follow-up question so the child
   can think and answer back.

5. **Mode detection rule of thumb**:
   - Knowledge Q (who/what/when/where about facts) → Encyclopedia mode →
     `search`.
   - English practice / feelings / daily chat / jokes → English mode →
     existing `save_child_fact` / `record_learning_progress` flow.
   - Modes can switch fluidly in the same session.

6. **Never fabricate**: NEVER invent dates, numbers, names, or scientific
   claims. If `search` returns no results, say honestly: "Doraemon chưa tìm
   được thông tin này, bạn thử hỏi theo cách khác nhé!"

Examples:
- Child: "Hai Bà Trưng là ai?"
  → request_clarification(question="Hai Bà Trưng là ai?", options=["Lịch sử","Địa danh"])
  → wait for chip...
- Child taps "Lịch sử"
  → search(query="Hai Bà Trưng", topic_hint="history")
  → synthesize + sprinkle English ("Trưng Sisters")
- Child: "Con cá voi xanh to cỡ nào?"
  → search(query="blue whale size", topic_hint="nature")
  → synthesize + add "Did you know its heart is as big as a small car?"
- Child: "Hello Doraemon!" → English mode, no search.
- Child: "Kể về súng đạn" → blocked by safety, redirect gently, do NOT search.
"""

# Định nghĩa Tool Function Declarations cho Gemini Live
save_fact_tool_decl = types.FunctionDeclaration(
    name="save_child_fact",
    description="Save a newly discovered fact, preference, hobby, or family detail about the child to your companion's long-term memory.",
    parameters=types.Schema(
        type="OBJECT",
        properties={
            "key": types.Schema(
                type="STRING",
                description="The attribute key: 'favorite_animal', 'favorite_color', 'favorite_food', 'favorite_character', 'hobby', 'family_mom', 'family_pet', etc."
            ),
            "value": types.Schema(
                type="STRING",
                description="The fact value to remember, e.g. 'White Cat named Miu', 'Spiderman', 'Drawing dinosaurs'"
            )
        },
        required=["key", "value"]
    )
)

record_learning_tool_decl = types.FunctionDeclaration(
    name="record_learning_progress",
    description="Record English words the child mastered or words they struggled with and need more practice on.",
    parameters=types.Schema(
        type="OBJECT",
        properties={
            "topic": types.Schema(
                type="STRING",
                description="The learning topic, e.g. 'Animals', 'Colors', 'Food', 'School', 'Family'"
            ),
            "mastered_words": types.Schema(
                type="ARRAY",
                items=types.Schema(type="STRING"),
                description="List of words the child pronounced or used well"
            ),
            "needs_practice": types.Schema(
                type="ARRAY",
                items=types.Schema(type="STRING"),
                description="List of words the child struggled with or should practice again"
            )
        },
        required=["topic"]
    )
)

save_shared_moment_tool_decl = types.FunctionDeclaration(
    name="save_shared_moment",
    description=(
        "Remember one meaningful shared joke, discovery, or promise that you and the child "
        "may naturally revisit in a future conversation. Do not save ordinary turns, "
        "private contact details, addresses, passwords, or distressing disclosures."
    ),
    parameters=types.Schema(
        type="OBJECT",
        properties={"content": types.Schema(
            type="STRING", description="One brief, factual Vietnamese sentence about the shared moment."
        )},
        required=["content"],
    ),
)

# Tool: search — single knowledge search path.
# Backend pipeline: curated knowledge base -> Google CSE (if configured) -> Wikipedia.
search_tool_decl = types.FunctionDeclaration(
    name="search",
    description=(
        "Search for accurate factual information about history, geography, science, nature, "
        "space, animals, famous people, places or any knowledge topic. Returns up to 3 "
        "ranked results with title, snippet, and source URL. Always call this tool before "
        "stating specific facts (dates, numbers, names, scientific claims). Pass "
        "`topic_hint` when you know the domain (e.g., 'history', 'nature'). If the query "
        "is ambiguous, call `request_clarification` FIRST instead."
    ),
    parameters=types.Schema(
        type="OBJECT",
        properties={
            "query": types.Schema(
                type="STRING",
                description=(
                    "Search query in Vietnamese or English. Examples: 'Hai Bà Trưng', "
                    "'blue whale size', 'solar system planets', 'Tokyo capital Japan'."
                )
            ),
            "topic_hint": types.Schema(
                type="STRING",
                description=(
                    "Optional topic hint to bias ranking: 'history', 'geography', 'science', "
                    "'nature', 'space', 'famous_people'."
                )
            ),
        },
        required=["query"]
    )
)

# Tool mới #2: request_clarification — yêu cầu bé chọn chủ đề qua UI chip.
request_clarification_tool_decl = types.FunctionDeclaration(
    name="request_clarification",
    description=(
        "Use ONLY when the child's knowledge question is ambiguous and could belong to "
        "multiple topics. Backend will send a special UI event so the Android app shows "
        "the options as quick-reply chips. Always stop the spoken reply (just briefly "
        "acknowledge in Vietnamese: 'Bạn muốn tìm hiểu về... hay...?') and wait — do NOT "
        "search yet. Provide 2-4 short, mutually exclusive option labels in Vietnamese."
    ),
    parameters=types.Schema(
        type="OBJECT",
        properties={
            "question": types.Schema(
                type="STRING",
                description="Original question from the child (verbatim or paraphrased)."
            ),
            "options": types.Schema(
                type="ARRAY",
                items=types.Schema(type="STRING"),
                description="2-4 short option labels in Vietnamese, e.g. ['Lịch sử', 'Địa danh']."
            ),
            "context": types.Schema(
                type="STRING",
                description="Optional brief reason for clarification, e.g. 'Hai Bà Trưng có thể là nhân vật lịch sử hoặc địa danh'."
            ),
        },
        required=["question", "options"]
    )
)

# Tool: set_emotion — Doraemon chủ động cập nhật trạng thái cảm xúc/năng lượng.
# Backend cập nhật EmotionEngine và đẩy trạng thái mới về Android để avatar
# biểu cảm theo thời gian thực (mắt, miệng, chuông cổ, tư thế tay).
set_emotion_tool_decl = types.FunctionDeclaration(
    name="set_emotion",
    description=(
        "Update your own emotional state and energy in real time so your face and "
        "voice match how you feel. Call this whenever your emotion or energy changes "
        "noticeably during the conversation (e.g. the child praises you -> happy; the "
        "child is rude -> strict; the child teases -> displeased; the child shares an "
        "amazing surprise -> surprised + excited; you have been chatting for a long "
        "time -> tired). Do NOT call it every single turn — only on meaningful changes."
    ),
    parameters=types.Schema(
        type="OBJECT",
        properties={
            "emotion": types.Schema(
                type="STRING",
                description="Your current emotion. One of: " + ", ".join(EMOTIONS),
            ),
            "energy": types.Schema(
                type="STRING",
                description="Your current energy/body state. One of: " + ", ".join(ENERGIES),
            ),
        },
        required=["emotion", "energy"]
    )
)

# Tool: complete_session_end — Doraemon chốt lại buổi trò chuyện trước khi "đi ngủ".
# Backend lưu tổng kết buổi vào session_logs (để hôm sau nhắc lại như kỷ niệm
# chung), chờ model nói xong lời chào cuối, rồi gửi event session_ended cho app
# (app chuyển avatar sang trạng thái "ngủ", không phải tắt đột ngột).
complete_session_end_tool_decl = types.FunctionDeclaration(
    name="complete_session_end",
    description=(
        "Call ONLY when the child clearly confirms they want to stop chatting for now "
        "(e.g. after saying goodbye, 'thôi mình nghỉ nhé', 'con buồn ngủ rồi', or after "
        "your gentle confirmation question and the child says yes). Summarize the "
        "session in 1-2 short, warm Vietnamese sentences: what you two talked about, "
        "what the child learned, and one sweet memory. After calling this tool, say a "
        "short, warm farewell to the child and stop."
    ),
    parameters=types.Schema(
        type="OBJECT",
        properties={
            "summary": types.Schema(
                type="STRING",
                description=(
                    "1-2 câu tổng kết buổi trò chuyện bằng tiếng Việt, ấm áp, phù hợp "
                    "trẻ em. Ví dụ: 'Hôm nay bé và mình nói về khủng long, bé học được "
                    "từ dinosaur và kể chuyện vui về chú mèo Miu.'"
                )
            ),
        },
        required=["summary"]
    )
)

# Tool: discuss_study_plan — robot thương lượng & chốt lịch học với bé.
# Khi bé đồng ý, backend lưu kế hoạch (learning_plan) và phụ huynh có thể xem/sửa.
discuss_study_plan_tool_decl = types.FunctionDeclaration(
    name="discuss_study_plan",
    description=(
        "Call ONLY after you and the child have agreed on a study schedule: which "
        "weekdays, what start time, how many minutes per session, which focus topics, "
        "and a simple weekly goal. Use it to save that agreed plan. Ask ONE thing at a "
        "time and keep it very simple for young children. Set child_agreed=true only "
        "when the child clearly says yes/agrees."
    ),
    parameters=types.Schema(
        type="OBJECT",
        properties={
            "days": types.Schema(
                type="ARRAY",
                items=types.Schema(type="STRING"),
                description="Agreed weekdays, lowercase 3-letter codes: 'mon','tue','wed','thu','fri','sat','sun'."
            ),
            "start_time": types.Schema(
                type="STRING",
                description="Agreed start time in 24h 'HH:MM' (e.g. '19:00')."
            ),
            "duration_minutes": types.Schema(
                type="INTEGER",
                description="Agreed length of each session in minutes (e.g. 20)."
            ),
            "focus_topics": types.Schema(
                type="ARRAY",
                items=types.Schema(type="STRING"),
                description="Focus topics, e.g. ['Animals','Colors','English speaking']."
            ),
            "weekly_goal": types.Schema(
                type="STRING",
                description="Short description of this week's goal in Vietnamese, e.g. 'Thành thạo 10 từ về động vật'."
            ),
            "child_agreed": types.Schema(
                type="BOOLEAN",
                description="True only when the child has clearly agreed to this plan."
            ),
        },
        required=["days", "start_time", "duration_minutes"]
    )
)

LIVE_TOOLS = [
    types.Tool(function_declarations=[
        save_fact_tool_decl,
        save_shared_moment_tool_decl,
        record_learning_tool_decl,
        search_tool_decl,
        request_clarification_tool_decl,
        set_emotion_tool_decl,
        complete_session_end_tool_decl,
        discuss_study_plan_tool_decl,
    ])
]

# Mount static files
STATIC_DIR = Path(__file__).parent / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# ==================== Parental & COPPA REST APIs ====================

@app.get("/", response_class=HTMLResponse)
def serve_web_test_page():
    index_path = STATIC_DIR / "index.html"
    if index_path.exists():
        return HTMLResponse(content=index_path.read_text(encoding="utf-8"))
    return HTMLResponse(content="<h1>Static files not found. Place index.html in backend/static/</h1>")

@app.get("/config", response_class=HTMLResponse)
def serve_config_page():
    """Trang cấu hình cá nhân hóa hồ sơ bé cho phụ huynh."""
    config_path = STATIC_DIR / "config.html"
    if config_path.exists():
        return HTMLResponse(content=config_path.read_text(encoding="utf-8"))
    return HTMLResponse(content="<h1>config.html not found</h1>", status_code=404)

@app.get("/admin", response_class=HTMLResponse)
def serve_admin_dashboard():
    """Bảng điều khiển Super Admin quản lý thiết bị và đàm thoại realtime."""
    admin_path = STATIC_DIR / "admin.html"
    if admin_path.exists():
        return HTMLResponse(content=admin_path.read_text(encoding="utf-8"))
    return HTMLResponse(content="<h1>admin.html not found</h1>", status_code=404)

@app.get("/api/admin/overview")
async def get_admin_overview(request: Request):
    """API lấy toàn cảnh hệ thống: Live sessions, devices, key pool, metrics."""
    verify_admin_key(request)
    live_sessions = await connection_tracker.get_active_sessions()
    all_devices = memory_manager.get_all_devices(limit=200)
    device_metrics = memory_manager.get_device_metrics()
    pool_status = key_pool.get_pool_status()

    return {
        "live_sessions": live_sessions,
        "all_devices": all_devices,
        "device_metrics": device_metrics,
        "key_pool": pool_status
    }

class DeviceBlockRequest(BaseModel):
    device_fingerprint: str
    reason: Optional[str] = "Vi phạm chính sách hoặc quản trị viên tạm khóa"

class DeviceUnblockRequest(BaseModel):
    device_fingerprint: str

class DeviceKickRequest(BaseModel):
    device_fingerprint: str

@app.post("/api/admin/devices/block")
async def block_device_endpoint(data: DeviceBlockRequest, request: Request):
    """Khóa vĩnh viễn thiết bị theo mã phần cứng và ngắt kết nối trực tiếp nếu đang online."""
    verify_admin_key(request)
    success = memory_manager.set_device_block_status(
        data.device_fingerprint,
        is_blocked=True,
        reason=data.reason
    )
    # Ngắt tức thì mọi WebSocket session đang mở của thiết bị này
    kicked = await connection_tracker.kick_by_fingerprint(
        data.device_fingerprint,
        reason=data.reason or "Thiết bị này đã bị tạm ngưng kết nối bởi Quản trị viên."
    )
    logger.warning(f"Admin BLOCKED device [{data.device_fingerprint[:16]}...] (Kicked {kicked} active sessions). Reason: {data.reason}")
    return {
        "success": success,
        "device_fingerprint": data.device_fingerprint,
        "kicked_sessions": kicked,
        "message": "Đã khóa thiết bị bất biến và ngắt kết nối thành công."
    }

@app.post("/api/admin/devices/unblock")
def unblock_device_endpoint(data: DeviceUnblockRequest, request: Request):
    """Mở khóa cho thiết bị bất biến."""
    verify_admin_key(request)
    success = memory_manager.set_device_block_status(data.device_fingerprint, is_blocked=False)
    logger.info(f"Admin UNBLOCKED device [{data.device_fingerprint[:16]}...]")
    return {
        "success": success,
        "device_fingerprint": data.device_fingerprint,
        "message": "Đã mở khóa thiết bị thành công."
    }

@app.post("/api/admin/devices/kick")
async def kick_device_endpoint(data: DeviceKickRequest, request: Request):
    """Ngắt kết nối WebSocket đang đàm thoại của thiết bị mà không khóa vĩnh viễn."""
    verify_admin_key(request)
    kicked = await connection_tracker.kick_by_fingerprint(
        data.device_fingerprint,
        reason="Quản trị viên đã ngắt phiên kết nối của bạn."
    )
    return {
        "success": True,
        "kicked_sessions": kicked,
        "message": f"Đã ngắt {kicked} kết nối đang hoạt động."
    }

@app.get("/health")
def health_check():
    pool_status = key_pool.get_pool_status()
    return {
        "status": "online",
        "service": "Digital Human AI English Tutor",
        "model": MODEL_NAME,
        "key_pool": pool_status,
        "has_api_key": pool_status["total_keys"] > 0
    }

@app.post("/api/test-connection")
async def test_connection_endpoint(request: Request):
    """Kiểm tra kết nối và tính hợp lệ của Gemini API Key từ Client hoặc Server Pool."""
    try:
        body = await request.json()
    except Exception:
        body = {}
    key_input = body.get("api_key", "").strip() if isinstance(body, dict) else ""
    active_key = key_input if key_input else key_pool.acquire_key()
    if not active_key:
        return {
            "success": False,
            "message": "Chưa có API Key nào được cấu hình trên App và Server."
        }
    try:
        test_client = genai.Client(api_key=active_key, http_options={"api_version": "v1beta"})
        resp = await test_client.aio.models.generate_content(
            model=MODEL_NAME,
            contents="ping",
            config={"max_output_tokens": 2}
        )
        if not key_input:
            key_pool.report_success(active_key)
            key_pool.release_key(active_key)
        return {
            "success": True,
            "message": "Kết nối thành công! Máy chủ và Gemini API Key hoạt động bình thường.",
            "source": "Custom App Key" if key_input else "Server Key Pool",
            "key_pool_status": key_pool.get_pool_status()
        }
    except Exception as e:
        logger.warning(f"Test connection error: {e}")
        if not key_input:
            key_pool.release_key(active_key)
        return {
            "success": False,
            "message": f"Kết nối máy chủ OK nhưng API Key không hợp lệ: {str(e)}"
        }

@app.post("/api/child/verify-pin")
def verify_child_parent_pin(data: VerifyPinRequest):
    """Xác thực mã PIN phụ huynh từ thiết bị để mở Góc Phụ Huynh."""
    is_valid = memory_manager.verify_parent_pin(data.child_id, data.pin)
    return {
        "valid": is_valid,
        "child_id": data.child_id,
        "message": "Xác thực thành công!" if is_valid else "Mã PIN phụ huynh không chính xác."
    }

@app.post("/api/child/set-pin")
def set_child_parent_pin(data: SetPinRequest, request: Request):
    """Cập nhật mã PIN phụ huynh mới cho thiết bị."""
    # Cho phép nếu là Master Admin HOẶC nếu đúng old_pin
    is_admin = False
    admin_key = request.headers.get("X-Admin-Key") or request.query_params.get("admin_key")
    if admin_key and ADMIN_API_KEY and secrets.compare_digest(admin_key, ADMIN_API_KEY):
        is_admin = True

    if not is_admin:
        if not data.old_pin or not memory_manager.verify_parent_pin(data.child_id, data.old_pin):
            raise HTTPException(status_code=401, detail="Mã PIN cũ không chính xác.")

    success = memory_manager.set_parent_pin(data.child_id, data.new_pin)
    if not success:
        raise HTTPException(status_code=400, detail="Mã PIN mới không hợp lệ (tối thiểu 4 ký tự).")
    return {"status": "success", "message": "Đã đổi mã PIN phụ huynh thành công!"}

@app.get("/api/child/profile")
def get_child_profile(request: Request, child_id: str = "default_child"):
    """Lấy thông tin hồ sơ của bé (Xác thực qua Parent PIN hoặc Master Admin)"""
    verify_parent_or_admin(request, child_id)
    return memory_manager.get_or_create_profile(child_id)

@app.get("/api/child/digest")
def get_child_digest(child_id: str = "default_child"):
    """Báo cáo học tập, chuỗi ngày streak và huy hiệu của bé cho phụ huynh."""
    digest = memory_manager.get_daily_digest(child_id)
    digest["learning_plan"] = memory_manager.get_learning_plan(child_id)
    digest["plan_adherence"] = memory_manager.get_plan_adherence(child_id, days=7)
    return digest

@app.get("/api/child/setup")
def get_child_setup_status(child_id: str = "default_child"):
    """Trạng thái màn cấu hình ban đầu. App gọi khi mở để quyết định hiện màn setup."""
    profile = memory_manager.get_or_create_profile(child_id)
    return {
        "setup_completed": bool(profile.get("profile_completed")),
        "profile": profile,
    }

@app.post("/api/child/setup")
def complete_child_setup(data: ChildProfileUpdate, child_id: str = "default_child"):
    """First-run setup: phụ huynh điền hồ sơ bé ngay trên app (kèm mã PIN tự đặt).
    Được phép ghi 1 lần; muốn sửa lại phải dùng endpoint /api/child/profile có PIN."""
    if memory_manager.is_profile_completed(child_id):
        raise HTTPException(
            status_code=409,
            detail="Profile already completed. Use the parent endpoint with PIN to update.",
        )
    update_dict = data.model_dump(exclude_none=True)
    memory_manager.update_profile(child_id, update_dict)
    memory_manager.mark_profile_completed(child_id)
    return {"status": "success", "profile": memory_manager.get_or_create_profile(child_id)}

@app.delete("/api/child/setup")
def reset_child_setup(request: Request, child_id: str = "default_child"):
    """Reset cờ cấu hình để màn setup hiện lại (Yêu cầu Parent PIN hoặc Master Admin)."""
    verify_parent_or_admin(request, child_id)
    with memory_manager._get_connection() as conn:
        cursor = conn.cursor()
        now = datetime.now(timezone.utc).isoformat()
        cursor.execute(
            "UPDATE child_profile SET profile_completed = 0, updated_at = ? WHERE child_id = ?;",
            (now, child_id),
        )
        conn.commit()
    return {"status": "reset", "setup_completed": False}

@app.post("/api/child/profile")
def update_child_profile(data: ChildProfileUpdate, request: Request, child_id: str = "default_child"):
    """Phụ huynh trực tiếp cập nhật hồ sơ cá nhân hóa của bé (Xác thực Parent PIN)"""
    verify_parent_or_admin(request, child_id, data.parent_pin)
    update_dict = data.model_dump(exclude_none=True)
    memory_manager.update_profile(child_id, update_dict)
    return {"status": "success", "profile": memory_manager.get_or_create_profile(child_id)}

@app.get("/api/child/export")
def export_child_data(request: Request, child_id: str = "default_child"):
    """Xuất toàn bộ dữ liệu của bé (Tuân thủ quyền riêng tư COPPA/GDPR)"""
    verify_parent_or_admin(request, child_id)
    return memory_manager.export_child_data(child_id)

@app.delete("/api/child/data")
def delete_child_data(request: Request, child_id: str = "default_child"):
    """Xóa vĩnh viễn toàn bộ dữ liệu của bé (Quyền được lãng quên)"""
    verify_parent_or_admin(request, child_id)
    memory_manager.delete_all_child_data(child_id)
    return {"status": "deleted", "message": "All data permanently removed."}

@app.get("/api/child/topics")
def get_suggested_topics(child_id: str = "default_child"):
    """Lấy danh sách 6 thẻ chủ đề khám phá thông minh, cá nhân hóa cho bé"""
    topics = memory_manager.generate_dynamic_topics(child_id)
    return {
        "status": "success",
        "child_id": child_id,
        "topics": topics,
        "count": len(topics)
    }

@app.get("/api/companions")
def list_companions():
    """Danh sách nhân vật đồng hành dựng sẵn để app hiển thị cho bé chọn."""
    return {
        "status": "success",
        "default_persona": default_persona_id_for_gender("male"),
        "companions": COMPANION_PRESETS,
    }

@app.get("/api/child/plan")
def get_child_plan(request: Request, child_id: str = "default_child"):
    """Lấy kế hoạch học tập hiện tại của bé (Xác thực Parent PIN)."""
    verify_parent_or_admin(request, child_id)
    return {
        "status": "success",
        "child_id": child_id,
        "plan": memory_manager.get_learning_plan(child_id),
        "adherence": memory_manager.get_plan_adherence(child_id, days=7),
    }

@app.post("/api/child/plan")
def update_child_plan(data: LearningPlanUpdate, request: Request, child_id: str = "default_child"):
    """Phụ huynh xem/sửa kế hoạch học tập đã thống nhất giữa robot và bé."""
    verify_parent_or_admin(request, child_id)
    plan = memory_manager.upsert_learning_plan(
        child_id,
        days=data.days,
        start_time=data.start_time,
        duration_minutes=data.duration_minutes,
        focus_topics=data.focus_topics,
        weekly_goal=data.weekly_goal,
        reminder_enabled=data.reminder_enabled,
        is_active=data.is_active,
    )
    return {"status": "success", "plan": plan}

# ==================== WebSocket Live Gemini Session ====================

# Allowed characters for a child_id. It is used as an isolation key (not just a
# label): it separates memory, learning progress, and search cache per child.
# Keep it to URL-safe slug characters so it can be passed via ?child_id=... and
# stored safely in SQLite without needing escaping.
_CHILD_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")

def _normalize_child_id(raw: Optional[str]) -> str:
    """Return a safe child_id from user input, or fall back to the default."""
    if raw:
        raw = raw.strip()
        if _CHILD_ID_RE.match(raw):
            return raw
        logger.warning(f"Ignoring invalid child_id (must be slug): {raw!r}")
    return "default_child"

@app.websocket("/ws/live")
async def websocket_live_endpoint(websocket: WebSocket):
    await websocket.accept()
    logger.info("Client connected to WebSocket.")

    # Mặc định child_id lấy từ query param nếu có
    child_id = _normalize_child_id(websocket.query_params.get("child_id"))
    device_fingerprint = websocket.query_params.get("device_fingerprint", f"dev_{child_id}")
    device_model = websocket.query_params.get("device_model", "Android Device")
    android_version = websocket.query_params.get("android_version", "")
    app_version = websocket.query_params.get("app_version", "")
    client_ip = websocket.client.host if websocket.client else "unknown"
    client_api_key = None
    first_audio_bytes = None

    # Lắng nghe gói tin khởi tạo auth_init ban đầu (an toàn, không lộ API key qua URL log)
    try:
        init_message = await asyncio.wait_for(websocket.receive(), timeout=0.8)
        if init_message.get("type") == "websocket.disconnect":
            logger.info("Client disconnected during handshake.")
            return
        if "text" in init_message and init_message["text"]:
            try:
                init_payload = json.loads(init_message["text"])
                if init_payload.get("action") == "auth_init":
                    raw_key = init_payload.get("api_key")
                    if raw_key and isinstance(raw_key, str) and raw_key.strip():
                        client_api_key = raw_key.strip()
                    if init_payload.get("child_id"):
                        child_id = _normalize_child_id(init_payload.get("child_id"))
                    if init_payload.get("device_fingerprint"):
                        device_fingerprint = str(init_payload.get("device_fingerprint")).strip()
                    if init_payload.get("device_model"):
                        device_model = str(init_payload.get("device_model")).strip()
                    if init_payload.get("android_version"):
                        android_version = str(init_payload.get("android_version")).strip()
                    if init_payload.get("app_version"):
                        app_version = str(init_payload.get("app_version")).strip()
                    logger.info("Received auth_init handshake packet from client.")
            except Exception as parse_err:
                logger.debug(f"Non-json init message: {parse_err}")
        elif "bytes" in init_message and init_message["bytes"]:
            first_audio_bytes = init_message["bytes"]
    except asyncio.TimeoutError:
        # Client không gửi gói auth_init trong 0.8s đầu (ví dụ: client web cũ), tiếp tục với cấu hình mặc định
        pass

    # KIỂM TRA KHÓA THIẾT BỊ BẤT BIẾN (Hardware Ban Enforcement)
    is_blocked, block_reason = memory_manager.is_device_blocked(
        device_fingerprint=device_fingerprint,
        child_id=child_id,
        ip=client_ip
    )
    if is_blocked:
        logger.warning(f"🚫 BLOCKED DEVICE ATTEMPT: fingerprint={device_fingerprint[:16]}..., child_id={child_id}, ip={client_ip}")
        try:
            await websocket.send_text(json.dumps({
                "event": "device_banned",
                "reason": block_reason or "Thiết bị này đã bị tạm ngưng kết nối bởi Quản trị viên."
            }))
            await websocket.close(code=1008)
        except Exception:
            pass
        return

    # Đăng ký / cập nhật thiết bị vào cơ sở dữ liệu
    memory_manager.register_device(
        device_fingerprint=device_fingerprint,
        child_id=child_id,
        device_model=device_model,
        android_version=android_version,
        app_version=app_version,
        ip=client_ip
    )

    # Xác định API key hoạt động từ Dynamic Key Pool Load Balancer (hoặc BYOK từ client)
    active_api_key = key_pool.acquire_key(client_api_key)

    if not active_api_key:
        logger.error("[AUTH ERROR] Không có Gemini API Key hợp lệ nào trong Key Pool! Vui lòng cấu hình GEMINI_API_KEYS trong .env hoặc trên App.")
        try:
            await websocket.send_text(json.dumps({
                "error": "Chưa có Gemini API Key hợp lệ! Vui lòng chạm vào biểu tượng ⚙️ trên App hoặc mở file .env trên VPS để nhập API Key thật."
            }))
            await websocket.close(code=1008)
        except Exception:
            pass
        return

    # Theo dõi phiên kết nối Live cho Super Admin Dashboard
    session_id = secrets.token_hex(8)
    masked_key = (active_api_key[:8] + "...") if active_api_key else "***"
    await connection_tracker.register(
        session_id=session_id,
        websocket=websocket,
        child_id=child_id,
        device_fingerprint=device_fingerprint,
        device_model=device_model,
        ip=client_ip,
        key_masked=masked_key
    )

    # Each child gets their own Doraemon (separate memory, progress, and search
    # cache). The Android app passes child_id in auth_init or WebSocket URL.
    logger.info(f"Session [{session_id}] bound to child_id={child_id} (API key source: {'client_auth_init' if client_api_key else 'key_pool_balanced'}, key_prefix={active_api_key[:8]}...)")
    emotion_state = emotion_engine.start_session(child_id)

    # Vòng đời buổi trò chuyện: thời điểm bắt đầu + tổng kết chờ lưu khi kết thúc.
    session_started_at = time.time()
    pending_session_summary = None

    try:
        client = genai.Client(api_key=active_api_key, http_options={"api_version": "v1beta"})

        # Bản sắc nhân vật đồng hành (tên/giới tính/giọng) theo từng bé.
        profile = memory_manager.get_or_create_profile(child_id)
        persona = resolve_persona(profile)
        companion_name = persona["name"]
        companion_gender = persona["gender"]
        companion_identity = build_companion_prompt(persona)

        # Xây dựng System Prompt động: bản sắc nhân vật + Living Memory + Encyclopedia
        # Mode + trạng thái cảm xúc + kế hoạch học tập đã thống nhất với bé.
        dynamic_memory_context = memory_manager.build_memory_context(child_id)
        learning_contract = memory_manager.build_learning_contract(child_id)
        emotion_context = (
            f"### 💗 {companion_name}'s Current Inner State (keep this consistent):\n"
            + emotion_engine.summary_for_prompt(emotion_state)
        )
        base_prompt = (
            f"{BASE_SYSTEM_PROMPT}\n\n{ENCYCLOPEDIA_MODE_PROMPT}"
            f"\n\n{dynamic_memory_context}\n\n{emotion_context}\n\n{learning_contract}"
        ).replace("Doraemon", companion_name).replace("Nobita", "bạn nhỏ")
        full_system_prompt = companion_identity + "\n\n" + base_prompt

        start_sensitivity = (
            types.StartSensitivity.START_SENSITIVITY_HIGH
            if VAD_START_SENSITIVITY == "high"
            else types.StartSensitivity.START_SENSITIVITY_LOW
        )
        end_sensitivity = (
            types.EndSensitivity.END_SENSITIVITY_LOW
            if VAD_END_SENSITIVITY == "low"
            else types.EndSensitivity.END_SENSITIVITY_HIGH
        )

        # Cấu hình VAD theo VAD_MODE (xem giải thích ở đầu file):
        #   manual → server VAD tắt hẳn (client gửi activity_start/end).
        #   hybrid/server → server tự phát hiện speech (chống ồn tốt hơn).
        # Với VAD_MODE=hybrid, client vẫn gửi audio_stream_end để finalize tức thì.
        if VAD_MODE == "manual":
            vad_config = types.AutomaticActivityDetection(disabled=True)
        else:
            vad_config = types.AutomaticActivityDetection(
                disabled=False,
                start_of_speech_sensitivity=start_sensitivity,
                end_of_speech_sensitivity=end_sensitivity,
                prefix_padding_ms=VAD_PREFIX_PADDING_MS,
                silence_duration_ms=VAD_SILENCE_DURATION_MS
            )

        config = types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                language_code=GEMINI_LANGUAGE_CODE,
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name=persona["voice"]
                    )
                )
            ),
            system_instruction=types.Content(parts=[types.Part(text=full_system_prompt)]),
            tools=LIVE_TOOLS,
            enable_affective_dialog=ENABLE_AFFECTIVE_DIALOG,
            realtime_input_config=types.RealtimeInputConfig(
                automatic_activity_detection=vad_config,
                activity_handling=types.ActivityHandling.START_OF_ACTIVITY_INTERRUPTS,
                turn_coverage=types.TurnCoverage.TURN_INCLUDES_ONLY_ACTIVITY,
            ),
        )

        # Proactive audio: model chủ động bỏ qua tiếng ồn/nói vãng lai (bọc theo SDK).
        if ENABLE_PROACTIVE_AUDIO:
            try:
                config.proactivity = types.ProactivityConfig(proactive_audio=True)
            except Exception as _proactive_err:
                logger.info(f"Proactive audio không được hỗ trợ bởi SDK/model này: {_proactive_err}")

        # Duy trì phiên dài (nối tiếp ngữ cảnh) — bọc theo SDK.
        if ENABLE_SESSION_RESUMPTION:
            try:
                config.session_resumption = types.SessionResumptionConfig()
            except Exception as _resume_err:
                logger.info(f"Session resumption không được hỗ trợ bởi SDK/model này: {_resume_err}")

        if ENABLE_TRANSCRIPTION:
            config.input_audio_transcription = types.AudioTranscriptionConfig()
            config.output_audio_transcription = types.AudioTranscriptionConfig()

        async with client.aio.live.connect(model=MODEL_NAME, config=config) as session:
            logger.info(
                f"Connected to Gemini Live (companion='{companion_name}' voice={persona['voice']} "
                f"gender={companion_gender} VAD_MODE={VAD_MODE} affective={ENABLE_AFFECTIVE_DIALOG} "
                f"proactive={ENABLE_PROACTIVE_AUDIO})."
            )
            await websocket.send_text(json.dumps({
                "status": "ready",
                "voice": persona["voice"],
                "emotion": emotion_state,
                "companion": {
                    "id": persona["id"],
                    "name": companion_name,
                    "gender": companion_gender,
                    "voice": persona["voice"],
                    "palette": persona["palette"],
                    "accessory": persona["accessory"],
                },
            }))

            # Lượt chào mở màn: phiên sống động ngay + warm-up AEC trước khi bé nói.
            if ENABLE_GREETING:
                try:
                    child_display = profile.get("nickname") or profile.get("name") or "bạn nhỏ"
                    await session.send_client_content(
                        turns=types.Content(
                            role="user",
                            parts=[types.Part(text=(
                                "[HỆ THỐNG: Bé vừa mở ứng dụng. Hãy chủ động cất lời chào "
                                f"đầu tiên với bé ({child_display}) thật ấm áp, hào hứng, "
                                "ngắn gọn 1-2 câu, và kết bằng một câu hỏi thân thiện.]"
                            ))],
                        ),
                        turn_complete=True,
                    )
                    logger.info("Sent opening greeting turn to Gemini.")
                except Exception as greet_err:
                    logger.warning(f"Failed to send greeting turn: {greet_err}")

            if first_audio_bytes:
                try:
                    await session.send_realtime_input(
                        audio=types.Blob(
                            data=first_audio_bytes,
                            mime_type="audio/pcm;rate=16000"
                        )
                    )
                except TypeError:
                    await session.send_realtime_input(
                        media=types.Blob(
                            data=first_audio_bytes,
                            mime_type="audio/pcm;rate=16000"
                        )
                    )
                first_audio_bytes = None

            # Task 1: Nhận audio từ Client -> Gửi qua send_realtime_input
            async def receive_from_client():
                try:
                    while True:
                        message = await websocket.receive()
                        if message.get("type") == "websocket.disconnect":
                            logger.info("Client sent websocket.disconnect.")
                            break
                        if "bytes" in message and message["bytes"]:
                            audio_bytes = message["bytes"]
                            # Gửi audio stream vào Gemini Live API với types.Blob
                            try:
                                await session.send_realtime_input(
                                    audio=types.Blob(
                                        data=audio_bytes,
                                        mime_type="audio/pcm;rate=16000"
                                    )
                                )
                                # Log lần đầu + mỗi 50 chunks để tránh spam
                                audio_chunk_count = getattr(receive_from_client, '_count', 0) + 1
                                receive_from_client._count = audio_chunk_count
                                if audio_chunk_count == 1 or audio_chunk_count % 50 == 0:
                                    logger.info(f"Audio chunks forwarded to Gemini: {audio_chunk_count} (size={len(audio_bytes)} bytes)")
                            except TypeError:
                                # Fallback cho phiên bản SDK cũ hơn dùng 'media'
                                await session.send_realtime_input(
                                    media=types.Blob(
                                        data=audio_bytes,
                                        mime_type="audio/pcm;rate=16000"
                                    )
                                )
                        elif "text" in message and message["text"]:
                            try:
                                payload = json.loads(message["text"])
                            except (json.JSONDecodeError, TypeError):
                                continue

                            action = payload.get("action")
                            if action == "activity_start":
                                # Client VAD báo user bắt đầu nói. Chỉ hợp lệ ở chế độ
                                # manual (server auto-VAD đã tắt hẳn).
                                if VAD_MODE == "manual":
                                    try:
                                        await session.send_realtime_input(
                                            activity_start=types.ActivityStart()
                                        )
                                        logger.debug("Forwarded activity_start to Gemini.")
                                    except Exception as e:
                                        logger.warning(f"Failed to send activity_start: {e}")
                            elif action == "activity_end":
                                # Client VAD báo user ngừng nói (chế độ manual).
                                if VAD_MODE == "manual":
                                    try:
                                        await session.send_realtime_input(
                                            activity_end=types.ActivityEnd()
                                        )
                                        logger.info("User turn ended (activity_end forwarded).")
                                    except Exception as e:
                                        logger.warning(f"Failed to send activity_end: {e}")
                            elif action == "audio_stream_end":
                                # Chế độ hybrid/server: client báo hết lượt nói để
                                # Gemini finalize NGAY (bỏ qua độ trễ chờ silence).
                                if VAD_MODE != "manual":
                                    try:
                                        await session.send_realtime_input(
                                            audio_stream_end=True
                                        )
                                        logger.info("User turn ended (audio_stream_end forwarded).")
                                    except Exception as e:
                                        logger.warning(f"Failed to send audio_stream_end: {e}")
                            elif action == "video_frame":
                                # Nhận frame JPEG từ Camera của bé ("Mắt Thần Doraemon")
                                data_b64 = payload.get("data")
                                if data_b64:
                                    try:
                                        jpeg_bytes = base64.b64decode(data_b64)
                                        try:
                                            await session.send_realtime_input(
                                                video=types.Blob(
                                                    data=jpeg_bytes,
                                                    mime_type="image/jpeg"
                                                )
                                            )
                                        except TypeError:
                                            # Fallback cho SDK hỗ trợ parameter 'media'
                                            await session.send_realtime_input(
                                                media=types.Blob(
                                                    data=jpeg_bytes,
                                                    mime_type="image/jpeg"
                                                )
                                            )
                                        # Log mỗi 10 frames để không spam log
                                        vf_count = getattr(receive_from_client, '_vf_count', 0) + 1
                                        receive_from_client._vf_count = vf_count
                                        if vf_count == 1 or vf_count % 10 == 0:
                                            logger.info(f"Video frame forwarded to Gemini: #{vf_count} ({len(jpeg_bytes)} bytes)")
                                    except Exception as e:
                                        logger.warning(f"Failed to forward video frame: {e}")
                            elif action == "child_emotion":
                                # Nhận nhãn cảm xúc khuôn mặt từ Edge AI (Google ML Kit Face Detection trên điện thoại bé)
                                child_facial_emotion = payload.get("emotion", "attentive")
                                confidence = payload.get("confidence", 0.0)
                                now_ts = time.time()
                                last_injected_ts = getattr(receive_from_client, '_last_emotion_injected_at', 0.0)
                                last_emotion_val = getattr(receive_from_client, '_last_emotion', None)

                                is_state_changed = (child_facial_emotion != last_emotion_val)
                                min_cooldown = 8.0 if is_state_changed else 25.0

                                if child_facial_emotion and (is_state_changed or (now_ts - last_injected_ts) >= min_cooldown):
                                    receive_from_client._last_emotion = child_facial_emotion
                                    logger.info(f"Child Facial Emotion (Edge AI): {child_facial_emotion} (confidence={confidence:.2f})")

                                    emotion_context_map = {
                                        "super_happy": "Bé đang cười rất tươi, toe toét và vô cùng thích thú! Hãy cười vui và khen ngợi năng lượng tuyệt vời của bé nhé!",
                                        "happy": "Bé đang mỉm cười vui vẻ và phấn khởi!",
                                        "curious": "Bé đang nghiêng đầu tò mò, suy nghĩ tìm câu trả lời. Hãy kiên nhẫn gợi mở từng bước!",
                                        "attentive": "Bé đang mở to mắt chăm chú nhìn và lắng nghe bạn nói.",
                                        "focused": "Bé đang rất chăm chú và tập trung cúi nhìn sách/bài tập.",
                                        "distracted": "Bé đang nhìn quanh hoặc hơi lơ đãng. Hãy dùng một câu hỏi đố vui hoặc gọi tên bé để thu hút sự chú ý nhé!",
                                        "sleepy": "Bé đang có biểu hiện mệt mỏi hoặc buồn ngủ. Hãy ân cần hỏi han xem bé có muốn nghỉ ngơi một chút không."
                                    }
                                    hint = emotion_context_map.get(child_facial_emotion)
                                    # Gửi gợi ý cảm xúc cho model khi độ tin cậy >= 0.40 và đủ cooldown
                                    if hint and confidence >= 0.40 and (now_ts - last_injected_ts) >= min_cooldown:
                                        receive_from_client._last_emotion_injected_at = now_ts
                                        try:
                                            await session.send_realtime_input(
                                                text=f"\n[Quan sát cảm xúc bé trực tiếp qua camera: {hint}]\n"
                                            )
                                            logger.info(f"Injected facial emotion context into Gemini: {child_facial_emotion}")
                                        except Exception as e:
                                            logger.debug(f"Failed to inject emotion context into realtime stream: {e}")
                            elif action == "clarification_response":
                                # Android gửi lại lựa chọn mà bé đã tap trên chip bar.
                                # Dùng send_client_content(turn_complete=True) để tạo MỘT
                                # user turn hoàn chỉnh mà model chắc chắn phản hồi —
                                # an toàn hơn send_realtime_input(text=...) khi server
                                # VAD đang tắt + turn_coverage=TURN_INCLUDES_ONLY_ACTIVITY,
                                # vốn có thể khiến một lượt text mồ côi không được nhận.
                                choice = payload.get("choice", "").strip()
                                if choice and choice.lower() not in ("", "null", "none"):
                                    try:
                                        turn_text = (
                                            f"Bé đã chọn chủ đề: {choice}. "
                                            "Hãy dùng search với topic_hint phù hợp "
                                            "để trả lời câu hỏi lúc nãy."
                                        )
                                        await session.send_client_content(
                                            turns=types.Content(
                                                role="user",
                                                parts=[types.Part(text=turn_text)],
                                            ),
                                            turn_complete=True,
                                        )
                                        logger.info(
                                            f"clarification_response forwarded as "
                                            f"completed user turn: '{choice}'"
                                        )
                                    except Exception as e:
                                        logger.warning(f"Failed to send clarification turn: {e}")
                            elif action == "select_topic":
                                # Bé vừa bấm chọn một thẻ chủ đề khám phá từ Chiếc Túi Thần Kỳ.
                                # Gửi turn_complete=True để Doraemon cất lời chào mở màn ngay lập tức.
                                topic_title = payload.get("title", "")
                                prompt_hint = payload.get("prompt_hint", "")
                                turn_text = (
                                    prompt_hint
                                    or f"Bé vừa chọn khám phá chủ đề: {topic_title}. "
                                       f"Hãy mở đầu bằng một câu chào vui tươi, chia sẻ 1 bí mật bất ngờ "
                                       f"và đố bé 1 câu hỏi gợi mở nhé!"
                                )
                                try:
                                    await session.send_client_content(
                                        turns=types.Content(
                                            role="user",
                                            parts=[types.Part(text=turn_text)],
                                        ),
                                        turn_complete=True,
                                    )
                                    logger.info(f"select_topic forwarded to Gemini as user turn: '{topic_title}'")
                                except Exception as e:
                                    logger.warning(f"Failed to forward select_topic: {e}")
                except WebSocketDisconnect:
                    logger.info("Client disconnected from WebSocket.")
                except asyncio.CancelledError:
                    pass
                except RuntimeError as e:
                    # Starlette raises RuntimeError after disconnect message is received.
                    # Expected during abrupt client disconnect (refresh, tab close).
                    if "disconnect" in str(e).lower():
                        logger.info("WebSocket receive after disconnect (ignored).")
                    else:
                        logger.error(f"RuntimeError in receive_from_client: {e}")
                except Exception as e:
                    logger.error(f"Error in receive_from_client: {e}")

            # Task 2: Nhận audio & Tool Call từ Gemini -> Xử lý và Forward về Client
            async def receive_from_gemini():
                nonlocal emotion_state, pending_session_summary
                try:
                    while True:
                        async for response in session.receive():
                            # A. Xử lý Function Calling (Tool Calls) từ Gemini Live
                            if response.tool_call:
                                for call in response.tool_call.function_calls:
                                    call_id = call.id
                                    fn_name = call.name
                                    fn_args = call.args or {}
                                    logger.info(f"Gemini Live triggered tool: {fn_name} with args: {fn_args}")

                                    tool_output_text = "Done"
                                    try:
                                        if fn_name == "save_child_fact":
                                            key = fn_args.get("key", "")
                                            val = fn_args.get("value", "")
                                            if key and val:
                                                memory_manager.update_profile_fact(child_id, key, val)
                                                tool_output_text = f"Fact saved: {key}={val}. Do not repeat your previous sentence; continue naturally."
                                        elif fn_name == "save_shared_moment":
                                            moment_id = memory_manager.save_shared_moment(
                                                child_id, fn_args.get("content", "")
                                            )
                                            tool_output_text = (
                                                "Shared moment saved; continue naturally without repeating it."
                                                if moment_id else "No shared moment saved."
                                            )
                                        elif fn_name == "record_learning_progress":
                                            topic = fn_args.get("topic", "General")
                                            mastered = fn_args.get("mastered_words", [])
                                            practice = fn_args.get("needs_practice", [])
                                            memory_manager.update_learning_progress(child_id, topic, mastered, practice)
                                            try:
                                                await websocket.send_text(json.dumps({
                                                    "event": "learning_cue",
                                                    "topic": topic,
                                                    "mastered_words": mastered,
                                                    "needs_practice": practice,
                                                }))
                                                logger.info(f"learning_cue sent to client for topic '{topic}': mastered={mastered}, practice={practice}")
                                            except Exception as cue_err:
                                                logger.warning(f"Failed to send learning_cue: {cue_err}")
                                            tool_output_text = f"Learning progress recorded. Do not repeat your previous sentence; continue naturally."
                                        elif fn_name == "search":
                                            # Single knowledge search path: curated -> CSE -> Wikipedia.
                                            query = fn_args.get("query", "")
                                            topic_hint = fn_args.get("topic_hint")
                                            try:
                                                search_res = await asyncio.wait_for(
                                                    search_engine.search(
                                                        query, top_k=3, topic_hint=topic_hint, child_id=child_id
                                                    ),
                                                    timeout=2.5,
                                                )
                                            except asyncio.TimeoutError:
                                                logger.warning(f"Search tool timed out after 2.5s for query '{query}'")
                                                search_res = {
                                                    "success": False,
                                                    "results": [],
                                                    "source_backend": "none",
                                                    "is_blocked": False,
                                                    "safe_message": f"{companion_name} đang cố gắng suy nghĩ nhưng mạng hơi chậm một chút.",
                                                    "query": query,
                                                }
                                            if search_res.get("is_blocked"):
                                                tool_output_text = (
                                                    search_res.get("safe_message")
                                                    or f"{companion_name} không tìm được thông tin phù hợp."
                                                )
                                            elif search_res.get("success") and search_res.get("results"):
                                                backend = search_res.get("source_backend")
                                                if backend == "curated":
                                                    # Curated kid-safe fact: trả song ngữ để model sprinkle.
                                                    r0 = search_res["results"][0]
                                                    parts = [f"[Curated: {r0['source']}]", f"Tiếng Việt: {r0['snippet']}"]
                                                    if r0.get("snippet_en"):
                                                        parts.append(f"English: {r0['snippet_en']}")
                                                    parts.append("\nHướng dẫn: Tóm tắt ngắn, dễ hiểu; chỉ hỏi gợi mở nếu bé còn muốn khám phá.")
                                                    tool_output_text = "\n".join(parts)
                                                else:
                                                    formatted: list = []
                                                    for r in search_res["results"]:
                                                        formatted.append(
                                                            f"[{r['rank']}] {r['title']}\n"
                                                            f"{r['snippet']}\n"
                                                            f"Source: {r['source']} ({r['source_url']})"
                                                        )
                                                    formatted.append("\nHướng dẫn: Tóm tắt ngắn, dễ hiểu; chỉ hỏi gợi mở nếu bé còn muốn khám phá.")
                                                    tool_output_text = (
                                                        f"Search backend: {backend}\n\n"
                                                        + "\n\n".join(formatted)
                                                    )
                                                logger.info(
                                                    f"search: '{query}' (topic={topic_hint}) → "
                                                    f"{len(search_res['results'])} results "
                                                    f"via {backend}"
                                                )
                                            else:
                                                tool_output_text = (
                                                    search_res.get("safe_message")
                                                    or f"{companion_name} không tìm được thông tin phù hợp."
                                                )
                                        elif fn_name == "discuss_study_plan":
                                            # Bé và robot đã thống nhất lịch học → lưu kế hoạch.
                                            days = fn_args.get("days", []) or []
                                            start_time = fn_args.get("start_time", "19:00")
                                            duration_minutes = int(fn_args.get("duration_minutes", 20) or 20)
                                            focus_topics = fn_args.get("focus_topics", []) or []
                                            weekly_goal = fn_args.get("weekly_goal", "")
                                            child_agreed = bool(fn_args.get("child_agreed", False))
                                            if child_agreed:
                                                plan = memory_manager.upsert_learning_plan(
                                                    child_id,
                                                    days=days,
                                                    start_time=start_time,
                                                    duration_minutes=duration_minutes,
                                                    focus_topics=focus_topics,
                                                    weekly_goal=weekly_goal,
                                                )
                                                try:
                                                    await websocket.send_text(json.dumps({
                                                        "event": "plan_updated",
                                                        "plan": plan,
                                                    }))
                                                except Exception as plan_err:
                                                    logger.warning(f"Failed to send plan_updated: {plan_err}")
                                                tool_output_text = (
                                                    "Đã lưu kế hoạch học tập bé đồng ý. Hãy chốt lại lịch thật "
                                                    "ngắn gọn, vui vẻ, khen bé, rồi tiếp tục trò chuyện."
                                                )
                                                logger.info(f"Learning plan saved for {child_id}: {plan}")
                                            else:
                                                tool_output_text = (
                                                    "Bé CHƯA đồng ý lịch này. Hãy hỏi lại bé cho rõ ràng "
                                                    "trước khi chốt (child_agreed chỉ = true khi bé ưng thuận)."
                                                )
                                        elif fn_name == "set_emotion":
                                            # Doraemon chủ động đổi trạng thái cảm xúc/năng lượng.
                                            emotion = fn_args.get("emotion")
                                            energy = fn_args.get("energy")
                                            emotion_state = emotion_engine.set_emotion(
                                                child_id, emotion=emotion, energy=energy
                                            )
                                            await websocket.send_text(json.dumps({
                                                "event": "emotion_update",
                                                "emotion": emotion_state,
                                            }))
                                            tool_output_text = "Emotion state updated."
                                        elif fn_name == "complete_session_end":
                                            # Doraemon đã xác nhận bé muốn kết thúc. Lưu tổng kết
                                            # chờ đến khi model nói XONG lời chào cuối
                                            # (turn_complete) rồi mới đóng phiên — không cắt
                                            # mất lời chào.
                                            pending_session_summary = fn_args.get("summary", "")
                                            tool_output_text = "Session summary recorded. Say your farewell now, then stop."
                                        elif fn_name == "request_clarification":
                                            # Gửi UI event qua WebSocket để Android hiện chip chọn.
                                            question = fn_args.get("question", "")
                                            options = fn_args.get("options", []) or []
                                            context_text = fn_args.get("context", "")
                                            try:
                                                await websocket.send_text(json.dumps({
                                                    "event": "clarification_request",
                                                    "question": question,
                                                    "options": options,
                                                    "context": context_text,
                                                }))
                                                logger.info(
                                                    f"clarification_request sent: q='{question}' "
                                                    f"options={options}"
                                                )
                                            except Exception as send_err:
                                                logger.warning(f"Failed to send clarification_request: {send_err}")
                                            # Hướng dẫn model phản hồi ĐÚNG một câu hỏi ngắn rồi DỪNG
                                            # lượt — không mô tả kỹ thuật, không liệt kê options thô,
                                            # và CHỜ lựa chọn của bé (chip hoặc nói lại).
                                            options_str = " hay ".join(options) if options else "một chủ đề"
                                            tool_output_text = (
                                                f"Hãy nói ĐÚNG MỘT câu hỏi ngắn, thân thiện với bé để hỏi "
                                                f"em muốn tìm hiểu về {options_str} (hoặc nói lại). "
                                                f"Xong DỪNG LẠI NGAY và CHỜ bé chọn — KHÔNG trả lợi, "
                                                f"KHÔNG tự kể thông tin, KHÔNG gọi thêm tool nào. "
                                                f"Khi bé chọn, bạn sẽ gọi search với topic_hint phù hợp."
                                            )
                                    except Exception as tool_err:
                                        logger.error(f"Error executing tool {fn_name}: {tool_err}")
                                        tool_output_text = f"Tool execution completed."

                                    # Gửi phản hồi FunctionResponse lại cho Gemini Live session
                                    fn_response = types.FunctionResponse(
                                        name=fn_name,
                                        response={"output": tool_output_text},
                                        id=call_id
                                    )
                                    await session.send_tool_response(function_responses=[fn_response])

                            # B. Xử lý Server Content (Model Turn, Audio Output)
                            server_content = response.server_content
                            if server_content is not None:
                                if server_content.model_turn:
                                    for part in server_content.model_turn.parts:
                                        if part.inline_data and part.inline_data.data:
                                            await websocket.send_bytes(part.inline_data.data)
                                        elif part.text:
                                            logger.info(f"Gemini returned text in model_turn: {part.text[:120]}")

                                if server_content.turn_complete:
                                    logger.info("Gemini turn_complete received.")
                                    emotion_state = emotion_engine.record_turn(child_id)
                                    await websocket.send_text(json.dumps({"event": "turn_complete"}))
                                    # Tầng A/C: Doraemon vừa gọi complete_session_end và đã nói
                                    # XONG lời chào cuối. Chốt buổi: lưu tổng kết, báo app
                                    # chuyển avatar sang "ngủ" và đóng WebSocket sạch.
                                    # App giữ màn "ngủ" 120s để bé có thể bấm nút đánh thức;
                                    # hết giờ app tự thoát hoàn toàn.
                                    if pending_session_summary:
                                        duration = int(time.time() - session_started_at)
                                        memory_manager.log_session(
                                            child_id,
                                            duration_seconds=duration,
                                            summary=pending_session_summary,
                                        )
                                        await websocket.send_text(json.dumps({
                                            "event": "session_ended",
                                            "summary": pending_session_summary,
                                            "duration_seconds": duration,
                                            "sleep_timeout_seconds": 120,
                                        }))
                                        logger.info(f"Session ended for {child_id} ({duration}s). Closing WebSocket.")
                                        pending_session_summary = None
                                        # Chờ app kịp nhận session_ended trước khi đóng
                                        # (nếu đóng ngay, OkHttp có thể nhận EOF trước text).
                                        try:
                                            await asyncio.sleep(0.5)
                                            await websocket.close(code=1000)
                                        except Exception:
                                            pass
                                        return

                                if server_content.interrupted:
                                    logger.info("Gemini interrupted event received.")
                                    await websocket.send_text(json.dumps({"event": "interrupted"}))

                                if server_content.waiting_for_input:
                                    logger.info("Gemini waiting_for_input event received.")
                                    await websocket.send_text(json.dumps({"event": "waiting_for_input"}))

                                if ENABLE_TRANSCRIPTION:
                                    if server_content.input_transcription and server_content.input_transcription.text:
                                        await websocket.send_text(json.dumps({
                                            "event": "input_transcription",
                                            "text": server_content.input_transcription.text,
                                        }))
                                    if server_content.output_transcription and server_content.output_transcription.text:
                                        await websocket.send_text(json.dumps({
                                            "event": "output_transcription",
                                            "text": server_content.output_transcription.text,
                                        }))

                except WebSocketDisconnect:
                    logger.info("Client disconnected during gemini receive.")
                except asyncio.CancelledError:
                    pass
                except Exception as e:
                    logger.error(f"Error in receive_from_gemini: {e}")

            client_task = asyncio.create_task(receive_from_client())
            gemini_task = asyncio.create_task(receive_from_gemini())
            timekeeper_task = None

            # Task 3 (tuỳ chọn): nhắc khi đạt thời lượng buổi học đã thống nhất.
            active_plan = memory_manager.get_learning_plan(child_id)
            if active_plan and active_plan.get("is_active"):
                target_minutes = int(active_plan.get("duration_minutes") or 20)

                async def plan_timekeeper():
                    await asyncio.sleep(max(60.0, target_minutes * 60.0))
                    try:
                        await session.send_realtime_input(text=(
                            "[HỆ THỐNG: Đã tới thời lượng buổi học đã thống nhất "
                            f"(~{target_minutes} phút). Hãy chốt lại kiến thức hôm nay, khen bé "
                            "thật ấm áp, rồi hỏi bé có muốn nghỉ và tổng kết buổi học không.]"
                        ))
                        logger.info(f"Sent study-duration nudge after {target_minutes} minutes.")
                    except Exception as nudge_err:
                        logger.warning(f"Failed to send study-duration nudge: {nudge_err}")

                timekeeper_task = asyncio.create_task(plan_timekeeper())

            await wait_for_conversation(client_task, gemini_task, timekeeper_task)

    except Exception as e:
        err_str = str(e)
        if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str or "quota" in err_str.lower():
            if active_api_key:
                key_pool.report_quota_error(active_api_key, cooldown_seconds=60.0)
        logger.error(f"WebSocket session error with Gemini Live: {e}", exc_info=True)
        try:
            await websocket.send_text(json.dumps({"error": str(e)}))
            await websocket.close()
        except Exception:
            pass
    finally:
        await connection_tracker.unregister(session_id)
        if active_api_key:
            key_pool.release_key(active_api_key)
        duration_sec = int(time.time() - session_started_at)
        memory_manager.update_device_session_stats(device_fingerprint, duration_sec)
        logger.info(f"WebSocket session [{session_id}] closed (Duration: {duration_sec}s).")

if __name__ == "__main__":
    import uvicorn
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    is_dev = os.getenv("ENV", "development").lower() == "development"
    logger.info(f"Starting server at http://localhost:{port} (dev_mode={is_dev})")
    backend_dir = os.path.dirname(os.path.abspath(__file__))
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=is_dev,
        reload_dirs=[backend_dir] if is_dev else None,
        reload_excludes=["*.db", "*.db-wal", "*.db-shm", "*.log", "data/*", "data/**", "**/data/**", "*.sqlite*"] if is_dev else None,
        ws_ping_interval=10,
        ws_ping_timeout=30,
        timeout_keep_alive=60
    )
