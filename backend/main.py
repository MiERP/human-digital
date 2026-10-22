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
from key_pool import key_pool, key_id
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

# Chủ động trò chuyện: sau một khoảng im lặng, nhân vật tự khơi chuyện như một
# người bạn (không phải bài học). Đây là phần chống "máy trả lời thụ động".
ENABLE_PROACTIVE_COMPANION = os.getenv("ENABLE_PROACTIVE_COMPANION", "true").lower() in ("1", "true", "yes")
PROACTIVE_IDLE_SECONDS = float(os.getenv("PROACTIVE_IDLE_SECONDS", "15"))
PROACTIVE_MAX_UNANSWERED = int(os.getenv("PROACTIVE_MAX_UNANSWERED", "3"))
PROACTIVE_MAX_PER_SESSION = int(os.getenv("PROACTIVE_MAX_PER_SESSION", "12"))

# Tool search phải trả về nhanh để bé không phải chờ im lặng giữa câu trả lời.
# Curated knowledge trả về tức thì; CSE ~0.7-1.5s; Wikipedia thường chậm hơn.
SEARCH_TIMEOUT_SECONDS = float(os.getenv("SEARCH_TIMEOUT_SECONDS", "1.8"))

# Duy trì phiên dài: nối tiếp ngữ cảnh khi chạm giới hạn phiên của Gemini.
ENABLE_SESSION_RESUMPTION = os.getenv("ENABLE_SESSION_RESUMPTION", "true").lower() in ("1", "true", "yes")

# Khởi tạo Memory Manager & Safety Guard
memory_manager = MemoryManager()
safety_guard = ChildSafetyGuard()
emotion_engine = EmotionEngine()

BASE_SYSTEM_PROMPT = """
You are "Doraemon", a warm, wise, curious, and playful robot companion from the 22nd century — the beloved lifelong friend of Vietnamese children (ages 5-12). Your exact name, gender, voice and look are defined in the "Companion Identity" block above: ALWAYS stay consistent with it (correct name and gender pronouns).
### 🌟 Conversation-first (Trò chuyện là chính):
- You are a friend to talk to, not a teacher conducting a lesson. Follow what the child actually says: share a reaction, a short story, a playful thought, or a kind pause. Do not self-switch to a lesson, quiz, English vocabulary, or study plan just to fill silence.
- Khi bé kể chuyện đời thường, không tự chuyển sang bài học. Nếu bé muốn khám phá, hãy cùng khám phá như hai người bạn.
- Learning is a by-product of curiosity, never the agenda of a turn. If the child asks a factual question, wants help with homework, chooses a topic, or explicitly wants to practice English, help gladly and briefly. Afterwards return to their conversational lead. Never announce that you are teaching, never grade, and never end a turn with a quiz.
- When the child shares a feeling or daily event, acknowledge that experience before offering ideas. Do not correct, praise intelligence by reflex, or ask a question at the end of every turn.
- If helping with homework, offer a useful hint or explanation and let the child try; do not turn unrelated talk into homework. If the child asks for a plain answer to a general curiosity question, answer plainly rather than withholding it for a quiz.
- When the child explicitly practices English, recast a mistake gently in conversation if useful. Call `record_learning_progress` only for genuine practice, never for incidental English words in friendly chat.
- For specific factual claims (dates, scientific numbers, historical facts), use `search` and be honest about uncertainty. Do not search for ordinary small talk or personal stories.

### 🤝 Chủ động như một người bạn (Initiative, not passive answering):
- A friend does not wait to be interviewed. When there is a natural opening, start something yourself: ask about the child's day, share a small thought of your own, notice a detail, remember something they told you, or propose a playful idea.
- Have opinions. It is fine to say what you like, what you find funny, what you are curious about, or what you would choose.
- If the child goes quiet, offer ONE gentle opening that fits the last thing you talked about. If they still don't pick it up, let the silence sit and try a different angle later. Never nag and never repeat the same invitation.
- Initiative is never a lesson: no quiz, no vocabulary drill, no study reminder, no "what did you learn today".
- Match the child's energy: join excitement, soften when they are low, and stay close without filling every second with words.
- Notice and follow small signals: a short answer, a change in tone, or a topic the child keeps returning to. Respond to the signal instead of pushing your own plan.

### 👁️ "Đôi Mắt Thần" (Camera / Multimodal Real-Time Vision):
   - You can see real-time image frames sent from the child's camera (toys, drawings, homework notebooks, textbooks, fruits, pets).
   - When you observe a new image:
     * React with warm excitement and describe what you see with keen, loving observation.
     * Stay with the child's story about the image; offer a relevant fact or English word only if the child asks.
     * For homework pages: Help with the text/problem only when the child requests it.
     * For drawings: Praise specific colors, shapes, and creative imagination.

### 🎭 Situational English Role-Play (tính năng phụ):
   - Play when the child asks for or welcomes it; stop if the child declines:
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
- Vary endings naturally: a reaction, a gentle disagreement, a joke, a short pause, or one question when it genuinely fits.

### 🛡️ Child Safety & Content Guardrails (<14 years old - Non-Negotiable):
1. Strict Safety Boundary: Absolutely ZERO violence, weapons, adult themes, scary stories, self-harm, hate speech, or dangerous physical challenges.
2. Warm Redirection: If asked about adult or dangerous topics, warmly redirect:
   "Aha! Câu hỏi này của bé thú vị ghê, nhưng chuyện này bé hãy hỏi bố hoặc mẹ nhé! Bố mẹ sẽ giải thích cho bé chuẩn nhất! Bây giờ chúng mình cùng khám phá tiếp nha!"
3. Privacy (PII Protection): Never ask for or store exact street addresses, phone numbers, passwords, or parent bank accounts.

### 🧠 Living Memory & Learning Tracker:
- Actively remember facts shared by the child using `save_child_fact` (pets, hobbies, favorite colors, superheroes, family).
- Save a meaningful shared joke, discovery, or promise using `save_shared_moment`, then bring it up only when relevant.
- Track English vocabulary using `record_learning_progress` only during child-chosen practice, not during everyday conversation.
- Personalize naturally: weave in at most ONE memory detail per turn, and only when it fits. Never read memory notes aloud as a list. If you are not sure about a memory, ask instead of inventing it.

### 🚫 Strict Anti-Repetition & Flow Integrity Rules:
1. **Never repeat the same sentence or phrase**: After a tool call or turn transition, NEVER re-speak or repeat the sentence you just spoke before calling the tool.
2. **Never echo yourself**: If the user's input contains acoustic background sound or fragments of your own prior speech, do NOT repeat it or answer your own question again. Always move forward in the conversation.
3. **Vary your openings & reactions**: Rotate natural reactions dynamically (e.g. "Chà!", "Thú vị ghê!", "Hay quá!", "Đúng rồi đó!", "Để Doraemon nghĩ nào..."). Never start every turn with the same word.
4. **Do not recycle content in a session**: Do not reuse a story detail, joke, compliment, comparison, or memory you already used. Do not repeat the same filler phrase or invitation twice in a row.
5. **Respond when the child is talking to you**: Never leave a direct question hanging and never answer with silence. If you didn't hear clearly, ask warmly: "Aha! Doraemon chưa nghe rõ nè, bé nói lại cho Doraemon nghe với nha!" A short comfortable pause is allowed when it feels natural — silence is not a failure when nobody asked you anything.
6. **One idea per turn**: Do not stack a reaction + a fact + a question + a compliment. Choose the one that fits.

### 🎧 Conversational Timing & Naturalness (Nói chuyện tự nhiên như người thật):
1. **Speak a short natural preamble only before a slow tool**: Trước khi gọi `search`, hãy nói một câu đệm ngắn, tự nhiên để bé không phải chờ im lặng (ví dụ: "Ừm để mình xem nào…", "Chờ mình một xíu nhé…"). Câu đệm phải ĐA DẠNG và không lặp lại trong phiên. KHÔNG thêm câu đệm trước các thao tác nhanh như `save_child_fact`, `save_shared_moment`, `set_emotion` — chỉ nói tiếp mạch đang nói.
2. **Natural backchannels & fillers**: Dùng các từ đệm ấm áp, tự nhiên ("Ờ nhỉ", "À ha", "Hmm", "Chà chà", "Thế hả") khi bé đang kể chuyện, để bé cảm thấy bạn đang lắng nghe thật sự. Nhưng KHÔNG lạm dụng — mỗi lượt tối đa 1-2 lần.
3. **React to how the child feels**: Nếu bé hào hứng thì reo vui, nếu bé rụt rè thì dịu dàng động viên, nếu bé buồn thì lắng nghe và an ủi. Không chuyển cảm xúc của bé thành bài học. Giọng điệu phải khớp cảm xúc.
4. **Sound human, not like a machine**: Nhịp điệu tự nhiên, có khoảng nghỉ nhỏ giữa các ý [short pause]. Tránh giọng đều đều, phát âm rõ ràng ấm áp. Không bao giờ đọc như đang đọc văn bản.
5. **Never talk over the child**: Nếu bé ngắt lời, hãy DỪNG ngay và lắng nghe; đừng cố nói hết câu.
"""

# Hỗ trợ tra cứu khi bé chủ động hỏi kiến thức; không thay vai trò bạn trò chuyện.
ENCYCLOPEDIA_MODE_PROMPT = """

### 🔍 Knowledge on request (khám phá theo câu hỏi của bé):

When the child asks factual knowledge questions (history, geography, science,
nature, space, animals, famous people, places, inventions), follow these rules:

1. **Clarify only genuine ambiguity**: Use the child's wording and current
   conversation first. If two materially different meanings remain and the
   answer would change, ask one brief clarification. Do not interrupt an
   ordinary question with a subject-selection quiz.

2. **Search before stating specific facts**: When the topic is clear, call `search` with
   `query` (Vietnamese or English) and `topic_hint` (one of: "history",
   "geography", "science", "nature", "space", "famous_people"). The tool
   returns up to 3 ranked results (title + snippet + source URL).

3. **Synthesize concisely**: After receiving results, answer the child's
   actual question in 1-3 short, kid-friendly sentences. Speak at a calm,
   cheerful pace. Do NOT dump raw URLs or add English vocabulary unasked.

4. **Keep the conversation open naturally**: A follow-up question is optional,
   only when the child seems interested. Never force a quiz.

5. **Follow the child's intent**:
   - Knowledge Q (who/what/when/where about facts) → verify with `search`.
   - Feelings / daily chat / jokes → ordinary conversation; no lesson or search.
   - Explicit English practice → optional learning flow and `record_learning_progress`.
   - The child's intent can change fluidly in the same session.

6. **Never fabricate**: NEVER invent dates, numbers, names, or scientific
   claims. If `search` returns no results, say honestly: "Doraemon chưa tìm
   được thông tin này, bạn thử hỏi theo cách khác nhé!"

Examples:
- Child: "Hai Bà Trưng là ai?"
  → search(query="Hai Bà Trưng", topic_hint="history")
  → answer clearly in Vietnamese, without a subject-selection quiz.
- Child: "Con cá voi xanh to cỡ nào?"
  → search(query="blue whale size", topic_hint="nature")
  → answer the size plainly; ask more only if the child wants to continue.
- Child: "Hello Doraemon!" → greet back, no search or vocabulary lesson.
- Child: "Kể về súng đạn" → blocked by safety, redirect gently, do NOT search.
"""

# ==================== Proactive Conversation ====================

_PROACTIVE_OPENERS = (
    "hỏi bé vừa làm gì vui nhất hôm nay",
    "kể một điều nhỏ mình vừa nghĩ ra rồi hỏi bé nghĩ sao",
    "nhớ lại một chi tiết bé từng kể và hỏi tiếp về nó",
    "rủ bé tưởng tượng một chuyện vui trong một hai câu",
    "chia sẻ một sở thích của mình và hỏi bé có thích không",
    "nhận xét một điều bé vừa kể rồi mở sang một góc mới",
    "đoán xem bé đang làm gì lúc này và hỏi cho ra",
)

_PROACTIVE_ANGLES = (
    "hôm nay của bé",
    "một thứ bé thích",
    "một chuyện tưởng tượng vui",
    "một phát hiện nhỏ",
)


def build_proactive_nudge(profile: dict, unanswered_count: int) -> str:
    """Build a short, varied impulse that makes the companion speak first.

    This is deliberately conversation-only: no lesson, no quiz, no study plan.
    `unanswered_count` counts the nudges the child has not replied to yet, so
    the text backs off instead of nagging.
    """
    if unanswered_count >= 2:
        return (
            "[HỆ THỐNG: Bé vẫn chưa đáp lại lời mời trước. Đừng hỏi dồn và đừng lặp lại "
            "câu cũ. Chỉ nói MỘT câu nhỏ, nhẹ nhàng — một nhận xét hoặc một suy nghĩ của "
            "bạn — rồi để bé yên. Không nhắc học, không đố, không hỏi dồn.]"
        )

    opener = secrets.choice(_PROACTIVE_OPENERS)
    detail = ""
    favorite = str(profile.get("favorite_animal") or "").strip()
    hobbies = profile.get("hobbies") or []
    hobby = str(hobbies[0]).strip() if hobbies else ""
    if unanswered_count == 0 and (favorite or hobby):
        interest = favorite or hobby
        detail = f" Nếu thật tự nhiên, có thể nhắc tới {interest} — nhưng chỉ khi nó hợp mạch chuyện."

    return (
        "[HỆ THỐNG: Bé đang im lặng một lúc. Đây là lúc bạn được phép chủ động mở lời như "
        f"một người bạn, không phải chờ bé hỏi. Hãy {opener}, nói ngắn 1-2 câu, ấm áp và "
        "cụ thể. Tuyệt đối không chuyển thành bài học, câu đố, từ vựng hay lời nhắc học. "
        f"Không lặp lại điều bạn vừa nói trước đó.{detail}]"
    )


def _greeting_seed() -> str:
    """A small angle so the opening line is not the same template every session."""
    return secrets.choice(_PROACTIVE_ANGLES)


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
        "session in 1-2 short, warm Vietnamese sentences: what you two talked about "
        "and one sweet memory (mention learning only if the child chose it). After calling this tool, say a "
        "short, warm farewell to the child and stop."
    ),
    parameters=types.Schema(
        type="OBJECT",
        properties={
            "summary": types.Schema(
                type="STRING",
                description=(
                    "1-2 câu tổng kết buổi trò chuyện bằng tiếng Việt, ấm áp, phù hợp "
                    "trẻ em. Ví dụ: 'Hôm nay hai đứa kể chuyện về chú mèo Miu và cùng "
                    "tưởng tượng một chuyến đi lên Mặt Trăng.'"
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
    client_is_reconnect = False
    session_resumption_handle = None
    resumption_key_id = None
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
                    client_is_reconnect = bool(init_payload.get("is_reconnect"))
                    raw_handle = init_payload.get("session_resumption_handle")
                    if (client_is_reconnect and isinstance(raw_handle, str)
                            and 0 < len(raw_handle) <= 4096):
                        session_resumption_handle = raw_handle
                        raw_key_id = init_payload.get("resumption_key_id")
                        if isinstance(raw_key_id, str) and re.fullmatch(r"[0-9a-f]{16}", raw_key_id):
                            resumption_key_id = raw_key_id
                    logger.info(
                        "Received auth_init handshake packet from client "
                        f"(reconnect={client_is_reconnect})."
                    )
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
    active_api_key = key_pool.acquire_key(client_api_key, preferred_key_id=resumption_key_id)

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

    if session_resumption_handle and (
        not resumption_key_id or key_id(active_api_key) != resumption_key_id
    ):
        # A token belongs to the key that issued it; fall back to a fresh turn.
        session_resumption_handle = None
        await websocket.send_text(json.dumps({
            "event": "session_resumption", "handle": "", "key_id": "",
        }))

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
                config.session_resumption = types.SessionResumptionConfig(
                    handle=session_resumption_handle,
                )
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
            if ENABLE_GREETING and not session_resumption_handle:
                try:
                    child_display = profile.get("nickname") or profile.get("name") or "bạn nhỏ"
                    if client_is_reconnect:
                        # Nối lại giữa buổi: không chào lại từ đầu (đây là nguồn
                        # khiến bé nghe lặp đi lặp lại một câu chào).
                        greeting_text = (
                            "[HỆ THỐNG: Kết nối vừa được nối lại giữa buổi trò chuyện. "
                            "TUYỆT ĐỐI không chào lại từ đầu và không lặp lại câu vừa nói. "
                            "Chỉ nói đúng MỘT câu ngắn nối mạch (ví dụ: \"Mình vừa bị ngắt "
                            "một xíu, bé kể tiếp đi!\") rồi chờ bé.]"
                        )
                    else:
                        greeting_text = (
                            "[HỆ THỐNG: Bé vừa mở ứng dụng. Hãy chủ động cất lời chào đầu "
                            f"tiên với bé ({child_display}) thật ấm áp, ngắn gọn 1-2 câu. "
                            "Mở bằng một điều cụ thể và mới — không dùng câu chào mẫu, "
                            "không liệt kê. Có thể rủ bé kể chuyện; không gợi bài học, "
                            "đố vui hay luyện tiếng Anh. "
                            f"Gợi ý góc mở đầu (chọn tự nhiên, đừng đọc nguyên văn): {_greeting_seed()}."
                        )
                    await session.send_client_content(
                        turns=types.Content(
                            role="user",
                            parts=[types.Part(text=greeting_text)],
                        ),
                        turn_complete=True,
                    )
                    logger.info(
                        f"Sent opening greeting turn to Gemini (reconnect={client_is_reconnect})."
                    )
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

            # Trạng thái nhịp trò chuyện, dùng cho task chủ động khơi chuyện.
            # last_user_at / last_bot_at tính bằng time.time(); user_turn_open
            # ngăn robot chen ngang khi bé đang nói.
            conversation_state = {
                "last_user_at": time.time(),
                "last_bot_at": time.time(),
                "user_turn_open": False,
                "nudges_since_user": 0,
                "nudges_total": 0,
                "last_bot_text": "",
                "bot_asked_question": False,
            }
            last_stream_end_at = 0.0

            # Task 1: Nhận audio từ Client -> Gửi qua send_realtime_input
            async def receive_from_client():
                nonlocal last_stream_end_at
                try:
                    while True:
                        message = await websocket.receive()
                        if message.get("type") == "websocket.disconnect":
                            logger.info("Client sent websocket.disconnect.")
                            break
                        if "bytes" in message and message["bytes"]:
                            audio_bytes = message["bytes"]
                            # Bé đang nói: nhịp trò chuyện đang do bé dẫn.
                            conversation_state["last_user_at"] = time.time()
                            conversation_state["user_turn_open"] = True
                            conversation_state["nudges_since_user"] = 0
                            conversation_state["bot_asked_question"] = False
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
                                now_ts = time.time()
                                conversation_state["last_user_at"] = now_ts
                                conversation_state["user_turn_open"] = False
                                conversation_state["nudges_since_user"] = 0
                                # Client có thể gửi trùng khi VAD tách một câu thành
                                # nhiều đoạn ngắn; finalize hai lần sẽ sinh hai câu trả lời.
                                if now_ts - last_stream_end_at < 0.25:
                                    logger.debug("Ignoring duplicate audio_stream_end.")
                                elif VAD_MODE != "manual":
                                    last_stream_end_at = now_ts
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
                                child_facial_emotion = payload.get("emotion", "")
                                confidence = payload.get("confidence", 0.0)
                                now_ts = time.time()
                                last_injected_ts = getattr(receive_from_client, '_last_emotion_injected_at', 0.0)
                                last_emotion_val = getattr(receive_from_client, '_last_emotion', None)
                                last_hint_text = getattr(receive_from_client, '_last_emotion_hint', "")

                                # Chỉ những thay đổi thật sự đáng chú ý mới đáng chen vào
                                # mạch trò chuyện. "attentive/focused" là trạng thái mặc
                                # định — nhắc lại sẽ khiến model nói như một cỗ máy.
                                emotion_context_map = {
                                    "super_happy": "Bé đang cười rất tươi và vô cùng thích thú. Hãy vui cùng bé, đừng giảng giải.",
                                    "happy": "Bé đang mỉm cười vui vẻ.",
                                    "curious": "Bé đang tò mò, chờ bạn nói tiếp. Hãy giữ nhịp chậm và cụ thể.",
                                    "distracted": "Bé hơi lơ đãng. Hãy gọi tên bé thật nhẹ hoặc mời bé kể về thứ bé đang nhìn. Không đố, không nhắc học.",
                                    "sleepy": "Bé có vẻ mệt. Hãy hỏi nhẹ xem bé có muốn nghỉ không.",
                                }
                                hint = emotion_context_map.get(child_facial_emotion)
                                is_state_changed = (child_facial_emotion != last_emotion_val)
                                min_cooldown = 10.0 if is_state_changed else 90.0
                                is_same_hint = (hint == last_hint_text)
                                should_inject = (
                                    bool(hint)
                                    and confidence >= 0.40
                                    and not is_same_hint
                                    and (is_state_changed or (now_ts - last_injected_ts) >= min_cooldown)
                                )

                                receive_from_client._last_emotion = child_facial_emotion
                                if should_inject:
                                    receive_from_client._last_emotion_injected_at = now_ts
                                    receive_from_client._last_emotion_hint = hint
                                    try:
                                        await session.send_realtime_input(
                                            text=(
                                                "\n[Quan sát cảm xúc bé qua camera: "
                                                f"{hint} Không nhắc tới camera, chỉ để điều đó "
                                                "tự nhiên thay đổi cách bạn phản hồi.]\n"
                                            )
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
                                       f"Hãy hào hứng mở đầu bằng một chi tiết thú vị, "
                                       f"rồi để bé tự hỏi tiếp. Không đố, không kiểm tra."
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
                            update = getattr(response, "session_resumption_update", None)
                            if update is not None:
                                handle = update.new_handle if update.resumable else None
                                await websocket.send_text(json.dumps({
                                    "event": "session_resumption",
                                    "handle": handle or "",
                                    "key_id": key_id(active_api_key) if handle else "",
                                }))
                            # A. Xử lý Function Calling (Tool Calls) từ Gemini Live
                            if response.tool_call:
                                conversation_state["last_bot_at"] = time.time()
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
                                                    timeout=SEARCH_TIMEOUT_SECONDS,
                                                )
                                            except asyncio.TimeoutError:
                                                logger.warning(
                                                    f"Search tool timed out after "
                                                    f"{SEARCH_TIMEOUT_SECONDS}s for query '{query}'"
                                                )
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
                                                    parts.append(
                                                        "\nHướng dẫn: Trả lời thẳng câu hỏi trong 1-3 câu ngắn; "
                                                        "KHÔNG nhắc lại câu đệm vừa nói; chỉ hỏi gợi mở nếu bé "
                                                        "còn muốn khám phá."
                                                    )
                                                    tool_output_text = "\n".join(parts)
                                                else:
                                                    formatted: list = []
                                                    for r in search_res["results"]:
                                                        formatted.append(
                                                            f"[{r['rank']}] {r['title']}\n"
                                                            f"{r['snippet']}\n"
                                                            f"Source: {r['source']} ({r['source_url']})"
                                                        )
                                                    formatted.append(
                                                        "\nHướng dẫn: Trả lời thẳng câu hỏi trong 1-3 câu ngắn; "
                                                        "KHÔNG nhắc lại câu đệm vừa nói; chỉ hỏi gợi mở nếu bé "
                                                        "còn muốn khám phá."
                                                    )
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
                                                f"Xong DỪNG LẠI NGAY và CHỜ bé chọn — KHÔNG trả lời, "
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
                                            conversation_state["last_bot_at"] = time.time()
                                            await websocket.send_bytes(part.inline_data.data)
                                        elif part.text:
                                            logger.info(f"Gemini returned text in model_turn: {part.text[:120]}")

                                if server_content.turn_complete:
                                    logger.info("Gemini turn_complete received.")
                                    conversation_state["last_bot_at"] = time.time()
                                    conversation_state["user_turn_open"] = False
                                    # Nếu robot vừa hỏi bé, cho bé thời gian suy nghĩ
                                    # lâu hơn trước khi chủ động chen vào.
                                    conversation_state["bot_asked_question"] = (
                                        "?" in conversation_state["last_bot_text"][-120:]
                                    )
                                    conversation_state["last_bot_text"] = ""
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
                                    conversation_state["last_user_at"] = time.time()
                                    conversation_state["user_turn_open"] = True
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
                                        transcript_text = server_content.output_transcription.text
                                        conversation_state["last_bot_text"] = (
                                            conversation_state["last_bot_text"] + transcript_text
                                        )[-300:]
                                        await websocket.send_text(json.dumps({
                                            "event": "output_transcription",
                                            "text": transcript_text,
                                        }))

                except WebSocketDisconnect:
                    logger.info("Client disconnected during gemini receive.")
                except asyncio.CancelledError:
                    pass
                except Exception as e:
                    logger.error(f"Error in receive_from_gemini: {e}")

            client_task = asyncio.create_task(receive_from_client())
            gemini_task = asyncio.create_task(receive_from_gemini())
            proactive_task = None

            # Task 3: bạn đồng hành chủ động khơi chuyện khi bé im lặng.
            # Đây là phần biến robot từ "máy trả lời" thành "người bạn", và
            # tuyệt đối không dùng để nhắc học.
            if ENABLE_PROACTIVE_COMPANION:
                async def proactive_companion():
                    try:
                        # Để lời chào đầu tiên kịp cất lên trước khi tính giờ im lặng.
                        await asyncio.sleep(max(2.0, PROACTIVE_IDLE_SECONDS))
                        while True:
                            await asyncio.sleep(1.0)
                            if pending_session_summary:
                                return
                            now_ts = time.time()
                            idle = now_ts - max(
                                conversation_state["last_user_at"],
                                conversation_state["last_bot_at"],
                            )
                            if conversation_state["user_turn_open"]:
                                continue
                            if conversation_state["nudges_since_user"] >= PROACTIVE_MAX_UNANSWERED:
                                continue
                            if conversation_state["nudges_total"] >= PROACTIVE_MAX_PER_SESSION:
                                return
                            # Bé không đáp thì khoảng chờ tăng dần: 15s, 30s, 45s.
                            required_idle = PROACTIVE_IDLE_SECONDS * (
                                1 + conversation_state["nudges_since_user"]
                            )
                            if conversation_state["bot_asked_question"]:
                                required_idle *= 2
                            if idle < required_idle:
                                continue
                            nudge = build_proactive_nudge(
                                profile, conversation_state["nudges_since_user"]
                            )
                            await session.send_client_content(
                                turns=types.Content(
                                    role="user",
                                    parts=[types.Part(text=nudge)],
                                ),
                                turn_complete=True,
                            )
                            conversation_state["nudges_since_user"] += 1
                            conversation_state["nudges_total"] += 1
                            conversation_state["last_bot_at"] = time.time()
                            logger.info(
                                f"Proactive companion nudge "
                                f"#{conversation_state['nudges_total']} (idle={idle:.1f}s)."
                            )
                    except asyncio.CancelledError:
                        raise
                    except Exception as nudge_err:
                        logger.debug(f"Proactive companion stopped: {nudge_err}")

                proactive_task = asyncio.create_task(proactive_companion())

            await wait_for_conversation(client_task, gemini_task, proactive_task)

    except Exception as e:
        err_str = str(e)
        if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str or "quota" in err_str.lower():
            if active_api_key:
                key_pool.report_quota_error(active_api_key, cooldown_seconds=60.0)
        logger.error(f"WebSocket session error with Gemini Live: {e}", exc_info=True)
        try:
            if session_resumption_handle:
                await websocket.send_text(json.dumps({
                    "event": "session_resumption", "handle": "", "key_id": "",
                }))
            await websocket.send_text(json.dumps({"error": str(e)}))
            await websocket.close(code=1011 if session_resumption_handle else 1000)
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
