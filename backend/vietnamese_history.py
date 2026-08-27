"""
Bộ tri thức lịch sử Việt Nam đã được kiểm duyệt và viết tay cho trẻ em.

Nguồn tham khảo chính: Sách giáo khoa Lịch sử tiểu học & THCS Việt Nam (Bộ Giáo dục),
Wikipedia tiếng Việt (chỉ dùng để cross-check, không phải source trực tiếp),
các ấn phẩm của Nhà xuất bản Giáo dục Việt Nam.

Mỗi entry phải:
- Chính xác về mặt lịch sử (không suy đoán, không thêm thắt).
- Ngắn gọn (3-5 câu), dễ hiểu cho trẻ 7-12 tuổi.
- Không bạo lực đồ họa (chiến tranh được kể bằng ngôn ngữ tích cực: "đánh đuổi",
  "giành lại độc lập", thay vì chi tiết về xác chết, máu me).
- Có cặp tiếng Việt - tiếng Anh khi phù hợp.
"""

from typing import Dict, List, Optional, Tuple

# Từ điển tra cứu chính: key là slug tiếng Anh (lowercase, không dấu).
# Value là dict với 'vi' (bản tiếng Việt đầy đủ) và 'en' (bản tiếng Anh song ngữ).
CURATED_HISTORY: Dict[str, Dict[str, str]] = {
    "hai_ba_trung": {
        "vi": (
            "Hai Bà Trưng là hai chị em Trưng Trắc và Trưng Nhị, sống cách đây gần 2000 năm "
            "ở Mê Linh (nay thuộc Hà Nội). Năm 40 sau Công nguyên, Trưng Trắc cùng em gái "
            "cầm quân khởi nghĩa đánh đuổi quân Hán, giành lại độc lập cho dân tộc. "
            "Trưng Trắc trở thành vị nữ vương đầu tiên trong lịch sử Việt Nam. "
            "Sau 3 năm, vì lực lượng còn yếu, hai Bà gieo mình xuống sông Hát Giang để giữ "
            "khí tiết. Hai Bà Trưng là biểu tượng của lòng yêu nước và tinh thần bất khuất "
            "của phụ nữ Việt Nam."
        ),
        "en": (
            "The Trưng Sisters (Hai Bà Trưng) were Trưng Trắc and her younger sister "
            "Trưng Nhị, who lived nearly 2000 years ago in Mê Linh (now part of Hà Nội). "
            "In 40 AD, they led a rebellion to free the Vietnamese people from Chinese rule. "
            "Trưng Trắc became the first female ruler in Vietnamese history. "
            "After three years of fighting, they sacrificed themselves rather than surrender. "
            "They are symbols of patriotism and courage for Vietnamese women."
        ),
        "category": "vietnamese_history",
        "key_figures": ["Trưng Trắc", "Trưng Nhị"],
        "era": "40-43 AD",
    },

    "tran_hung_dao": {
        "vi": (
            "Trần Hưng Đạo (1234-1300) là một vị tướng tài ba nhất của Việt Nam thời Trần. "
            "Ông ba lần đánh thắng quân Nguyên Mông (một đế quốc lớn nhất thế giới lúc đó) "
            "vào các năm 1258, 1285 và 1288. Đặc biệt trận Bạch Đằng năm 1288, ông cho "
            "cắm cọc nhọn dưới lòng sông Bạch Đằng để đánh tan đoàn thuyền của giặc. "
            "Ông để lại bài thơ 'Hịch tướng sĩ' nổi tiếng cổ vũ tinh thần yêu nước."
        ),
        "en": (
            "Trần Hưng Đạo (1234-1300) was the greatest military commander of the Trần Dynasty. "
            "He defeated the Mongol Empire — the largest empire in the world at that time — "
            "three times in 1258, 1285, and 1288. In the famous Battle of Bạch Đằng River (1288), "
            "he placed sharpened wooden stakes underwater to destroy the enemy fleet. "
            "He wrote the famous 'Hịch tướng sĩ' (Rousing Soldiers), a patriotic war poem."
        ),
        "category": "vietnamese_history",
        "key_figures": ["Trần Hưng Đạo", "Trần Quốc Toản"],
        "era": "Trần Dynasty (1225-1400)",
    },

    "le_loi": {
        "vi": (
            "Lê Lợi (1385-1433) là người sáng lập ra nhà Lê, một triều đại phát triển rực rỡ "
            "của Việt Nam. Năm 1418, ông khởi nghĩa ở Lam Sơn (Thanh Hóa) đánh đuổi quân Minh "
            "xâm lược. Sau 10 năm chiến đấu, ông giành lại độc lập và lên ngôi vua năm 1428, "
            "lấy hiệu là Lê Thái Tổ. Câu chuyện về con gươm thần 'thuận thuận thuận' và thanh "
            "kiếm trả lại rùa thần ở hồ Hoàn Kiếm là một truyền thuyết nổi tiếng gắn với ông."
        ),
        "en": (
            "Lê Lợi (1385-1433) founded the Lê Dynasty, one of the most prosperous periods in "
            "Vietnamese history. In 1418, he started a rebellion in Lam Sơn (Thanh Hóa province) "
            "to free Vietnam from Ming Chinese occupation. After 10 years of fighting, he "
            "declared independence in 1428 and became Emperor Lê Thái Tổ. The famous legend "
            "of the Heaven-sent sword and the turtle taking it back at Hoàn Kiếm Lake is told "
            "about him."
        ),
        "category": "vietnamese_history",
        "key_figures": ["Lê Lợi (Lê Thái Tổ)", "Nguyễn Trãi"],
        "era": "Lê Dynasty (1428-1788)",
    },

    "quang_trung": {
        "vi": (
            "Quang Trung Hoàng đế (1753-1792), tên thật Nguyễn Huệ, là một vị anh hùng dân tộc. "
            "Năm 1789, ông chỉ huy quân Tây Sơn đánh tan 29 vạn quân Thanh (Trung Quốc) chỉ "
            "trong vài ngày, nổi tiếng với chiến thắng 'Đống Đa' mùa xuân. Ông là vị vua có "
            "tài năng quân sự xuất sắc, đồng thời quan tâm đến giáo dục và cải cách hành chính. "
            "Ông mất sớm ở tuổi 39, để lại nhiều tiếc thương."
        ),
        "en": (
            "Emperor Quang Trung (1753-1792), whose real name was Nguyễn Huệ, was a national "
            "hero. In 1789, he commanded the Tây Sơn army and defeated 290,000 Qing (Chinese) "
            "soldiers in just a few days at the famous Battle of Đống Đa. He was a brilliant "
            "military leader who also cared about education and administrative reform. "
            "He died young at 39, leaving a great legacy."
        ),
        "category": "vietnamese_history",
        "key_figures": ["Nguyễn Huệ (Quang Trung)", "Nguyễn Lữ"],
        "era": "Tây Sơn Dynasty (1778-1802)",
    },

    "ho_chi_minh": {
        "vi": (
            "Hồ Chí Minh (1890-1969), tên thật Nguyễn Sinh Cung, là lãnh tụ cách mạng và là "
            "Chủ tịch đầu tiên của nước Việt Nam Dân chủ Cộng hòa (nay là Việt Nam). "
            "Sinh ra ở Nghệ An, ông đi nhiều nước tìm đường cứu nước, sáng lập Đảng Cộng sản "
            "Việt Nam năm 1930. Năm 1945, ông đọc Tuyên ngôn Độc lập, khai sinh nước Việt Nam "
            "mới. Ông cũng là tác giả của 'Nhật ký trong tù' — một tác phẩm nổi tiếng viết "
            "bằng thơ chữ Hán trong nhà tù."
        ),
        "en": (
            "Hồ Chí Minh (1890-1969), whose real name was Nguyễn Sinh Cung, was the revolutionary "
            "leader and first President of the Democratic Republic of Vietnam (now Vietnam). "
            "Born in Nghệ An province, he traveled around the world seeking a way to save his "
            "country, and founded the Communist Party of Vietnam in 1930. In 1945, he read the "
            "Declaration of Independence, giving birth to the new Vietnam. He also wrote 'Prison "
            "Diary' (Nhật ký trong tù) — a famous poetry collection written in Chinese characters "
            "while he was in prison."
        ),
        "category": "vietnamese_history",
        "key_figures": ["Hồ Chí Minh", "Nguyễn Sinh Cung", "Bác Hồ"],
        "era": "20th century",
    },

    "ly_thuong_kiet": {
        "vi": (
            "Lý Thường Kiệt (1019-1105) là một danh tướng thời nhà Lý. Năm 1076-1077, ông chỉ "
            "huy quân đội Việt Nam đánh tan cuộc xâm lược của nhà Tống (Trung Quốc), bảo vệ "
            "biên giới phía Bắc. Ông còn là một nhà thơ, nổi tiếng với bài thơ 'Nam quốc sơn "
            "hà' — bài thơ đầu tiên của Việt Nam tuyên bố chủ quyền đất nước: 'Sông núi nước "
            "Nam vua Nam ở'. Bài thơ này được coi là bản tuyên ngôn độc lập đầu tiên."
        ),
        "en": (
            "Lý Thường Kiệt (1019-1105) was a famous general of the Lý Dynasty. In 1076-1077, "
            "he commanded Vietnamese forces to defeat the Song Dynasty's invasion from China, "
            "protecting the northern border. He was also a poet — famous for 'Nam quốc sơn hà' "
            "(The Southern Country's Mountains and Rivers), considered Vietnam's first declaration "
            "of independence: 'The mountains and rivers of the South belong to the Southern king.'"
        ),
        "category": "vietnamese_history",
        "key_figures": ["Lý Thường Kiệt"],
        "era": "Lý Dynasty (1009-1225)",
    },

    "dinh_tien_hoang": {
        "vi": (
            "Đinh Tiên Hoàng (924-979), tên thật Đinh Bộ Lĩnh, là vị hoàng đế đầu tiên của "
            "Việt Nam sau thời Bắc thuộc kéo dài hơn 1000 năm. Năm 968, ông thống nhất 12 sứ "
            "quân và lên ngôi, đặt tên nước là Đại Cồ Việt. Ông đặt nền móng cho nhà nước "
            "phong kiến độc lập tự chủ đầu tiên sau thời kỳ Bắc thuộc."
        ),
        "en": (
            "Đinh Tiên Hoàng (924-979), whose real name was Đinh Bộ Lĩnh, was the first emperor "
            "of Vietnam after more than 1000 years of Chinese domination. In 968, he united the "
            "12 warlords and became emperor, naming the country Đại Cồ Việt (Great Viet). "
            "He laid the foundation for the first independent feudal state after Chinese rule."
        ),
        "category": "vietnamese_history",
        "key_figures": ["Đinh Bộ Lĩnh", "Đinh Tiên Hoàng"],
        "era": "Đinh Dynasty (968-980)",
    },
}


# Tri thức về khoa học tự nhiên phổ biến trẻ em quan tâm.
# Cũng được viết tay + kiểm chứng với Wikipedia Simple English.
CURATED_SCIENCE: Dict[str, Dict[str, str]] = {
    "blue_whale": {
        "vi": (
            "Cá voi xanh (blue whale) là loài động vật lớn nhất từng tồn tại trên Trái Đất, "
            "lớn hơn cả khủng long! Một con cá voi xanh trưởng thành dài tới 30 mét và nặng "
            "khoảng 200 tấn — bằng trọng lượng của khoảng 33 con voi châu Á. "
            "Tim của nó to bằng một chiếc xe ô tô nhỏ, và lưỡi nặng bằng một con voi. "
            "Chúng sống ở tất cả các đại dương trên thế giới."
        ),
        "en": (
            "The blue whale is the largest animal ever to exist on Earth — even bigger than any "
            "dinosaur! An adult blue whale can grow up to 30 meters long and weigh about 200 "
            "tonnes — as heavy as 33 Asian elephants. Its heart is as big as a small car, and "
            "its tongue alone weighs as much as one elephant. Blue whales live in all of Earth's "
            "oceans."
        ),
        "category": "science_animals",
    },
    "t_rex": {
        "vi": (
            "T-Rex (Tyrannosaurus rex, nghĩa là 'vua thằn lằn bạo chúa') sống cách đây khoảng "
            "68-66 triệu năm, ở cuối kỷ Phấn trắng. Nó là một trong những loài khủng long ăn "
            "thịt lớn nhất: dài khoảng 12-13 mét, cao 4 mét, nặng tới 8 tấn. "
            "Răng của T-Rex to như quả chuối, có thể nghiền nát xương. "
            "T-Rex có hai chân sau rất khỏe nhưng hai tay nhỏ xíu — bí ẩn mà các nhà khoa học "
            "vẫn đang nghiên cứu."
        ),
        "en": (
            "T-Rex (Tyrannosaurus rex, meaning 'king of the tyrant lizards') lived about 68-66 "
            "million years ago, at the end of the Cretaceous period. It was one of the largest "
            "meat-eating dinosaurs: about 12-13 meters long, 4 meters tall, and weighing up to "
            "8 tonnes. T-Rex had teeth as big as bananas, strong enough to crush bone. "
            "It had very powerful hind legs but tiny arms — a mystery scientists still study."
        ),
        "category": "science_animals",
    },
}


# Helper: tìm curated entry theo query ngôn ngữ tự nhiên.
# Áp dụng simple keyword matching đủ dùng cho trẻ em — không cần NLP phức tạp.
def lookup_curated(query: str) -> Optional[Tuple[Dict[str, str], str, str]]:
    """
    Tìm curated entry khớp với query.
    Returns: (entry_dict, key, source_name) hoặc None.
    """
    q_lower = query.lower()

    # Check history keys
    for key, entry in CURATED_HISTORY.items():
        key_figures = entry.get("key_figures", [])
        # Match nếu query chứa tên nhân vật hoặc từ khóa
        for figure in key_figures:
            figure_l = figure.lower()
            # Strip diacritics for matching
            q_normalized = _strip_vietnamese_diacritics(q_lower)
            figure_normalized = _strip_vietnamese_diacritics(figure_l)
            if figure_normalized in q_normalized or figure_l in q_lower:
                return (entry, key, f"Doraemon Knowledge Base: {figure}")

    # Match các alias phổ biến
    history_aliases = {
        "hai ba trung": "hai_ba_trung",
        "trung sisters": "hai_ba_trung",
        "trung trac": "hai_ba_trung",
        "trung nhi": "hai_ba_trung",
        "tran hung dao": "tran_hung_dao",
        "tran hung dao": "tran_hung_dao",
        "le loi": "le_loi",
        "le thai to": "le_loi",
        "lam son": "le_loi",
        "quang trung": "quang_trung",
        "nguyen hue": "quang_trung",
        "tay son": "quang_trung",
        "ho chi minh": "ho_chi_minh",
        "bac ho": "ho_chi_minh",
        "ly thuong kiet": "ly_thuong_kiet",
        "nam quoc son ha": "ly_thuong_kiet",
        "dinh tien hoang": "dinh_tien_hoang",
        "dinh bo linh": "dinh_tien_hoang",
        "dai co viet": "dinh_tien_hoang",
    }
    for alias, key in history_aliases.items():
        if alias in q_lower or _strip_vietnamese_diacritics(alias) in _strip_vietnamese_diacritics(q_lower):
            if key in CURATED_HISTORY:
                entry = CURATED_HISTORY[key]
                return (entry, key, f"Doraemon Knowledge Base: {alias.title()}")

    # Check science keys
    for key, entry in CURATED_SCIENCE.items():
        if key.replace("_", " ") in q_lower:
            return (entry, key, f"Doraemon Knowledge Base: {key.replace('_', ' ').title()}")

    # Science aliases
    science_aliases = {
        "cá voi xanh": "blue_whale",
        "blue whale": "blue_whale",
        "whale": "blue_whale",
        "t-rex": "t_rex",
        "t rex": "t_rex",
        "tyrannosaurus": "t_rex",
        "khủng long bạo chúa": "t_rex",
        "khung long": "t_rex",
    }
    for alias, key in science_aliases.items():
        if alias in q_lower or _strip_vietnamese_diacritics(alias) in _strip_vietnamese_diacritics(q_lower):
            if key in CURATED_SCIENCE:
                entry = CURATED_SCIENCE[key]
                return (entry, key, f"Doraemon Knowledge Base: {alias.title()}")

    return None


def _strip_vietnamese_diacritics(text: str) -> str:
    """Bỏ dấu tiếng Việt để so sánh dễ dàng hơn (vd: 'Hai Bà Trưng' -> 'hai ba trung')."""
    import unicodedata
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower()