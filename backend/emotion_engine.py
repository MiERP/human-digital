"""Doraemon Emotion Engine — "trái tim" cảm xúc của Doraemon.

Lớp trạng thái nội tâm chạy ở backend, lưu riêng theo từng bé (child_id):
- Cảm xúc (emotion): happy, surprised, strict, displeased, sad, neutral
- Năng lượng (energy): energetic, excited, sleepy, drowsy, tired, neutral

Động cơ (drivers):
1. Nhịp ngày — giờ địa phương quyết định năng lượng nền của Doraemon.
2. Model chủ động đổi trạng thái qua tool `set_emotion` (Gemini Live function call).
3. Cảm xúc mạnh tự suy giảm dần về neutral (decay), năng lượng override có TTL.
4. Phiên nói dài làm Doraemon mệt dần (fatigue); nghỉ ngơi thì hồi phục.

Mọi trạng thái được lưu vào data/emotions/{child_id}.json nên Doraemon "nhớ"
cảm xúc của mình qua các phiên — nền tảng cho việc "lớn lên cùng bé".
"""

import json
import os
import logging
import time
from datetime import datetime
from typing import Dict, Optional

logger = logging.getLogger("digital-human-emotion")

EMOTIONS = ("happy", "surprised", "strict", "displeased", "sad", "neutral")
ENERGIES = ("energetic", "excited", "sleepy", "drowsy", "tired", "neutral")

EMOTION_LABELS_VN = {
    "happy": "vui vẻ",
    "surprised": "ngạc nhiên",
    "strict": "nghiêm khắc (nhẹ nhàng, ấm áp)",
    "displeased": "hờn dỗi",
    "sad": "buồn",
    "neutral": "bình thường",
}

ENERGY_LABELS_VN = {
    "energetic": "khỏe khoắn",
    "excited": "phấn khích",
    "sleepy": "ngái ngủ",
    "drowsy": "buồn ngủ",
    "tired": "mệt mỏi",
    "neutral": "bình thường",
}

# Cảm xúc khác neutral sẽ giảm cường độ một nửa sau khoảng thời gian này,
# rồi quay về neutral khi cường độ quá thấp.
EMOTION_HALF_LIFE_SECONDS = 240.0
# Năng lượng do model đặt (override) sẽ tự hết hạn và quay về nhịp ngày.
ENERGY_OVERRIDE_TTL_SECONDS = 900.0
# Mỗi lượt nói của bé làm Doraemon mệt thêm một chút; nghỉ > 60s thì hồi phục.
FATIGUE_PER_TURN = 0.025
FATIGUE_RECOVERY_PER_MINUTE = 0.02
FATIGUE_TIRED_THRESHOLD = 0.5


def _energy_baseline_for_hour(hour: int) -> str:
    """Nhịp sinh hoạt của Doraemon theo giờ trong ngày (giờ địa phương)."""
    if 5 <= hour < 8:
        return "sleepy"      # sáng sớm còn ngái ngủ
    if 8 <= hour < 11:
        return "energetic"   # buổi sáng khỏe khoắn
    if 11 <= hour < 13:
        return "sleepy"      # gần trưa hơi ngái
    if 13 <= hour < 15:
        return "drowsy"      # đầu giờ chiều buồn ngủ
    if 15 <= hour < 18:
        return "energetic"   # chiều khỏe khoắn
    if 18 <= hour < 21:
        return "excited"     # buổi tối vui chơi phấn khích
    return "drowsy"          # đêm muộn buồn ngủ — Doraemon rủ bé đi ngủ


_STATE_KEYS = (
    "emotion", "intensity", "energy_override", "energy_override_at",
    "fatigue", "last_turn_at", "updated_at",
)


class EmotionEngine:
    def __init__(self, data_dir: Optional[str] = None):
        if data_dir is None:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            data_dir = os.path.join(base_dir, "data", "emotions")
        self.data_dir = data_dir
        os.makedirs(data_dir, exist_ok=True)

    # ---------- persistence ----------

    def _file(self, child_id: str) -> str:
        # child_id đã được validate ở tầng main (slug-safe), không cần escape.
        return os.path.join(self.data_dir, f"{child_id}.json")

    def _fresh(self) -> Dict:
        return {
            "emotion": "neutral",
            "intensity": 0.5,
            "energy_override": None,
            "energy_override_at": 0.0,
            "fatigue": 0.0,
            "last_turn_at": 0.0,
            "updated_at": time.time(),
        }

    def _load(self, child_id: str) -> Dict:
        try:
            with open(self._file(child_id), "r", encoding="utf-8") as f:
                raw = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return self._fresh()
        state = self._fresh()
        for key in _STATE_KEYS:
            if key in raw:
                state[key] = raw[key]
        return state

    def _save(self, child_id: str, state: Dict) -> None:
        try:
            with open(self._file(child_id), "w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False)
        except OSError as e:
            logger.warning(f"Không lưu được trạng thái cảm xúc của {child_id}: {e}")

    # ---------- state computation ----------

    def get_state(self, child_id: str) -> Dict:
        """Trạng thái hiệu quả hiện tại, đã áp decay/hồi phục theo thời gian."""
        s = self._load(child_id)
        now = time.time()
        changed = False

        if s["emotion"] != "neutral":
            elapsed = max(0.0, now - s["updated_at"])
            s["intensity"] *= 0.5 ** (elapsed / EMOTION_HALF_LIFE_SECONDS)
            if s["intensity"] < 0.12:
                s["emotion"] = "neutral"
                s["intensity"] = 0.5
            changed = True

        if s["energy_override"] and now - s["energy_override_at"] > ENERGY_OVERRIDE_TTL_SECONDS:
            s["energy_override"] = None
            changed = True

        idle = now - s["last_turn_at"]
        if idle > 60 and s["fatigue"] > 0:
            minutes = min(idle / 60.0, 30.0)
            s["fatigue"] = max(0.0, s["fatigue"] - FATIGUE_RECOVERY_PER_MINUTE * minutes)
            changed = True

        if changed:
            s["updated_at"] = now
            self._save(child_id, s)
        return self._effective(s)

    def _effective(self, s: Dict) -> Dict:
        hour = datetime.now().hour
        energy = s["energy_override"] or _energy_baseline_for_hour(hour)
        if s["fatigue"] > FATIGUE_TIRED_THRESHOLD and energy != "excited":
            energy = "tired"
        return {
            "emotion": s["emotion"],
            "energy": energy,
            "intensity": round(s["intensity"], 2),
            "fatigue": round(s["fatigue"], 2),
        }

    # ---------- mutations ----------

    def set_emotion(
        self, child_id: str, emotion: Optional[str] = None, energy: Optional[str] = None
    ) -> Dict:
        s = self._load(child_id)
        now = time.time()

        if emotion in EMOTIONS:
            if emotion == "neutral":
                s["emotion"] = "neutral"
                s["intensity"] = 0.5
            else:
                s["emotion"] = emotion
                s["intensity"] = 1.0

        if energy in ENERGIES:
            if energy == "neutral":
                s["energy_override"] = None
            else:
                s["energy_override"] = energy
                s["energy_override_at"] = now

        s["updated_at"] = now
        self._save(child_id, s)
        state = self._effective(s)
        logger.info(f"Emotion update [{child_id}]: {state}")
        return state

    def record_turn(self, child_id: str) -> Dict:
        """Gọi khi Doraemon hoàn thành một lượt nói — tích lũy mệt mỏi nhẹ."""
        s = self._load(child_id)
        s["fatigue"] = min(1.0, s["fatigue"] + FATIGUE_PER_TURN)
        s["last_turn_at"] = time.time()
        s["updated_at"] = time.time()
        self._save(child_id, s)
        return self._effective(s)

    # ---------- prompt helpers ----------

    def summary_for_prompt(self, state: Dict) -> str:
        emotion = EMOTION_LABELS_VN.get(state["emotion"], state["emotion"])
        energy = ENERGY_LABELS_VN.get(state["energy"], state["energy"])
        return (
            f"- Trạng thái cảm xúc hiện tại của Doraemon: {emotion} "
            f"(cường độ {int(state['intensity'] * 100)}%). "
            f"Năng lượng: {energy}. "
            f"Mức mệt mỏi tích lũy: {int(state['fatigue'] * 100)}%.\n"
            f"- Hãy diễn tả giọng nói và nội dung cho khớp với trạng thái này, "
            f"và gọi tool set_emotion khi cảm xúc hoặc năng lượng của Doraemon "
            f"thay đổi đáng kể."
        )
