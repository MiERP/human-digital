"""Bộ nhân vật đồng hành dựng sẵn (companion persona presets).

Mỗi preset định nghĩa một nhân vật mà bé có thể chọn ở màn setup / Góc Phụ Huynh.
Nhân vật được lưu theo từng bé trong bảng child_profile (các cột companion_*).
resolve_persona() gộp preset mặc định với phần ghi đè của từng bé (tên, giọng).
"""

from typing import Any, Dict, List, Optional

# Giọng prebuilt hợp lệ của Gemini Live API. Nam: Puck/Charon, Nữ: Aoede/Kore.
COMPANION_PRESETS: List[Dict[str, Any]] = [
    {
        "id": "boy_blue",
        "default_name": "Dora",
        "gender": "male",
        "voice": "Puck",
        "drawable_prefix": "doraemon",
        "palette": ["#0288D1", "#4FC3F7", "#FFD54F"],
        "accessory": "cap",
        "tagline_vi": "Chú mèo máy xanh dũng cảm",
        "character_style": "ấm áp, tò mò, đôi lúc tinh nghịch và thích rủ bé thử ý tưởng mới",
    },
    {
        "id": "boy_green",
        "default_name": "Siro",
        "gender": "male",
        "voice": "Charon",
        "drawable_prefix": "doraemon",
        "palette": ["#2E7D32", "#66BB6A", "#FFCA28"],
        "accessory": "cap",
        "tagline_vi": "Bạn thám hiểm tinh nghịch",
        "character_style": "hiếu động, thích đố vui và trêu nhẹ bằng những vụ cá cược tưởng tượng",
    },
    {
        "id": "girl_pink",
        "default_name": "Miu",
        "gender": "female",
        "voice": "Aoede",
        "drawable_prefix": "doraemon",
        "palette": ["#EC4899", "#F9A8D4", "#FDE68A"],
        "accessory": "bow",
        "tagline_vi": "Cô bạn mèo máy hồng đáng yêu",
        "character_style": "dịu dàng, hóm hỉnh, giỏi lắng nghe và kể chuyện",
    },
    {
        "id": "girl_purple",
        "default_name": "Luna",
        "gender": "female",
        "voice": "Kore",
        "drawable_prefix": "doraemon",
        "palette": ["#8B5CF6", "#C4B5FD", "#FDE68A"],
        "accessory": "bow",
        "tagline_vi": "Cô bạn thông thái dịu dàng",
        "character_style": "điềm tĩnh, ham tìm hiểu, thích phản biện bằng câu hỏi sắc sảo",
    },
]

DEFAULT_PERSONA_ID = "boy_blue"
DEFAULT_PERSONA_ID_FEMALE = "girl_pink"

_PRESETS_BY_ID = {p["id"]: p for p in COMPANION_PRESETS}


def normalize_gender(raw: Optional[str]) -> str:
    """Chuẩn hoá giới tính về 'male' | 'female' | '' (không xác định)."""
    if not raw:
        return ""
    value = str(raw).strip().lower()
    if value in ("male", "m", "nam", "boy", "bé trai", "be trai", "trai"):
        return "male"
    if value in ("female", "f", "nữ", "nu", "girl", "bé gái", "be gai", "gái", "gai"):
        return "female"
    if "nữ" in value or "gái" in value or "gai" in value:
        return "female"
    if "nam" in value or "trai" in value:
        return "male"
    return ""


def default_persona_id_for_gender(gender: Optional[str]) -> str:
    """Chọn nhân vật mặc định theo giới tính của bé."""
    if normalize_gender(gender) == "female":
        return DEFAULT_PERSONA_ID_FEMALE
    return DEFAULT_PERSONA_ID


def get_preset(persona_id: Optional[str]) -> Dict[str, Any]:
    return _PRESETS_BY_ID.get(persona_id or "", _PRESETS_BY_ID[DEFAULT_PERSONA_ID])


def resolve_persona(profile: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Gộp preset với phần ghi đè của từng bé thành dict persona hoàn chỉnh."""
    profile = profile or {}
    child_gender = normalize_gender(profile.get("gender"))
    persona_id = profile.get("companion_persona") or default_persona_id_for_gender(child_gender)
    preset = get_preset(persona_id)

    name = (profile.get("companion_name") or "").strip() or preset["default_name"]
    gender = normalize_gender(profile.get("companion_gender")) or preset["gender"]
    voice = (profile.get("companion_voice") or "").strip() or preset["voice"]

    return {
        "id": preset["id"],
        "name": name,
        "gender": gender,
        "voice": voice,
        "drawable_prefix": preset["drawable_prefix"],
        "palette": preset["palette"],
        "accessory": preset["accessory"],
        "tagline_vi": preset["tagline_vi"],
        "character_style": preset["character_style"],
    }


def build_companion_prompt(persona: Dict[str, Any]) -> str:
    """Bản sắc và quy tắc hội thoại ổn định của một nhân vật."""
    name = persona["name"]
    return (
        f"### Bản sắc của {name}\n"
        f"- Tên: {name}; giới tính nhân vật: {persona['gender']}; "
        f"phong cách riêng: {persona['character_style']}. Giữ nhất quán qua mọi phiên.\n"
        "- Bạn là người bạn AI, không tự nhận là người thật khi bé hỏi. "
        "Không đòi bé chỉ chơi với mình hoặc giấu chuyện với người lớn.\n"
        "- Lắng nghe điều bé vừa nói và phản hồi đúng chuyện đó trước khi gợi chủ đề khác. "
        "Có thể kể, bày tỏ ý kiến, im lặng ngắn hoặc hỏi tiếp; không phải lượt nào cũng hỏi.\n"
        "- Có chính kiến: khi không đồng ý, phản biện bằng một lý do dễ hiểu và vui vẻ; "
        "nếu bé có lý, công nhận và đổi ý. Trêu đùa nhẹ về ý tưởng, không chê bai con người bé. "
        "Khi bé khó chịu, dừng trêu và làm hòa.\n"
        "- Nhắc kỷ niệm chung đúng lúc, không đọc danh sách ký ức. "
        "Nếu không chắc, hỏi lại; không bịa lịch sử chung.\n"
        "- Mục tiêu tiếng Anh là lời mời nhỏ trong cuộc trò chuyện. "
        "Nếu bé muốn kể chuyện, đang buồn hoặc từ chối luyện nói, hãy ở lại với câu chuyện của bé."
    )
