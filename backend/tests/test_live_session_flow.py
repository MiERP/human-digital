"""Exercise the real WebSocket endpoint with a deterministic Gemini Live stand-in."""

import os
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient

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

    def __init__(self, **kwargs):
        self.aio = SimpleNamespace(live=self)

    def connect(self, **kwargs):
        FakeGeminiClient.prompt = kwargs["config"].system_instruction.parts[0].text
        return self

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, exc_type, exc, tb):
        return False


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
                        audio = ws.receive_bytes()
                        turn = ws.receive_json()
                        ended = ws.receive_json()

            self.assertEqual(ready["status"], "ready")
            self.assertEqual(ready["companion"]["name"], "Siro")
            self.assertIn("phản biện", FakeGeminiClient.prompt)
            self.assertTrue(FakeGeminiClient.session.greeting_sent)
            self.assertEqual(audio, b"farewell-audio")
            self.assertEqual(turn["event"], "turn_complete")
            self.assertEqual(ended["event"], "session_ended")
            self.assertEqual(len(memory.get_shared_moments("test_companion")), 1)
            self.assertEqual(len(FakeGeminiClient.session.tool_responses), 2)


if __name__ == "__main__":
    unittest.main()
