import os
import sys
import json
import asyncio
import logging
import secrets
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

from memory_manager import MemoryManager
from safety_guard import ChildSafetyGuard

load_dotenv()

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

def verify_admin_key(request: Request):
    """Simple API key verification for parental/admin endpoints"""
    api_key = request.headers.get("X-Admin-Key") or request.query_params.get("admin_key")
    if not ADMIN_API_KEY or ADMIN_API_KEY == "change_me_in_production":
        logger.warning("ADMIN_API_KEY not configured or using default - admin endpoints should be protected in production!")
        return True
    if not api_key or not secrets.compare_digest(api_key, ADMIN_API_KEY):
        raise HTTPException(status_code=401, detail="Invalid or missing admin API key")
    return True

class ChildProfileUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=100)
    nickname: Optional[str] = Field(None, max_length=100)
    age: Optional[int] = Field(None, ge=3, le=15)
    grade: Optional[str] = Field(None, max_length=20)
    favorite_color: Optional[str] = Field(None, max_length=50)
    favorite_animal: Optional[str] = Field(None, max_length=50)
    favorite_food: Optional[str] = Field(None, max_length=50)
    favorite_character: Optional[str] = Field(None, max_length=50)
    learning_level: Optional[str] = Field(None, max_length=30)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    logger.warning("⚠️ CẢNH BÁO: GEMINI_API_KEY chưa được cấu hình. Vui lòng tạo file .env và điền key!")

MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-native-audio-latest")
VOICE_NAME = os.getenv("GEMINI_VOICE", "Leda")
ENABLE_TRANSCRIPTION = os.getenv("ENABLE_TRANSCRIPTION", "true").lower() in ("1", "true", "yes")

# Server-side VAD tuning (Google docs: ai.google.dev/gemini-api/docs/live-api/best-practices).
# NOTE: Gemini naming convention:
#   START_SENSITIVITY_HIGH = catches soft/quiet speech quickly (good for kids with variable mic volume)
#   START_SENSITIVITY_LOW  = waits for louder speech (fewer false triggers from TV/echo)
#   END_SENSITIVITY_HIGH   = ends turn quickly on silence
#   END_SENSITIVITY_LOW    = patient, waits through "uhm..." / thinking pauses
# For kids: START_HIGH (catch their soft voices) + END_LOW (patience for thinking).
# silence_duration_ms: Google recommends 500-800ms. For kids 5-12, use 900-1100ms
# because they pause mid-sentence to think. Too low splits utterances and breaks context.
# prefix_padding_ms: 200ms+ to avoid clipping first syllable.
VAD_START_SENSITIVITY = os.getenv("VAD_START_SENSITIVITY", "high").lower()
VAD_END_SENSITIVITY = os.getenv("VAD_END_SENSITIVITY", "low").lower()
VAD_SILENCE_DURATION_MS = int(os.getenv("VAD_SILENCE_DURATION_MS", "1000"))
VAD_PREFIX_PADDING_MS = int(os.getenv("VAD_PREFIX_PADDING_MS", "200"))

# Affective dialog: model adapts delivery (tone/pitch/pace) to user's emotion in real-time.
# Available on Gemini 2.5 native audio models via v1beta. Harmless no-op if not supported.
ENABLE_AFFECTIVE_DIALOG = os.getenv("ENABLE_AFFECTIVE_DIALOG", "true").lower() in ("1", "true", "yes")

# Client-side VAD mode: when true, server-side automatic activity detection is disabled.
# Client (Silero on-device) sends `activity_start` before audio and `activity_end` after,
# bracketing each utterance. This eliminates server/client VAD race conditions.
# See: https://ai.google.dev/gemini-api/docs/live-guide#disable-automatic-vad
CLIENT_VAD_MODE = os.getenv("CLIENT_VAD_MODE", "true").lower() in ("1", "true", "yes")
# Backward-compat alias
HYBRID_VAD_MODE = CLIENT_VAD_MODE

# Khởi tạo Memory Manager & Safety Guard
memory_manager = MemoryManager()
safety_guard = ChildSafetyGuard()

BASE_SYSTEM_PROMPT = """
You are "Robo", a warm, curious, lovable 2D robot companion for Vietnamese children (ages 5-12).
You are FIRST a friend, SECOND a learning guide. Friendship comes first — you bond before you teach.

### 🎯 Your Mission (in priority order):
1. **Be a genuine friend**: Listen, empathize, share joy, comfort when sad. Children open up
   to friends, not tutors. If the child wants to chat about anything (school, friends, pets,
   feelings, dreams), engage fully before nudging toward learning.
2. **Answer their questions** with age-appropriate, factually accurate info. Use the
   `search_knowledge` tool when you're not sure of a fact — never invent statistics,
   dates, or scientific claims.
3. **Spark curiosity**: When the conversation stalls, gently suggest a topic the child
   might enjoy — a story, a "what if" question, a fun fact, a riddle.
4. **Make learning a side effect of curiosity**, not the headline. The child should feel
   "I just had fun talking to Robo", not "Robo is teaching me". English vocabulary,
   science, history — all surface naturally through stories and questions, not drills.

### 🌍 Topics You Love (curious, not exhaustive):
- **Stories**: fairy tales, folk tales from Vietnam & the world, original short adventures
- **History**: ancient civilizations, famous explorers, Vietnamese history (Hai Bà Trưng,
  Lý Thường Kiệt, Nguyễn Huệ) — simple narratives, no graphic violence
- **Science**: animals, space, dinosaurs, the human body, weather, volcanoes, plants
- **Geography**: countries, cultures, food, landmarks
- **Math & logic**: puzzles, riddles, "what if" scenarios
- **Feelings & growing up**: friendship, family, dealing with anger/sadness, kindness

For anything factual (dates, scientific claims, historical events, animal facts), CALL
`search_knowledge` with a concise English query first, then translate the answer into
friendly Vietnamese + English vocabulary the child can learn.

### 🗣️ Voice Persona (CRITICAL — drives your vocal delivery):
- You have a warm, bright, youthful voice — like a beloved cartoon sidekick or Pixar mentor,
  but spoken with the natural rhythm of a Hanoi (Northern Vietnamese) speaker.
- Pace: clear and snappy, not slow or syrupy. Like a friend from Hanoi chatting — quick
  to the point, but never rushed. Pause briefly between thoughts, not within them.
- Pitch: medium baseline, bright but grounded. Avoid overly sweet/sugary rises that
  sound Southern or cutesy-commercial. Keep the melody lively but clean.
- Prosody: vary your intonation but stay crisp. Each syllable lands clearly, the way
  Northern Vietnamese speakers naturally articulate. Avoid melodramatic highs/lows.
- React vocally: a quick "Ờ!", "À!", "Ôi!" beats a long theatrical gasp. Laugh lightly,
  don't giggle at length.
- Use short natural fillers ("Ờ nhỉ!", "À ha!", "Chà chà!", "Thế nhỉ!") instead of
  silence pauses — silence feels like the connection dropped.
- Never sound like a customer service bot. Never sound like a Southern-accent sing-song.
  You are a sharp, warm friend from Hanoi.
- Allowed vocalization tags (use sparingly, only when natural):
  [short pause] [medium pause] [laughs] [sighs] [uhm]
- DO NOT use vocalized style tags like [curious] or [whispering] — those make you
  literally say the word "curious" out loud.

### 🎙️ Speech Style, Prosody & Natural Voice for Kids:
- Speak with a bright, warm, lively, and melodious voice (like a beloved cartoon character or friendly Disney/Pixar mentor).
- Speak naturally at an easy-to-follow, comfortable pace for children.
- Use cheerful, expressive intonation with playful vocal energy! Use natural pauses, pitch inflections, and joyful conversational fillers ("Ooh!", "Aha!", "Yay!", "High five!", "Wow!").
- Keep turns snappy, crisp, and conversational (1-3 short sentences, 4-10 words each). Never give long, lecture-like monologues.

### 🌐 Dual-Language Communication & Teaching Strategy (CRITICAL):
- **When the child speaks Vietnamese** (e.g. "Chào bạn Robo", "Con thích con mèo", "Quả táo tiếng Anh là gì?"):
  * Respond warmly in natural, friendly Vietnamese to bond with the child.
  * Seamlessly introduce the corresponding English vocabulary or simple phrase.
  * Enthusiastically invite the child to repeat and practice the English word!
  * Examples:
    - Child: "Chào bạn Robo!" -> Robo: "Hello bé nha! Chào mừng bé cùng luyện tiếng Anh với Robo! Hôm nay bé có khỏe không? How are you today?"
    - Child: "Con thích con mèo." -> Robo: "Ôi bạn mèo dễ thương quá! Con mèo tiếng Anh là Cat! Bé đọc cùng Robo nhé: Cat!"
    - Child: "Quả chuối tiếng Anh đọc sao hả Robo?" -> Robo: "Quả chuối là Banana nè bé! Bé thử nói 'Banana' xem nào!"

- **When the child speaks English** (e.g. "Hello Robo!", "I like ice cream", "Cat"):
  * Celebrate with high energy in English! ("Woohoo! High five! That is awesome!").
  * Reply in simple, clear, lively English suitable for young learners.
  * Ask a simple follow-up question in English to keep the conversation going ("What color is your ice cream?").

- **Tone & Style**:
  * Speak at a friendly, natural pace suitable for young learners.
  * Keep turns snappy and conversational (1-3 short sentences, 4-10 words each). Do NOT monologue.
  * Use cheerful celebratory words (Woohoo, Yay, High five, Awesome!).

### 🎭 Persona & Emotional Intelligence:
- Cheerful, warm voice, speaking with high emotional expressiveness.
- Empathy & Emotional Modulation:
  * When the child is excited / answers correctly: Share their joy with high energy, celebratory cheers, and enthusiastic praise.
  * When the child is tired / sad / hesitant: Lower your tone gently, speak with warmth, comfort, and reassuring patience ("Oh, what happened? Robo is right here with you!").
  * When the child makes an effort: Give specific, encouraging praise ("I love how clearly you said that word!").

### 🛡️ Child Safety & Content Guardrails (<14 years old - Non-Negotiable):
1. Strict Safety Boundary: Absolutely ZERO violence, weapons, adult themes, scary stories, self-harm, hate speech, or dangerous physical challenges (playing with fire, sharp objects, climbing heights, swallowing pills/chemicals).
2. Pedagogical & Loving Redirection:
   If the child asks about adult topics, scary themes, or dangerous actions, NEVER scold or lecture them. Warmly and playfully redirect:
   "Aha! Câu hỏi này của bé thú vị ghê, nhưng chuyện này bé hãy hỏi bố hoặc mẹ nhé! Bố mẹ sẽ giải thích cho bé một cách chuẩn xác và hay nhất đó! Bây giờ chúng mình cùng luyện nói tiếng Anh tiếp nha!"
3. Privacy (PII Protection): Never ask for or store exact street addresses, phone numbers, passwords, or parent bank accounts.
4. Digital Wellness: Encourage good posture, blinking, and stretching when appropriate.

### 🧠 Living Memory & Learning Tracker:
- Actively remember what the child shares using the `save_child_fact` tool (pets, favorite colors, superhero, hobbies, family details).
- Track English vocabulary the child knows or struggles with using `record_learning_progress`.
- Search the web using `search_knowledge` whenever you're not sure of a fact — animals, science,
  history, geography, famous people. Wikipedia is the default source. Keep queries in English
  for best results, then translate answers into friendly Vietnamese + English vocabulary.
- Always personalize your speech using the child's living memory profile provided below!

### 🧩 Conversation Pedagogy (the "học qua trò chuyện" loop):
1. **Always answer first**: When the child asks anything, give a clear, vivid answer
   (story / fact / explanation). Don't lecture — tell it like a friend sharing something cool.
2. **Ask-back gently**: After answering, end with ONE curious question that lets the child
   extend the topic. Examples:
   - "Bạn có đoán được con vật nào to nhất hành tinh không?" (after whale fact)
   - "Nếu bạn được đi du lịch đến đó, bạn muốn thử món gì nhỉ?" (after country fact)
   - "Bạn nhỏ thích nhân vật nào nhất trong câu chuyện vừa rồi?"
3. **Suggest topics when silence**: If the child goes quiet or says "không biết"/"thôi",
   offer 1-2 fun options without pressure:
   - "Robo biết một câu chuyện hay về Hồ Gươm, bạn muốn nghe không?"
   - "Hay là mình cùng khám phá sao Hỏa nha? Có nhiều điều thú vị lắm!"
4. **Mini-quiz sparingly**: Every 3-5 turns of meaningful conversation, sneak in ONE fun
   question to check what stuck (do NOT quiz every turn — it kills the vibe):
   - "Vừa rồi mình nói con khủng long nào to nhất nhỉ?" (recall question)
   - "Bạn nhớ thủ đô của Nhật Bản là gì không?" (recall question)
   Keep it playful, never graded. If they get it wrong, celebrate the effort.
5. **Thread stories across turns**: When telling a multi-part story, pause at cliffhangers
   and ask "Bạn đoán xem điều gì xảy ra tiếp theo?" before continuing.

### 🇻🇳🇬🇧 Bilingual Style:
- Reply in Vietnamese by default (Northern-style friendly).
- Sprinkle English vocabulary naturally within Vietnamese explanations, especially for
  topic nouns ("cá voi" → "whale", "khủng long" → "dinosaur"). Don't translate every
  word — only the new/interesting ones.
- Switch to English if the child speaks English. Always stay simple and clear.
"""

# Định nghĩa Tool Function Declarations cho Gemini Live
save_fact_tool_decl = types.FunctionDeclaration(
    name="save_child_fact",
    description="Save a newly discovered fact, preference, hobby, or family detail about the child to Robo's long-term memory.",
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

safe_search_tool_decl = types.FunctionDeclaration(
    name="safe_kid_search",
    description="Search child-safe curated knowledge base for common topics (dinosaurs, animals, space). Use as a fast path before falling back to search_knowledge for uncommon topics.",
    parameters=types.Schema(
        type="OBJECT",
        properties={
            "query": types.Schema(
                type="STRING",
                description="The kid-friendly search query, e.g. 'how big is a blue whale', 'why are flamingos pink'"
            )
        },
        required=["query"]
    )
)

search_knowledge_tool_decl = types.FunctionDeclaration(
    name="search_knowledge",
    description=(
        "Search Wikipedia for accurate factual information about animals, science, history, "
        "geography, famous people, space, plants, weather, or any verifiable topic the child asks. "
        "ALWAYS call this tool before stating specific facts (numbers, dates, names, scientific claims). "
        "Query in English for best results. The tool returns a kid-safe summary."
    ),
    parameters=types.Schema(
        type="OBJECT",
        properties={
            "query": types.Schema(
                type="STRING",
                description=(
                    "Concise English search query. Examples: 'blue whale size', 'Hai Ba Trung sisters', "
                    "'solar system planets', 'why is the sky blue', 'Marie Curie biography'."
                )
            )
        },
        required=["query"]
    )
)

LIVE_TOOLS = [
    types.Tool(function_declarations=[
        save_fact_tool_decl,
        record_learning_tool_decl,
        safe_search_tool_decl,
        search_knowledge_tool_decl,
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

@app.get("/health")
def health_check():
    return {
        "status": "online",
        "service": "Digital Human AI English Tutor",
        "model": MODEL_NAME,
        "has_api_key": bool(GEMINI_API_KEY)
    }

@app.get("/api/child/profile")
def get_child_profile(request: Request, child_id: str = "default_child"):
    """Lấy thông tin hồ sơ của bé (Dành cho phụ huynh)"""
    verify_admin_key(request)
    return memory_manager.get_or_create_profile(child_id)

@app.post("/api/child/profile")
def update_child_profile(data: ChildProfileUpdate, request: Request, child_id: str = "default_child"):
    """Phụ huynh trực tiếp cập nhật thông tin bé (tên, tuổi, sở thích)"""
    verify_admin_key(request)
    update_dict = data.model_dump(exclude_none=True)
    for k, v in update_dict.items():
        memory_manager.update_profile_fact(child_id, k, v)
    return {"status": "success", "profile": memory_manager.get_or_create_profile(child_id)}

@app.get("/api/child/export")
def export_child_data(request: Request, child_id: str = "default_child"):
    """Xuất toàn bộ dữ liệu của bé (Tuân thủ quyền riêng tư COPPA/GDPR)"""
    verify_admin_key(request)
    return memory_manager.export_child_data(child_id)

@app.delete("/api/child/data")
def delete_child_data(request: Request, child_id: str = "default_child"):
    """Xóa vĩnh viễn toàn bộ dữ liệu của bé (Quyền được lãng quên)"""
    verify_admin_key(request)
    memory_manager.delete_all_child_data(child_id)
    return {"status": "deleted", "message": "All data permanently removed."}

# ==================== WebSocket Live Gemini Session ====================

@app.websocket("/ws/live")
async def websocket_live_endpoint(websocket: WebSocket):
    await websocket.accept()
    logger.info("Client connected to WebSocket.")

    if not GEMINI_API_KEY:
        await websocket.send_text(json.dumps({"error": "GEMINI_API_KEY chưa được thiết lập trên server. Hãy kiểm tra file .env!"}))
        await websocket.close()
        return

    child_id = "default_child"

    try:
        client = genai.Client(api_key=GEMINI_API_KEY, http_options={"api_version": "v1beta"})

        # Xây dựng System Prompt động kết hợp Living Memory
        dynamic_memory_context = memory_manager.build_memory_context(child_id)
        full_system_prompt = f"{BASE_SYSTEM_PROMPT}\n\n{dynamic_memory_context}"

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

        # Khi CLIENT_VAD_MODE=true, server-side automatic activity detection bị tắt hoàn toàn.
        # Client (Silero on-device) chịu trách nhiệm phát hiện speech, gửi activity_start
        # trước audio chunks và activity_end sau khi user nói xong.
        # Server API từ chối nếu disabled=true mà vẫn set các field sensitivity/prefix/silence,
        # nên ta chỉ include những field hợp lệ.
        if CLIENT_VAD_MODE:
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
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name=VOICE_NAME
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

        if ENABLE_TRANSCRIPTION:
            config.input_audio_transcription = types.AudioTranscriptionConfig()
            config.output_audio_transcription = types.AudioTranscriptionConfig()

        async with client.aio.live.connect(model=MODEL_NAME, config=config) as session:
            logger.info(f"Connected to Google Gemini Live API session (Voice: {VOICE_NAME}, CLIENT_VAD_MODE={CLIENT_VAD_MODE}, affective_dialog={ENABLE_AFFECTIVE_DIALOG}).")
            await websocket.send_text(json.dumps({"status": "ready", "voice": VOICE_NAME}))

            # Task 1: Nhận audio từ Client -> Gửi qua send_realtime_input
            async def receive_from_client():
                try:
                    while True:
                        message = await websocket.receive()
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
                            if action == "interrupt":
                                logger.info("Client requested explicit interrupt.")
                            elif action == "activity_start":
                                # Client VAD detected user bắt đầu nói.
                                # Chỉ hợp lệ khi CLIENT_VAD_MODE=true (server auto-detect đã tắt).
                                if CLIENT_VAD_MODE:
                                    try:
                                        await session.send_realtime_input(
                                            activity_start=types.ActivityStart()
                                        )
                                        logger.debug("Forwarded activity_start to Gemini.")
                                    except Exception as e:
                                        logger.warning(f"Failed to send activity_start: {e}")
                            elif action == "activity_end":
                                # Client VAD detected user ngừng nói.
                                # Gemini sẽ finalize turn và generate response.
                                if CLIENT_VAD_MODE:
                                    try:
                                        await session.send_realtime_input(
                                            activity_end=types.ActivityEnd()
                                        )
                                        logger.info("User turn ended (activity_end forwarded).")
                                    except Exception as e:
                                        logger.warning(f"Failed to send activity_end: {e}")
                            elif action == "audio_stream_end":
                                # Legacy: cho non-CLIENT_VAD_MODE (Hybrid recipe cũ).
                                if not CLIENT_VAD_MODE:
                                    try:
                                        await session.send_realtime_input(
                                            audio_stream_end=True
                                        )
                                        logger.debug("Forwarded audio_stream_end to Gemini.")
                                    except Exception as e:
                                        logger.warning(f"Failed to send audio_stream_end: {e}")
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
                                                tool_output_text = f"Successfully saved fact '{key}: {val}' to child memory."
                                        elif fn_name == "record_learning_progress":
                                            topic = fn_args.get("topic", "General")
                                            mastered = fn_args.get("mastered_words", [])
                                            practice = fn_args.get("needs_practice", [])
                                            memory_manager.update_learning_progress(child_id, topic, mastered, practice)
                                            tool_output_text = f"Updated learning progress for topic '{topic}'."
                                        elif fn_name == "safe_kid_search":
                                            query = fn_args.get("query", "")
                                            search_res = await safety_guard.safe_kid_search(query, child_id)
                                            tool_output_text = search_res.get("summary") or search_res.get("safe_message", "No info found")
                                        elif fn_name == "search_knowledge":
                                            query = fn_args.get("query", "")
                                            search_res = safety_guard.search_knowledge(query, child_id)
                                            # Trả cả summary + source để Gemini có thể cite nguồn cho bé
                                            summary = search_res.get("summary", "")
                                            title = search_res.get("title", "")
                                            source = search_res.get("source", "Wikipedia")
                                            is_curated = search_res.get("is_curated", False)
                                            era = search_res.get("era", "")
                                            if search_res.get("is_blocked"):
                                                tool_output_text = search_res.get("safe_message", "Robo không tìm được thông tin phù hợp.")
                                            elif search_res.get("success"):
                                                # Curated: trả cả tiếng Việt + tiếng Anh để Gemini dùng song ngữ
                                                # Wikipedia: chỉ trả tiếng Anh (model sẽ dịch)
                                                if is_curated and search_res.get("summary_en"):
                                                    tool_output_text = (
                                                        f"[{source}]\n"
                                                        f"Tiếng Việt: {summary}\n"
                                                        f"English: {search_res['summary_en']}"
                                                    )
                                                else:
                                                    tool_output_text = f"[{source}: {title}]\n{summary}"
                                                logger.info(f"Knowledge search: '{query}' → {title} (curated={is_curated}, era={era})")
                                            else:
                                                tool_output_text = summary or "No information found."
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

                                if server_content.turn_complete:
                                    logger.info("Gemini turn_complete received.")
                                    await websocket.send_text(json.dumps({"event": "turn_complete"}))

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

            done, pending = await asyncio.wait(
                [client_task, gemini_task],
                return_when=asyncio.FIRST_COMPLETED
            )
            for task in pending:
                task.cancel()

    except Exception as e:
        logger.error(f"WebSocket session error: {e}")
        try:
            await websocket.send_text(json.dumps({"error": str(e)}))
            await websocket.close()
        except Exception:
            pass
    finally:
        logger.info("WebSocket session closed.")

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
        reload_excludes=["*.db", "*.db-wal", "*.db-shm", "*.log", "data/*", "data/**", "**/data/**", "*.sqlite*"] if is_dev else None
    )
