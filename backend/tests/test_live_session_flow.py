"""Exercise the real WebSocket endpoint with a deterministic Gemini Live stand-in."""

import os
import hashlib
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import main
from emotion_engine import EmotionEngine
from memory_manager import MemoryManager


class FakeGeminiSession:
    def __init__(self):
        self.tool_responses = []
        self.greeting_sent = False

    async def send_client_content(self, **kwargs):
        self.greeting_sent = True

    async def send_tool_response(self, **kwargs):
        self.tool_responses.append(kwargs)

    async def receive(self):
        yield SimpleNamespace(
            tool_call=None,
            server_content=None,
            session_resumption_update=SimpleNamespace(
                new_handle="resume-test-handle", resumable=True,
            ),
        )
        for name, args in (
            ("save_shared_moment", {"content": "Hai bạn đặt tên cho tàu vũ trụ là Sao Xanh"}),
            ("complete_session_end", {"summary": "Hai bạn cùng khám phá tàu vũ trụ."}),
        ):
            yield SimpleNamespace(
                tool_call=SimpleNamespace(function_calls=[SimpleNamespace(
                    id=name, name=name, args=args,
                )]),
                server_content=None,
            )
        yield SimpleNamespace(
            tool_call=None,
            server_content=SimpleNamespace(
                model_turn=SimpleNamespace(parts=[SimpleNamespace(
                    inline_data=SimpleNamespace(data=b"farewell-audio"), text=None,
                )]),
                turn_complete=True,
                interrupted=False,
                waiting_for_input=False,
                input_transcription=None,
                output_transcription=None,
            ),
        )


class FakeGeminiClient:
    session = FakeGeminiSession()
    prompt = None
    resumption_handle = None

    def __init__(self, **kwargs):
        self.aio = SimpleNamespace(live=self)

    def connect(self, **kwargs):
        FakeGeminiClient.prompt = kwargs["config"].system_instruction.parts[0].text
        FakeGeminiClient.resumption_handle = kwargs["config"].session_resumption.handle
        return self

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, exc_type, exc, tb):
        return False


class RejectingResumptionClient(FakeGeminiClient):
    def connect(self, **kwargs):
        if kwargs["config"].session_resumption.handle:
            raise RuntimeError("expired resumption handle")
        return super().connect(**kwargs)


class TestLiveSessionFlow(unittest.TestCase):
    def test_persona_memory_audio_and_graceful_end(self):
        with tempfile.TemporaryDirectory() as tmp:
            memory = MemoryManager(db_path=os.path.join(tmp, "memory.db"))
            memory.get_or_create_profile("test_companion")
            memory.update_profile("test_companion", {
                "companion_persona": "boy_green", "companion_name": "Siro",
            })
            emotion = EmotionEngine(data_dir=os.path.join(tmp, "emotions"))
            FakeGeminiClient.session = FakeGeminiSession()
            with patch.object(main, "memory_manager", memory), \
                    patch.object(main, "emotion_engine", emotion), \
                    patch.object(main.genai, "Client", FakeGeminiClient), \
                    patch.object(main.key_pool, "acquire_key", return_value="test-key"), \
                    patch.object(main.key_pool, "release_key"):
                with TestClient(main.app) as client:
                    with client.websocket_connect("/ws/live?child_id=test_companion") as ws:
                        ws.send_json({"action": "auth_init", "child_id": "test_companion"})
                        ready = ws.receive_json()
                        resumption = ws.receive_json()
                        audio = ws.receive_bytes()
                        turn = ws.receive_json()
                        ended = ws.receive_json()
                        # Server closes the socket after a short grace period.
                        # Consume that close so the test client does not cancel
                        # its portal while the server is still shutting down.
                        try:
                            ws.receive_json()
                        except Exception:
                            pass

            self.assertEqual(ready["status"], "ready")
            self.assertEqual(resumption, {
                "event": "session_resumption", "handle": "resume-test-handle",
                "key_id": hashlib.sha256(b"test-key").hexdigest()[:16],
            })
            self.assertIsNone(FakeGeminiClient.resumption_handle)
            self.assertEqual(ready["companion"]["name"], "Siro")
            self.assertIn("phản biện", FakeGeminiClient.prompt)
            self.assertIn("Conversation-first", FakeGeminiClient.prompt)
            self.assertIn("không tự chuyển sang bài học", FakeGeminiClient.prompt)
            self.assertIn("Chủ động như một người bạn", FakeGeminiClient.prompt)
            # No learning plan -> learning must not appear in the prompt at all.
            self.assertNotIn("Learning Plan", FakeGeminiClient.prompt)
            self.assertTrue(FakeGeminiClient.session.greeting_sent)
            self.assertEqual(audio, b"farewell-audio")
            self.assertEqual(turn["event"], "turn_complete")
            self.assertEqual(ended["event"], "session_ended")
            self.assertEqual(len(memory.get_shared_moments("test_companion")), 1)
            self.assertEqual(len(FakeGeminiClient.session.tool_responses), 2)

    def test_reconnect_passes_client_handle_to_gemini(self):
        with tempfile.TemporaryDirectory() as tmp:
            memory = MemoryManager(db_path=os.path.join(tmp, "memory.db"))
            emotion = EmotionEngine(data_dir=os.path.join(tmp, "emotions"))
            FakeGeminiClient.session = FakeGeminiSession()
            with patch.object(main, "memory_manager", memory), \
                    patch.object(main, "emotion_engine", emotion), \
                    patch.object(main.genai, "Client", FakeGeminiClient), \
                    patch.object(main.key_pool, "acquire_key", return_value="test-key"), \
                    patch.object(main.key_pool, "release_key"):
                with TestClient(main.app) as client:
                    with client.websocket_connect("/ws/live?child_id=test_companion") as ws:
                        ws.send_json({
                            "action": "auth_init", "child_id": "test_companion",
                            "is_reconnect": True,
                            "session_resumption_handle": "previous-handle",
                            "resumption_key_id": hashlib.sha256(b"test-key").hexdigest()[:16],
                        })
                        self.assertEqual(ws.receive_json()["status"], "ready")
                        self.assertEqual(FakeGeminiClient.resumption_handle, "previous-handle")
                        self.assertFalse(FakeGeminiClient.session.greeting_sent)
                        # Consume remaining fake events before closing the test portal.
                        for _ in range(4):
                            ws.receive()
                        try:
                            ws.receive_json()
                        except Exception:
                            pass

    def test_expired_handle_is_cleared_and_socket_requests_retry(self):
        with tempfile.TemporaryDirectory() as tmp:
            memory = MemoryManager(db_path=os.path.join(tmp, "memory.db"))
            emotion = EmotionEngine(data_dir=os.path.join(tmp, "emotions"))
            with patch.object(main, "memory_manager", memory), \
                    patch.object(main, "emotion_engine", emotion), \
                    patch.object(main.genai, "Client", RejectingResumptionClient), \
                    patch.object(main.key_pool, "acquire_key", return_value="test-key"), \
                    patch.object(main.key_pool, "release_key"):
                with TestClient(main.app) as client:
                    with client.websocket_connect("/ws/live?child_id=test_companion") as ws:
                        ws.send_json({
                            "action": "auth_init", "child_id": "test_companion",
                            "is_reconnect": True,
                            "session_resumption_handle": "expired-handle",
                            "resumption_key_id": hashlib.sha256(b"test-key").hexdigest()[:16],
                        })
                        self.assertEqual(ws.receive_json(), {
                            "event": "session_resumption", "handle": "", "key_id": "",
                        })
                        self.assertIn("expired resumption handle", ws.receive_json()["error"])
                        with self.assertRaises(WebSocketDisconnect) as error:
                            ws.receive_json()
                        self.assertEqual(error.exception.code, 1011)


if __name__ == "__main__":
    unittest.main()
