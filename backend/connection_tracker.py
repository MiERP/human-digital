import time
import json
import logging
import asyncio
from typing import Dict, Any, List, Optional
from fastapi import WebSocket

logger = logging.getLogger("digital-human-tracker")

class ActiveSession:
    def __init__(
        self,
        session_id: str,
        websocket: WebSocket,
        child_id: str,
        device_fingerprint: str,
        device_model: str,
        ip: str,
        key_masked: str
    ):
        self.session_id: str = session_id
        self.websocket: WebSocket = websocket
        self.child_id: str = child_id
        self.device_fingerprint: str = device_fingerprint
        self.device_model: str = device_model or "Unknown Device"
        self.ip: str = ip
        self.key_masked: str = key_masked
        self.connected_at: float = time.time()
        self.last_ping_at: float = time.time()

    @property
    def duration_seconds(self) -> int:
        return max(0, int(time.time() - self.connected_at))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "child_id": self.child_id,
            "device_fingerprint": self.device_fingerprint,
            "device_model": self.device_model,
            "ip": self.ip,
            "key_masked": self.key_masked,
            "connected_at_ts": self.connected_at,
            "duration_sec": self.duration_seconds,
            "connected_at_str": time.strftime("%H:%M:%S %d/%m/%Y", time.localtime(self.connected_at))
        }

class ActiveConnectionTracker:
    """Theo dõi tất cả các kết nối WebSocket đang đàm thoại trong thời gian thực."""
    def __init__(self):
        self._sessions: Dict[str, ActiveSession] = {}
        self._lock = asyncio.Lock()

    async def register(
        self,
        session_id: str,
        websocket: WebSocket,
        child_id: str,
        device_fingerprint: str,
        device_model: str,
        ip: str,
        key_masked: str
    ) -> ActiveSession:
        async with self._lock:
            session = ActiveSession(
                session_id=session_id,
                websocket=websocket,
                child_id=child_id,
                device_fingerprint=device_fingerprint,
                device_model=device_model,
                ip=ip,
                key_masked=key_masked
            )
            self._sessions[session_id] = session
            logger.info(f"Registered live session: {session_id} for device [{device_fingerprint[:12]}...] (Active: {len(self._sessions)})")
            return session

    async def unregister(self, session_id: str):
        async with self._lock:
            if session_id in self._sessions:
                s = self._sessions.pop(session_id)
                logger.info(f"Unregistered live session: {session_id} (Duration: {s.duration_seconds}s, Remaining: {len(self._sessions)})")

    async def get_active_sessions(self) -> List[Dict[str, Any]]:
        async with self._lock:
            return [s.to_dict() for s in self._sessions.values()]

    async def kick_by_fingerprint(self, device_fingerprint: str, reason: str = "Bị Quản trị viên ngắt kết nối") -> int:
        """Ngắt kết nối tức thì tất cả session của 1 thiết bị."""
        kicked_count = 0
        to_kick = []
        async with self._lock:
            for s_id, s in self._sessions.items():
                if s.device_fingerprint == device_fingerprint:
                    to_kick.append(s)

        for s in to_kick:
            try:
                await s.websocket.send_text(json.dumps({
                    "event": "device_banned",
                    "reason": reason
                }))
                await s.websocket.close(code=1008)
                kicked_count += 1
                logger.warning(f"Kicked live session {s.session_id} for device {device_fingerprint}")
            except Exception as e:
                logger.debug(f"Error closing socket on kick: {e}")

        return kicked_count

    @property
    def online_count(self) -> int:
        return len(self._sessions)

connection_tracker = ActiveConnectionTracker()
