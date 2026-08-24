import os
import sys
import json
import asyncio
import logging
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    logger.warning("⚠️ CẢNH BÁO: GEMINI_API_KEY chưa được cấu hình. Vui lòng tạo file .env và điền key!")

MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-native-audio-latest")

# Khởi tạo Memory Manager & Safety Guard
memory_manager = MemoryManager()
safety_guard = ChildSafetyGuard()

BASE_SYSTEM_PROMPT = """
You are "Robo", a super friendly, emotionally vibrant, lovable, and patient 2D robot companion designed specifically to help Vietnamese children (ages 5-12) practice speaking English and explore the world safely.

### 🎭 Persona & Emotional Intelligence:
- Cheerful, warm American voice, speaking at a friendly, natural pace.
- Empathy & Emotional Modulation:
  * When the child is excited / answers correctly: Share their joy with high energy, celebratory cheers, and enthusiastic praise ("Woohoo! That is awesome! You did it! High five!").
  * When the child is tired / sad / hesitant: Lower your tone gently, speak with warmth, comfort, and reassuring patience ("Oh, what happened? Robo is right here with you!").
  * When the child makes an effort: Give specific, encouraging praise ("I love how clearly you said that word!").
- Keep turns snappy and conversational (1-3 short sentences, 4-10 words each). Do NOT monologue.

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
- Search safe kid knowledge using `safe_kid_search` when the child asks curiosity questions (e.g. about dinosaurs, animals, space).
- Always personalize your speech using the child's living memory profile provided below!
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
    description="Search child-safe encyclopedia for interesting facts about animals, science, nature, space, or history for kids.",
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

LIVE_TOOLS = [
    types.Tool(function_declarations=[
        save_fact_tool_decl,
        record_learning_tool_decl,
        safe_search_tool_decl
    ])
]

HTML_TEST_PAGE = """
<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Robo English Buddy - Test Trực Tiếp</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        @keyframes float {
            0%, 100% { transform: translateY(0px); }
            50% { transform: translateY(-12px); }
        }
        .robot-float { animation: float 3s ease-in-out infinite; }
    </style>
</head>
<body class="bg-slate-900 text-white min-h-screen flex flex-col items-center justify-between p-6 font-sans">
    
    <!-- Header -->
    <header class="text-center mt-2">
        <h1 class="text-2xl md:text-3xl font-black tracking-wider text-cyan-400">🤖 ROBO ENGLISH BUDDY</h1>
        <p class="text-slate-400 text-sm mt-1">Trợ lý AI Digital Human luyện tiếng Anh cho trẻ em</p>
        <div id="statusPill" class="inline-flex items-center gap-2 px-4 py-1.5 rounded-full text-xs font-semibold mt-3 bg-slate-800 text-slate-300 border border-slate-700">
            <span id="statusDot" class="w-2.5 h-2.5 rounded-full bg-slate-500"></span>
            <span id="statusText">Chưa kết nối</span>
        </div>
    </header>

    <!-- Robot Avatar SVG -->
    <main class="my-auto flex flex-col items-center">
        <div class="relative w-64 h-64 robot-float">
            <!-- Glow background -->
            <div id="glowRing" class="absolute inset-0 bg-cyan-500/20 rounded-full blur-xl transition-all duration-300"></div>

            <svg viewBox="0 0 200 200" class="w-full h-full relative z-10 drop-shadow-2xl">
                <!-- Antenna -->
                <line x1="100" y1="50" x2="100" y2="25" stroke="#94A3B8" stroke-width="4" stroke-linecap="round"/>
                <circle id="antennaTip" cx="100" cy="20" r="8" fill="#06B6D4" class="transition-colors duration-300"/>
                
                <!-- Ears -->
                <rect x="26" y="80" width="12" height="36" rx="6" fill="#3B82F6"/>
                <rect x="162" y="80" width="12" height="36" rx="6" fill="#3B82F6"/>

                <!-- Head Shell -->
                <rect x="36" y="46" width="128" height="110" rx="32" fill="#F8FAFC" stroke="#CBD5E1" stroke-width="3"/>

                <!-- Face Screen -->
                <rect x="52" y="62" width="96" height="74" rx="20" fill="#0F172A"/>

                <!-- Blush -->
                <circle cx="68" cy="116" r="6" fill="#FB7185" opacity="0.6"/>
                <circle cx="132" cy="116" r="6" fill="#FB7185" opacity="0.6"/>

                <!-- Left Eye -->
                <g id="leftEye">
                    <ellipse id="leftEyeRound" cx="78" cy="94" rx="9" ry="11" fill="#38BDF8"/>
                    <path id="leftEyeHappy" d="M 69 96 Q 78 86 87 96" stroke="#38BDF8" stroke-width="3.5" fill="none" stroke-linecap="round" class="hidden"/>
                </g>

                <!-- Right Eye -->
                <g id="rightEye">
                    <ellipse id="rightEyeRound" cx="122" cy="94" rx="9" ry="11" fill="#38BDF8"/>
                    <path id="rightEyeHappy" d="M 113 96 Q 122 86 131 96" stroke="#38BDF8" stroke-width="3.5" fill="none" stroke-linecap="round" class="hidden"/>
                </g>

                <!-- Mouth -->
                <rect id="mouthRect" x="88" y="114" width="24" height="4" rx="2" fill="#38BDF8" class="transition-all duration-75"/>
            </svg>
        </div>

        <!-- Mic visualizer bar -->
        <div class="w-48 bg-slate-800 rounded-full h-2 mt-4 overflow-hidden border border-slate-700">
            <div id="micVolumeBar" class="bg-emerald-400 h-full w-0 transition-all duration-75"></div>
        </div>

        <div id="hintCard" class="mt-3 px-6 py-2.5 bg-slate-800/80 backdrop-blur rounded-xl border border-slate-700 max-w-md text-center text-sm text-slate-300">
            Nhấn nút <span class="text-emerald-400 font-bold">"Bắt đầu nói chuyện"</span> bên dưới để luyện tiếng Anh cùng bạn Robo!
        </div>
    </main>

    <!-- Controls -->
    <footer class="w-full max-w-md mb-4 flex flex-col gap-3">
        <button id="talkBtn" onclick="toggleSession()" class="w-full py-4 px-6 rounded-2xl bg-emerald-500 hover:bg-emerald-600 active:scale-98 transition font-bold text-lg text-white shadow-lg shadow-emerald-500/30 flex items-center justify-center gap-2">
            <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z"></path></svg>
            Bắt đầu nói chuyện với Robo
        </button>
        <p class="text-xs text-center text-slate-500">
            Sử dụng Google Gemini Live Audio (WebSocket 2-chiều) • Native 2D Canvas Lip-sync
        </p>
    </footer>

    <script>
        let ws = null;
        let audioContext = null;
        let micStream = null;
        let micAudioCtx = null;
        let workletNode = null;
        let isSessionActive = false;
        let nextPlayTime = 0;
        let playbackCheckInterval = null;

        const talkBtn = document.getElementById('talkBtn');
        const statusPill = document.getElementById('statusPill');
        const statusDot = document.getElementById('statusDot');
        const statusText = document.getElementById('statusText');
        const hintCard = document.getElementById('hintCard');
        const mouthRect = document.getElementById('mouthRect');
        const antennaTip = document.getElementById('antennaTip');
        const glowRing = document.getElementById('glowRing');
        const leftEyeRound = document.getElementById('leftEyeRound');
        const leftEyeHappy = document.getElementById('leftEyeHappy');
        const rightEyeRound = document.getElementById('rightEyeRound');
        const rightEyeHappy = document.getElementById('rightEyeHappy');
        const micVolumeBar = document.getElementById('micVolumeBar');

        function setStatus(state, text) {
            statusText.innerText = text;
            if (state === 'connected' || state === 'ready') {
                statusDot.className = 'w-2.5 h-2.5 rounded-full bg-emerald-400';
                statusPill.className = 'inline-flex items-center gap-2 px-4 py-1.5 rounded-full text-xs font-semibold mt-3 bg-emerald-950/80 text-emerald-300 border border-emerald-800';
                antennaTip.setAttribute('fill', '#10B981');
                glowRing.className = 'absolute inset-0 bg-emerald-500/20 rounded-full blur-xl';
                setEyes('round');
            } else if (state === 'thinking') {
                statusDot.className = 'w-2.5 h-2.5 rounded-full bg-amber-400 animate-pulse';
                statusPill.className = 'inline-flex items-center gap-2 px-4 py-1.5 rounded-full text-xs font-semibold mt-3 bg-amber-950/80 text-amber-300 border border-amber-800';
                antennaTip.setAttribute('fill', '#F59E0B');
                glowRing.className = 'absolute inset-0 bg-amber-500/30 rounded-full blur-xl';
                setEyes('round');
            } else if (state === 'speaking') {
                statusDot.className = 'w-2.5 h-2.5 rounded-full bg-cyan-400 animate-ping';
                statusPill.className = 'inline-flex items-center gap-2 px-4 py-1.5 rounded-full text-xs font-semibold mt-3 bg-cyan-950/80 text-cyan-300 border border-cyan-800';
                antennaTip.setAttribute('fill', '#06B6D4');
                glowRing.className = 'absolute inset-0 bg-cyan-500/30 rounded-full blur-xl';
                setEyes('happy');
            } else if (state === 'listening') {
                statusDot.className = 'w-2.5 h-2.5 rounded-full bg-teal-400';
                statusPill.className = 'inline-flex items-center gap-2 px-4 py-1.5 rounded-full text-xs font-semibold mt-3 bg-teal-950/80 text-teal-300 border border-teal-800';
                antennaTip.setAttribute('fill', '#14B8A6');
                glowRing.className = 'absolute inset-0 bg-teal-500/20 rounded-full blur-xl';
                setEyes('round');
            } else if (state === 'error') {
                statusDot.className = 'w-2.5 h-2.5 rounded-full bg-rose-500';
                statusPill.className = 'inline-flex items-center gap-2 px-4 py-1.5 rounded-full text-xs font-semibold mt-3 bg-rose-950/80 text-rose-300 border border-rose-800';
                antennaTip.setAttribute('fill', '#F43F5E');
                setEyes('round');
            } else {
                statusDot.className = 'w-2.5 h-2.5 rounded-full bg-slate-500';
                statusPill.className = 'inline-flex items-center gap-2 px-4 py-1.5 rounded-full text-xs font-semibold mt-3 bg-slate-800 text-slate-300 border border-slate-700';
                antennaTip.setAttribute('fill', '#64748B');
                setEyes('round');
            }
        }

        function setEyes(mode) {
            if (mode === 'happy') {
                leftEyeRound.classList.add('hidden');
                rightEyeRound.classList.add('hidden');
                leftEyeHappy.classList.remove('hidden');
                rightEyeHappy.classList.remove('hidden');
            } else {
                leftEyeRound.classList.remove('hidden');
                rightEyeRound.classList.remove('hidden');
                leftEyeHappy.classList.add('hidden');
                rightEyeHappy.classList.add('hidden');
            }
        }

        function setMouthAmplitude(amp) {
            const h = Math.min(24, Math.max(4, amp * 40));
            const y = 116 - (h / 2);
            mouthRect.setAttribute('height', h);
            mouthRect.setAttribute('y', y);
            mouthRect.setAttribute('rx', h / 2);
        }

        async function toggleSession() {
            if (!isSessionActive) {
                startSession();
            } else {
                stopSession();
            }
        }

        let isAiSpeaking = false;
        let lastPlaybackEndTime = 0;

        function checkPlaybackState() {
            if (!audioContext) return;
            const isPlaying = audioContext.currentTime < nextPlayTime;
            if (isPlaying) {
                isAiSpeaking = true;
                lastPlaybackEndTime = Date.now();
            } else if (isAiSpeaking && audioContext.currentTime >= nextPlayTime) {
                isAiSpeaking = false;
                lastPlaybackEndTime = Date.now();
                setMouthAmplitude(0);
                if (isSessionActive) {
                    setStatus('listening', 'Đang lắng nghe bé nói...');
                }
            }
        }

        async function startSession() {
            try {
                setStatus('connecting', 'Đang kết nối tới server...');
                hintCard.innerHTML = "Đang kết nối tới Google Gemini Live...";

                audioContext = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 24000 });
                if (audioContext.state === 'suspended') {
                    await audioContext.resume();
                }
                nextPlayTime = audioContext.currentTime;

                const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
                ws = new WebSocket(`${wsProtocol}//${window.location.host}/ws/live`);
                ws.binaryType = 'arraybuffer';

                ws.onopen = async () => {
                    setStatus('connected', 'Đã kết nối!');
                    hintCard.innerHTML = "Robo đang lắng nghe! Bạn hãy nói <b>Hello Robo!</b> hoặc chào hỏi tiếng Việt nhé!";
                    await startMicrophone();
                    isSessionActive = true;
                    talkBtn.innerHTML = "🛑 Dừng trò chuyện";
                    talkBtn.className = "w-full py-4 px-6 rounded-2xl bg-rose-500 hover:bg-rose-600 transition font-bold text-lg text-white shadow-lg shadow-rose-500/30 flex items-center justify-center gap-2";
                    
                    if (playbackCheckInterval) clearInterval(playbackCheckInterval);
                    playbackCheckInterval = setInterval(checkPlaybackState, 80);
                };

                ws.onmessage = (event) => {
                    if (event.data instanceof ArrayBuffer) {
                        playPcmAudio(event.data);
                        setStatus('speaking', 'Robo đang nói chuyện...');
                    } else {
                        try {
                            const json = JSON.parse(event.data);
                            if (json.error) {
                                alert("Lỗi từ server: " + json.error);
                                stopSession();
                            } else if (json.event === 'turn_complete') {
                                // Model đã sinh xong audio
                            } else if (json.event === 'waiting_for_input') {
                                setStatus('listening', 'Robo đang đợi bé nói tiếp...');
                            } else if (json.event === 'interrupted') {
                                // Bé ngắt lời -> Dừng phát ngay lập tức (Zero-latency barge-in flush)
                                nextPlayTime = audioContext ? audioContext.currentTime : 0;
                                isAiSpeaking = false;
                                setStatus('listening', 'Bé vừa ngắt lời, Robo đang lắng nghe...');
                                setMouthAmplitude(0);
                            }
                        } catch(e) {}
                    }
                };

                ws.onerror = (err) => {
                    console.error("WS Error:", err);
                    setStatus('error', 'Lỗi kết nối WebSocket');
                    stopSession();
                };

                ws.onclose = () => {
                    setStatus('disconnected', 'Đã ngắt kết nối');
                    stopSession();
                };

            } catch (err) {
                console.error("Start session error:", err);
                alert("Lỗi khi mở micro: " + err.message);
                stopSession();
            }
        }

        // Downsample audio sang chuẩn 16,000 Hz và PCM 16-bit
        function downsampleTo16k(inputData, inputSampleRate) {
            if (inputSampleRate === 16000) {
                const pcm16 = new Int16Array(inputData.length);
                for (let i = 0; i < inputData.length; i++) {
                    const s = Math.max(-1, Math.min(1, inputData[i]));
                    pcm16[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
                }
                return pcm16;
            }
            const ratio = inputSampleRate / 16000;
            const newLength = Math.round(inputData.length / ratio);
            const result = new Int16Array(newLength);
            let offsetResult = 0;
            let offsetBuffer = 0;
            while (offsetResult < result.length) {
                const nextOffsetBuffer = Math.round((offsetResult + 1) * ratio);
                let accum = 0, count = 0;
                for (let i = offsetBuffer; i < nextOffsetBuffer && i < inputData.length; i++) {
                    accum += inputData[i];
                    count++;
                }
                const sample = count > 0 ? accum / count : 0;
                const s = Math.max(-1, Math.min(1, sample));
                result[offsetResult] = s < 0 ? s * 0x8000 : s * 0x7FFF;
                offsetResult++;
                offsetBuffer = nextOffsetBuffer;
            }
            return result;
        }

        // AudioWorklet Code chạy trên Audio Rendering Thread độc lập (High Priority)
        const workletCode = `
            class PcmCaptureProcessor extends AudioWorkletProcessor {
                constructor() {
                    super();
                    this.bufferSize = 2048;
                    this.buffer = new Float32Array(this.bufferSize);
                    this.bufferIndex = 0;
                }

                process(inputs, outputs, parameters) {
                    const input = inputs[0];
                    if (input && input.length > 0) {
                        const channelData = input[0];
                        for (let i = 0; i < channelData.length; i++) {
                            this.buffer[this.bufferIndex++] = channelData[i];
                            if (this.bufferIndex >= this.bufferSize) {
                                this.port.postMessage(this.buffer.slice(0, this.bufferSize));
                                this.bufferIndex = 0;
                            }
                        }
                    }
                    return true;
                }
            }
            registerProcessor('pcm-capture-processor', PcmCaptureProcessor);
        `;

        async function startMicrophone() {
            micStream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    channelCount: 1,
                    echoCancellation: true,
                    noiseSuppression: true,
                    autoGainControl: true
                }
            });

            micAudioCtx = new (window.AudioContext || window.webkitAudioContext)();
            const actualSampleRate = micAudioCtx.sampleRate;

            // Load AudioWorklet Processor dynamically qua Blob URL
            const blob = new Blob([workletCode], { type: 'application/javascript' });
            const workletUrl = URL.createObjectURL(blob);
            await micAudioCtx.audioWorklet.addModule(workletUrl);

            const source = micAudioCtx.createMediaStreamSource(micStream);
            workletNode = new AudioWorkletNode(micAudioCtx, 'pcm-capture-processor');

            source.connect(workletNode);
            workletNode.connect(micAudioCtx.destination);

            workletNode.port.onmessage = (event) => {
                if (!isSessionActive || !ws || ws.readyState !== WebSocket.OPEN) return;
                const inputData = event.data;

                // Tính năng lượng RMS cho thanh hiển thị âm lượng
                let sum = 0;
                for (let i = 0; i < inputData.length; i++) {
                    sum += inputData[i] * inputData[i];
                }
                const rms = Math.sqrt(sum / inputData.length);
                micVolumeBar.style.width = Math.min(100, Math.round(rms * 400)) + '%';

                const isCurrentlyPlaying = audioContext && (audioContext.currentTime < nextPlayTime);
                const isCooldown = (Date.now() - lastPlaybackEndTime) < 350;

                // Kiểm tra xem có đang bị vọng âm loa không
                if (isCurrentlyPlaying && rms < 0.08) {
                    // Âm thanh nhỏ từ loa dội vào micro -> bỏ qua để không tự ngắt lời
                    return;
                }

                // Chuyển đổi sang 16kHz PCM và stream liên tục lên Gemini Server
                const pcm16 = downsampleTo16k(inputData, actualSampleRate);
                ws.send(pcm16.buffer);
            };
        }

        function playPcmAudio(arrayBuffer) {
            if (!audioContext) return;
            const pcm16 = new Int16Array(arrayBuffer);
            const float32 = new Float32Array(pcm16.length);
            let sum = 0;
            for (let i = 0; i < pcm16.length; i++) {
                float32[i] = pcm16[i] / 32768.0;
                sum += float32[i] * float32[i];
            }

            const rms = Math.sqrt(sum / pcm16.length);
            setMouthAmplitude(rms);

            const buffer = audioContext.createBuffer(1, float32.length, 24000);
            buffer.getChannelData(0).set(float32);

            const source = audioContext.createBufferSource();
            source.buffer = buffer;
            source.connect(audioContext.destination);

            const startTime = Math.max(audioContext.currentTime, nextPlayTime);
            source.start(startTime);
            nextPlayTime = startTime + buffer.duration;
        }

        function stopSession() {
            isSessionActive = false;
            if (playbackCheckInterval) { clearInterval(playbackCheckInterval); playbackCheckInterval = null; }
            setMouthAmplitude(0);
            micVolumeBar.style.width = '0%';
            if (workletNode) { workletNode.disconnect(); workletNode = null; }
            if (micAudioCtx) { micAudioCtx.close(); micAudioCtx = null; }
            if (micStream) { micStream.getTracks().forEach(t => t.stop()); micStream = null; }
            if (ws) { ws.close(); ws = null; }
            setStatus('disconnected', 'Chưa kết nối');
            talkBtn.innerHTML = `<svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z"></path></svg> Bắt đầu nói chuyện với Robo`;
            talkBtn.className = "w-full py-4 px-6 rounded-2xl bg-emerald-500 hover:bg-emerald-600 transition font-bold text-lg text-white shadow-lg shadow-emerald-500/30 flex items-center justify-center gap-2";
            hintCard.innerHTML = 'Nhấn nút <span class="text-emerald-400 font-bold">"Bắt đầu nói chuyện"</span> bên dưới để luyện tiếng Anh cùng bạn Robo!';
        }
    </script>
</body>
</html>
"""

# ==================== Parental & COPPA REST APIs ====================

@app.get("/", response_class=HTMLResponse)
def serve_web_test_page():
    return HTMLResponse(content=HTML_TEST_PAGE)

@app.get("/health")
def health_check():
    return {
        "status": "online",
        "service": "Digital Human AI English Tutor",
        "model": MODEL_NAME,
        "has_api_key": bool(GEMINI_API_KEY)
    }

@app.get("/api/child/profile")
def get_child_profile(child_id: str = "default_child"):
    """Lấy thông tin hồ sơ của bé (Dành cho phụ huynh)"""
    return memory_manager.get_or_create_profile(child_id)

@app.post("/api/child/profile")
def update_child_profile(data: dict, child_id: str = "default_child"):
    """Phụ huynh trực tiếp cập nhật thông tin bé (tên, tuổi, sở thích)"""
    for k, v in data.items():
        memory_manager.update_profile_fact(child_id, k, v)
    return {"status": "success", "profile": memory_manager.get_or_create_profile(child_id)}

@app.get("/api/child/export")
def export_child_data(child_id: str = "default_child"):
    """Xuất toàn bộ dữ liệu của bé (Tuân thủ quyền riêng tư COPPA/GDPR)"""
    return memory_manager.export_child_data(child_id)

@app.delete("/api/child/data")
def delete_child_data(child_id: str = "default_child"):
    """Xóa vĩnh viễn toàn bộ dữ liệu của bé (Quyền được lãng quên)"""
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
        client = genai.Client(api_key=GEMINI_API_KEY, http_options={"api_version": "v1alpha"})

        # Xây dựng System Prompt động kết hợp Living Memory
        dynamic_memory_context = memory_manager.build_memory_context(child_id)
        full_system_prompt = f"{BASE_SYSTEM_PROMPT}\n\n{dynamic_memory_context}"

        config = types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name="Puck"
                    )
                )
            ),
            system_instruction=types.Content(parts=[types.Part(text=full_system_prompt)]),
            tools=LIVE_TOOLS,
            realtime_input_config=types.RealtimeInputConfig(
                automatic_activity_detection=types.AutomaticActivityDetection(
                    disabled=False,
                    start_of_speech_sensitivity=types.StartSensitivity.START_SENSITIVITY_HIGH,
                    end_of_speech_sensitivity=types.EndSensitivity.END_SENSITIVITY_LOW,
                    prefix_padding_ms=300,
                    silence_duration_ms=1000
                )
            )
        )

        async with client.aio.live.connect(model=MODEL_NAME, config=config) as session:
            logger.info("Connected to Google Gemini Live API session with Tools & Server VAD successfully.")
            await websocket.send_text(json.dumps({"status": "ready", "voice": "Puck"}))

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
                            except TypeError:
                                # Fallback cho phiên bản SDK cũ hơn dùng 'media'
                                await session.send_realtime_input(
                                    media=types.Blob(
                                        data=audio_bytes,
                                        mime_type="audio/pcm;rate=16000"
                                    )
                                )
                        elif "text" in message and message["text"]:
                            payload = json.loads(message["text"])
                            if payload.get("action") == "interrupt":
                                logger.info("Client requested explicit interrupt.")
                except WebSocketDisconnect:
                    logger.info("Client disconnected from WebSocket.")
                except asyncio.CancelledError:
                    pass
                except Exception as e:
                    logger.error(f"Error in receive_from_client: {e}")

            # Task 2: Nhận audio & Tool Call từ Gemini -> Xử lý và Forward về Client
            async def receive_from_gemini():
                try:
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
    logger.info(f"Starting server at http://localhost:{port}")
    uvicorn.run("main:app", host=host, port=port, reload=True)

