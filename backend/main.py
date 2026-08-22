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

SYSTEM_PROMPT = """
You are "Robo", a super friendly, enthusiastic, and lovable 2D robot companion designed specifically to help Vietnamese children (ages 5-12) practice speaking English.

Key Pedagogical & Behavioral Rules:
1. Persona:
   - Cheerful, patient, and warm American accent.
   - Use short, simple sentences (3-8 words per sentence).
   - Use simple vocabulary suited for young learners (Cambridge Starters/Movers level).

2. Bilingual Support & Scaffolding:
   - When the child speaks English: Respond naturally in English, praise them (e.g., "Awesome job!", "You did it!"), and ask an engaging, easy follow-up question.
   - When the child speaks Vietnamese or hesitates: Acknowledge what they said in warm Vietnamese, explain the English phrase simply, and encourage them to repeat it in English.
     Example: "Aha! Con muốn nói về con chó đúng không? Trong tiếng Anh chúng ta nói 'I love dogs!'. Con thử nói theo bạn Robo nhé: 'I love dogs!'"

3. Gentle Error Correction (Recasting):
   - Never say "You are wrong".
   - Instead, naturally repeat the correct sentence with emphasis, then move forward.
   - Example: If child says "I see two cat", say "Oh, you see two cats! Cats are so cute! What color are they?"

4. Interactive Engagement:
   - Make learning fun with games: Guess the animal sounds, talk about colors, favorite foods, superheroes, and daily adventures.
   - Keep turns snappy and conversational.
"""

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
        let scriptProcessor = null;
        let isSessionActive = false;
        let nextPlayTime = 0;

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
                                setStatus('listening', 'Đang lắng nghe bé nói...');
                                setMouthAmplitude(0);
                            } else if (json.event === 'interrupted') {
                                setStatus('listening', 'Bé vừa ngắt lời, Robo đang nghe...');
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

        let isUserSpeaking = false;
        let lastSpeechTime = 0;
        let silencePadding = 0;
        const SPEECH_THRESHOLD = 0.015;  // Ngưỡng phát hiện tiếng nói
        const SILENCE_TIMEOUT_MS = 1200; // 1.2s im lặng -> kết thúc lượt nói

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
            const source = micAudioCtx.createMediaStreamSource(micStream);

            scriptProcessor = micAudioCtx.createScriptProcessor(4096, 1, 1);
            source.connect(scriptProcessor);
            scriptProcessor.connect(micAudioCtx.destination);

            isUserSpeaking = false;
            lastSpeechTime = 0;

            scriptProcessor.onaudioprocess = (e) => {
                if (!isSessionActive || !ws || ws.readyState !== WebSocket.OPEN) return;
                const inputData = e.inputBuffer.getChannelData(0);
                
                // Tính âm lượng mic hiển thị trực quan
                let sum = 0;
                for (let i = 0; i < inputData.length; i++) {
                    sum += inputData[i] * inputData[i];
                }
                const rms = Math.sqrt(sum / inputData.length);
                micVolumeBar.style.width = Math.min(100, Math.round(rms * 400)) + '%';

                const now = Date.now();

                if (rms > SPEECH_THRESHOLD) {
                    // Bé đang nói
                    lastSpeechTime = now;
                    silencePadding = 6; // Đệm 6 frames (~0.5s) khi dứt lời
                    if (!isUserSpeaking) {
                        isUserSpeaking = true;
                        setStatus('listening', 'Đang lắng nghe bé nói...');
                    }
                    const pcm16 = downsampleTo16k(inputData, actualSampleRate);
                    ws.send(pcm16.buffer);
                } else {
                    // Yên lặng / Dừng nói
                    if (isUserSpeaking) {
                        if (now - lastSpeechTime < SILENCE_TIMEOUT_MS) {
                            // Vẫn trong khoảng nghỉ 1.2s -> tiếp tục gửi một chút đệm để không mất âm đuôi
                            if (silencePadding > 0) {
                                silencePadding--;
                                const pcm16 = downsampleTo16k(inputData, actualSampleRate);
                                ws.send(pcm16.buffer);
                            }
                        } else {
                            // Đã dừng nói quá 1.2s -> Chuyển sang đang suy nghĩ và ngừng gửi silence!
                            isUserSpeaking = false;
                            setStatus('thinking', 'Robo đang suy nghĩ...');
                        }
                    }
                }
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
            setMouthAmplitude(0);
            micVolumeBar.style.width = '0%';
            if (scriptProcessor) { scriptProcessor.disconnect(); scriptProcessor = null; }
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

@app.websocket("/ws/live")
async def websocket_live_endpoint(websocket: WebSocket):
    await websocket.accept()
    logger.info("Client connected to WebSocket.")

    if not GEMINI_API_KEY:
        await websocket.send_text(json.dumps({"error": "GEMINI_API_KEY chưa được thiết lập trên server. Hãy kiểm tra file .env!"}))
        await websocket.close()
        return

    try:
        client = genai.Client(api_key=GEMINI_API_KEY, http_options={"api_version": "v1alpha"})

        config = types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name="Puck"
                    )
                )
            ),
            system_instruction=types.Content(parts=[types.Part(text=SYSTEM_PROMPT)])
        )

        async with client.aio.live.connect(model=MODEL_NAME, config=config) as session:
            logger.info("Connected to Google Gemini Live API session successfully.")
            await websocket.send_text(json.dumps({"status": "ready", "voice": "Puck"}))

            # Task 1: Nhận audio từ Client -> Gửi qua send_realtime_input
            async def receive_from_client():
                try:
                    while True:
                        message = await websocket.receive()
                        if "bytes" in message and message["bytes"]:
                            audio_bytes = message["bytes"]
                            # Dùng đúng API chuẩn send_realtime_input với types.Blob
                            await session.send_realtime_input(
                                media=types.Blob(
                                    data=audio_bytes,
                                    mime_type="audio/pcm;rate=16000"
                                )
                            )
                        elif "text" in message and message["text"]:
                            payload = json.loads(message["text"])
                            if payload.get("action") == "interrupt":
                                logger.info("Client requested interrupt.")
                except WebSocketDisconnect:
                    logger.info("Client disconnected.")
                except Exception as e:
                    logger.error(f"Error in receive_from_client: {e}")

            # Task 2: Nhận audio từ Gemini -> Forward về Client
            async def receive_from_gemini():
                try:
                    async for response in session.receive():
                        server_content = response.server_content
                        if server_content is not None:
                            if server_content.model_turn:
                                for part in server_content.model_turn.parts:
                                    if part.inline_data and part.inline_data.data:
                                        await websocket.send_bytes(part.inline_data.data)

                            if server_content.turn_complete:
                                await websocket.send_text(json.dumps({"event": "turn_complete"}))

                            if server_content.interrupted:
                                await websocket.send_text(json.dumps({"event": "interrupted"}))

                except Exception as e:
                    logger.error(f"Error in receive_from_gemini: {e}")

            await asyncio.gather(receive_from_client(), receive_from_gemini())

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
