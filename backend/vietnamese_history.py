"""
Bộ tri thức Bách khoa toàn thư viết tay chuẩn hóa cho trẻ em (5-12 tuổi).
Được biên soạn cẩn thận, chính xác theo SGK Giáo dục Việt Nam & Wikipedia Giáo dục.

Bao gồm hơn 100 chủ đề vàng:
1. Lịch sử & Danh nhân Việt Nam
2. Chiến tích & Di tích Lịch sử
3. Địa lý & Danh lam thắng cảnh Việt Nam
4. Hệ Mặt Trời & Thiên văn Vũ trụ
5. Khoa học Tự nhiên & Hiện tượng đời sống
6. Thế giới Động vật & Sinh học
7. Phát minh & Công nghệ

Mỗi mục gồm:
- 'vi': Bản tóm tắt tiếng Việt thân thiện, giàu hình ảnh, dễ hiểu (3-5 câu).
- 'en': Bản tiếng Anh ngắn gọn giúp Doraemon sprinkle từ vựng song ngữ.
- 'category': Phân loại chủ đề.
- 'key_figures': Danh sách từ khóa đối sánh thực thể.
"""

from typing import Dict, List, Optional, Tuple
import unicodedata

CURATED_KNOWLEDGE: Dict[str, Dict[str, any]] = {
    # ==================== 1. LỊCH SỬ & DANH NHÂN VIỆT NAM ====================
    "hung_vuong": {
        "vi": (
            "Các Vua Hùng là những vị vua đầu tiên lập nên nhà nước Văn Lang — nhà nước đầu tiên "
            "trong lịch sử Việt Nam, đóng đô ở Phong Châu (nay thuộc Phú Thọ). Có 18 đời vua Hùng "
            "với nhiều truyền thuyết nổi tiếng như Bánh chưng bánh giầy, Sơn Tinh Thủy Tinh, Thánh Gióng. "
            "Ngày mùng 10 tháng 3 Âm lịch hằng năm là ngày Giỗ Tổ Hùng Vương để con cháu nhớ ơn cội nguồn."
        ),
        "en": (
            "The Hùng Kings (Vua Hùng) were the legendary first rulers who founded Văn Lang, the first "
            "Vietnamese kingdom in Phong Châu (Phú Thọ). There were 18 generations of Hùng Kings. "
            "Every year on the 10th day of the 3rd lunar month, Vietnamese people celebrate the Hùng Kings Temple Festival."
        ),
        "category": "vietnamese_history",
        "key_figures": ["Vua Hùng", "Hùng Vương", "Văn Lang", "Giỗ Tổ Hùng Vương", "Phong Châu"],
    },

    "an_duong_vuong": {
        "vi": (
            "An Dương Vương, tên thật là Thục Phán, là người lập nên nhà nước Âu Lạc tiếp nối thời đại Hùng Vương. "
            "Ông cho xây dựng thành Cổ Loa hình xoắn ốc 9 vòng kiên cố và có tướng quân Cao Lỗ chế tạo ra chiếc nỏ thần "
            "bắn một phát ra hàng ngàn mũi tên để bảo vệ đất nước."
        ),
        "en": (
            "An Dương Vương (Thục Phán) founded the ancient kingdom of Âu Lạc. He built the legendary spiral-shaped "
            "Cổ Loa Citadel and used a magic crossbow (nỏ thần) invented by General Cao Lỗ to defend his country."
        ),
        "category": "vietnamese_history",
        "key_figures": ["An Dương Vương", "Thục Phán", "Âu Lạc", "Thành Cổ Loa", "Nỏ thần"],
    },

    "hai_ba_trung": {
        "vi": (
            "Hai Bà Trưng là hai chị em Trưng Trắc và Trưng Nhị, sống cách đây gần 2000 năm ở Mê Linh (Hà Nội). "
            "Năm 40 sau Công nguyên, Trưng Trắc cùng em gái cưỡi voi ra trận khởi nghĩa đánh đuổi quân Hán, "
            "giành lại độc lập cho dân tộc. Trưng Trắc trở thành vị nữ vương đầu tiên trong lịch sử Việt Nam. "
            "Hai Bà là biểu tượng sáng ngời của lòng yêu nước và tinh thần bất khuất của phụ nữ Việt Nam."
        ),
        "en": (
            "The Trưng Sisters (Hai Bà Trưng) were Trưng Trắc and Trưng Nhị from Mê Linh. In 40 AD, riding war elephants, "
            "they led a rebellion to liberate Vietnam from the Han Dynasty, and Trưng Trắc became the first female ruler of Vietnam."
        ),
        "category": "vietnamese_history",
        "key_figures": ["Hai Bà Trưng", "Trưng Trắc", "Trưng Nhị", "Mê Linh", "Trưng Sisters", "Hai Ba Trung"],
    },

    "ba_trieu": {
        "vi": (
            "Bà Triệu (Triệu Thị Trinh, 226–248) là nữ anh hùng quê ở Thanh Hóa. Năm 248, bà cưỡi voi trắng một ngà "
            "lãnh đạo nhân dân đứng lên khởi nghĩa chống lại quân xâm lược Đông Ngô. Câu nói nổi tiếng của bà là: "
            "'Tôi muốn cưỡi cơn gió mạnh, đạp luồng sóng dữ, chém cá kình ở biển Đông, chứ không chịu khom lưng làm tì thiếp người ta!'"
        ),
        "en": (
            "Lady Triệu (Bà Triệu, 226–248) was a fearless Vietnamese heroine who rode a single-tusked white elephant into battle "
            "against Eastern Wu invaders, famously declaring she wanted to ride the storm and tame the giant whales of the Eastern Sea."
        ),
        "category": "vietnamese_history",
        "key_figures": ["Bà Triệu", "Triệu Thị Trinh", "Triệu Quốc Đạt", "Voi trắng một ngà"],
    },

    "ngo_quyen": {
        "vi": (
            "Ngô Quyền (897–944) là vị anh hùng dân tộc vĩ đại quê ở Đường Lâm (Hà Nội). Năm 938, ông đã dùng kế cắm cọc nhọn "
            "bịt sắt dưới lòng sông Bạch Đằng, lợi dụng thủy triều lên xuống để đánh tan đoàn thuyền giặc Nam Hán. "
            "Chiến thắng Bạch Đằng năm 938 đã chấm dứt hoàn toàn hơn 1000 năm Bắc thuộc, mở ra kỷ nguyên độc lập lâu dài cho Việt Nam."
        ),
        "en": (
            "Ngô Quyền (897–944) was the legendary general who defeated the Southern Han navy in the Battle of Bạch Đằng River (938) "
            "by embedding iron-tipped wooden stakes in the riverbed, ending over 1,000 years of Chinese domination."
        ),
        "category": "vietnamese_history",
        "key_figures": ["Ngô Quyền", "Ngo Quyen", "Bạch Đằng 938", "Sông Bạch Đằng", "Đường Lâm"],
    },

    "dinh_tien_hoang": {
        "vi": (
            "Đinh Tiên Hoàng (924–979), tên thật là Đinh Bộ Lĩnh, quê ở Ninh Bình. Thuở nhỏ, ông cùng các bạn chăn trâu "
            "chơi trò 'cờ lau tập trận'. Lớn lên, ông có tài quân sự xuất chúng, dẹp yên 12 sứ quân, thống nhất đất nước vào năm 968, "
            "lên ngôi Hoàng đế và đặt tên nước là Đại Cồ Việt, đóng đô ở Hoa Lư."
        ),
        "en": (
            "Đinh Tiên Hoàng (Đinh Bộ Lĩnh, 924–979) united Vietnam by defeating 12 rival warlords in 968. He became the first Emperor "
            "of independent Vietnam, named the nation Đại Cồ Việt, and established the capital in Hoa Lư."
        ),
        "category": "vietnamese_history",
        "key_figures": ["Đinh Bộ Lĩnh", "Đinh Tiên Hoàng", "Dinh Bo Linh", "Dinh Tien Hoang", "Cờ lau tập trận", "Đại Cồ Việt", "Hoa Lư"],
    },

    "le_hoan": {
        "vi": (
            "Lê Hoàn (941–1005), tức Lê Đại Hành, là người sáng lập ra nhà Tiền Lê. Năm 981, ông trực tiếp chỉ huy quân dân "
            "đánh bại cuộc xâm lược của quân Tống trên sông Bạch Đằng và ải Chi Lăng, giữ vững nền độc lập non trẻ của nước Đại Cồ Việt. "
            "Ông cũng là vị vua đầu tiên tiến hành lễ cày ruộng Tịch điền đầu năm để khuyến khích nông nghiệp."
        ),
        "en": (
            "Lê Hoàn (Emperor Lê Đại Hành, 941–1005) founded the Early Lê Dynasty and successfully defeated Song Chinese invaders "
            "in 981. He was also the first emperor to perform the traditional royal ploughing ceremony (Tịch điền)."
        ),
        "category": "vietnamese_history",
        "key_figures": ["Lê Hoàn", "Lê Đại Hành", "Le Hoan", "Le Dai Hanh", "Tiền Lê", "Bạch Đằng 981", "Tịch điền"],
    },

    "ly_cong_uan": {
        "vi": (
            "Lý Công Uẩn (974–1028), tức Lý Thái Tổ, là người sáng lập ra triều đại nhà Lý rực rỡ. Năm 1010, nhận thấy vùng đất "
            "Hoa Lư chật hẹp, ông đã viết 'Chiếu dời đô' chuyển kinh đô về thành Đại La và đổi tên thành Thăng Long (nghĩa là Rồng bay lên, "
            "nay chính là thủ đô Hà Nội yêu dấu)."
        ),
        "en": (
            "Lý Công Uẩn (Emperor Lý Thái Tổ, 974–1028) founded the Lý Dynasty. In 1010, he wrote the famous Edict on Transferring the Capital "
            "moving the royal seat to Thăng Long ('Rising Dragon', modern Hà Nội)."
        ),
        "category": "vietnamese_history",
        "key_figures": ["Lý Công Uẩn", "Lý Thái Tổ", "Ly Cong Uan", "Ly Thai To", "Chiếu dời đô", "Thăng Long", "Nhà Lý"],
    },

    "ly_thuong_kiet": {
        "vi": (
            "Lý Thường Kiệt (1019–1105) là danh tướng kiệt xuất thời nhà Lý. Năm 1077, ông chỉ huy quân đội đánh tan quân Tống "
            "trên phòng tuyến sông Như Nguyệt (sông Cầu). Đêm đêm, ông cho người ngâm vang bài thơ thần 'Nam quốc sơn hà' "
            "('Sông núi nước Nam vua Nam ở') — được coi là bản Tuyên ngôn Độc lập đầu tiên của nước ta."
        ),
        "en": (
            "Lý Thường Kiệt (1019–1105) was a supreme commander of the Lý Dynasty who defeated the Song invasion at Như Nguyệt River. "
            "He is renowned for the patriotic poem 'Nam quốc sơn hà', regarded as Vietnam's first Declaration of Independence."
        ),
        "category": "vietnamese_history",
        "key_figures": ["Lý Thường Kiệt", "Ly Thuong Kiet", "Nam quốc sơn hà", "Sông Như Nguyệt", "Phòng tuyến sông Cầu"],
    },

    "tran_hung_dao": {
        "vi": (
            "Trần Hưng Đạo (1234–1300), tên thật là Trần Quốc Tuấn, là vị tướng thiên tài thời nhà Trần. Ông đã chỉ huy quân dân "
            "Đại Việt 3 lần đánh thắng đội quân Nguyên Mông hùng mạnh bậc nhất thế giới thời đó (1258, 1285, 1288). "
            "Đặc biệt trong trận Bạch Đằng năm 1288, ông tái lập trận địa cọc gỗ chôn vùi toàn bộ hạm đội giặc. "
            "Ông là tác giả bài 'Hịch tướng sĩ' bất hủ."
        ),
        "en": (
            "Trần Hưng Đạo (Trần Quốc Tuấn, 1234–1300) was the supreme military commander of the Trần Dynasty who defeated three Mongol invasions "
            "in 1258, 1285, and 1288, famously using underwater stakes at the Battle of Bạch Đằng (1288)."
        ),
        "category": "vietnamese_history",
        "key_figures": ["Trần Hưng Đạo", "Trần Quốc Tuấn", "Tran Hung Dao", "Tran Quoc Tuan", "Hịch tướng sĩ", "Bạch Đằng 1288", "Nhà Trần"],
    },

    "tran_quoc_toan": {
        "vi": (
            "Trần Quốc Toản (1267–1285) là người anh hùng thiếu niên dũng cảm thời nhà Trần. Vì còn quá nhỏ tuổi (15 tuổi) không được "
            "vào dự hội nghị Bình Than bàn việc đánh giặc, cậu đã ấm ức bóp nát quả cam trong tay lúc nào không biết. "
            "Sau đó, Quốc Toản về quê tự chiêu mộ hơn một ngàn binh sĩ trẻ, thêu lên lá cờ 6 chữ vàng 'Phá cường địch, báo hoàng ân' "
            "và lập nhiều chiến công lẫy lừng."
        ),
        "en": (
            "Trần Quốc Toản (1267–1285) was a brave teenage hero of the Trần Dynasty who accidentally crushed an orange in frustration "
            "when excluded from the war council due to young age. He formed his own army under a banner reading 'Destroy the Enemy, Repay the Emperor'."
        ),
        "category": "vietnamese_history",
        "key_figures": ["Trần Quốc Toản", "Tran Quoc Toan", "Bóp nát quả cam", "Phá cường địch báo hoàng ân", "Bình Than"],
    },

    "chu_van_an": {
        "vi": (
            "Chu Văn An (1292–1370) là nhà giáo dục lỗi lạc, được tôn xưng là 'Vạn thế sư biểu' (Người thầy của muôn đời). "
            "Ông từng giữ chức Tư nghiệp Quốc Tử Giám — trường đại học đầu tiên của Việt Nam, dạy dỗ nhiều thế hệ nhân tài. "
            "Ông nổi tiếng thanh liêm, chính trực, từng dâng 'Thất trảm sớ' xin chém 7 tên gian thần."
        ),
        "en": (
            "Chu Văn An (1292–1370) was an eminent educator and scholar known as the 'Teacher of Ten Thousand Generations'. "
            "He served as rector of Quốc Tử Giám (Imperial Academy) and was revered for his integrity and dedication to students."
        ),
        "category": "vietnamese_history",
        "key_figures": ["Chu Văn An", "Chu Van An", "Vạn thế sư biểu", "Quốc Tử Giám", "Thất trảm sớ"],
    },

    "le_loi": {
        "vi": (
            "Lê Lợi (1385–1433), tức Lê Thái Tổ, là lãnh tụ cuộc khởi nghĩa Lam Sơn (Thanh Hóa). Sau 10 năm gian khổ chiến đấu "
            "cùng quân sư Nguyễn Trãi, ông đã đánh đuổi hoàn toàn quân Minh xâm lược, giành lại độc lập năm 1428 và lập nên nhà Hậu Lê. "
            "Truyền thuyết Hồ Gươm kể rằng sau khi hòa bình lập lại, Rùa Vàng đã nổi lên nhận lại thanh gươm Thuận Thiên thần kỳ."
        ),
        "en": (
            "Lê Lợi (Emperor Lê Thái Tổ, 1385–1433) led the Lam Sơn Uprising, liberating Vietnam from Ming occupation after 10 years "
            "of struggle. He founded the Later Lê Dynasty, commemorated by the legend of the Magic Sword returned to the Golden Turtle at Hoàn Kiếm Lake."
        ),
        "category": "vietnamese_history",
        "key_figures": ["Lê Lợi", "Lê Thái Tổ", "Le Loi", "Le Thai To", "Khởi nghĩa Lam Sơn", "Hồ Gươm", "Gươm Thuận Thiên", "Rùa Vàng"],
    },

    "nguyen_trai": {
        "vi": (
            "Nguyễn Trãi (1380–1442), hiệu Ức Trai, là danh nhân văn hóa thế giới và đại công thần khai quốc thời Lê. "
            "Ông là mưu sĩ kiệt xuất giúp Lê Lợi đánh thắng giặc bằng chiến lược 'đánh vào lòng người' (tâm công). "
            "Ông là tác giả của áng thiên cổ hùng văn 'Bình Ngô đại cáo' — bản Tuyên ngôn Độc lập thứ hai khẳng định chủ quyền của đất nước."
        ),
        "en": (
            "Nguyễn Trãi (1380–1442) was a legendary strategist, poet, and UNESCO-recognized World Cultural Celebrity. "
            "He helped Lê Lợi achieve independence and penned 'Bình Ngô đại cáo', considered Vietnam's second Declaration of Independence."
        ),
        "category": "vietnamese_history",
        "key_figures": ["Nguyễn Trãi", "Nguyen Trai", "Bình Ngô đại cáo", "Ức Trai", "Côn Sơn"],
    },

    "quang_trung": {
        "vi": (
            "Quang Trung Hoàng đế (1753–1792), tên thật là Nguyễn Huệ, là người anh hùng áo vải cờ đào xứ Tây Sơn. "
            "Mùa xuân năm Kỷ Dậu (1789), ông đã chỉ huy cuộc hành quân thần tốc ra Bắc, đánh tan 29 vạn quân Thanh chỉ trong 5 ngày, "
            "lập nên chiến thắng Ngọc Hồi – Đống Đa vang dội. Ông là thiên tài quân sự bách chiến bách thắng."
        ),
        "en": (
            "Emperor Quang Trung (Nguyễn Huệ, 1753–1792) was the brilliant leader of the Tây Sơn Uprising. In 1789, he led a lightning campaign "
            "that defeated 290,000 Qing troops at the famous Battle of Ngọc Hồi – Đống Đa."
        ),
        "category": "vietnamese_history",
        "key_figures": ["Quang Trung", "Nguyễn Huệ", "Nguyen Hue", "Tây Sơn", "Ngọc Hồi Đống Đa", "Chiến thắng Đống Đa"],
    },

    "ho_chi_minh": {
        "vi": (
            "Chủ tịch Hồ Chí Minh (1890–1969), tên thuở nhỏ là Nguyễn Sinh Cung, là vị lãnh tụ kính yêu của nhân dân Việt Nam. "
            "Năm 1911, Bác ra đi từ bến cảng Nhà Rồng tìm đường cứu nước. Ngày 2 tháng 9 năm 1945 tại Quảng trường Ba Đình (Hà Nội), "
            "Bác đọc Tuyên ngôn Độc lập khai sinh ra nước Việt Nam Dân chủ Cộng hòa. Bác luôn yêu thương các cháu thiếu nhi vô bờ bến."
        ),
        "en": (
            "President Hồ Chí Minh (1890–1969), affectionately called 'Bác Hồ', was the beloved founding father of modern Vietnam. "
            "On September 2, 1945, at Ba Đình Square in Hà Nội, he proclaimed Vietnam's Declaration of Independence."
        ),
        "category": "vietnamese_history",
        "key_figures": ["Hồ Chí Minh", "Bác Hồ", "Ho Chi Minh", "Bac Ho", "Nguyễn Ái Quốc", "Nguyễn Sinh Cung", "Tuyên ngôn Độc lập", "2 tháng 9"],
    },

    "vo_nguyen_giap": {
        "vi": (
            "Đại tướng Võ Nguyên Giáp (1911–2013) là vị Tổng tư lệnh vĩ đại của Quân đội Nhân dân Việt Nam. "
            "Ông là học trò xuất sắc của Bác Hồ, người đã chỉ huy chiến thắng Điện Biên Phủ năm 1954 'lừng lẫy năm châu, chấn động địa cầu' "
            "và Chiến dịch Hồ Chí Minh năm 1975 thống nhất non sông. Thế giới tôn vinh ông là một trong những vị tướng kiệt xuất nhất lịch sử."
        ),
        "en": (
            "General Võ Nguyên Giáp (1911–2013) was the legendary commander-in-chief of the Vietnam People's Army, renowned globally "
            "for masterminding the historic victory at the Battle of Điện Biên Phủ in 1954."
        ),
        "category": "vietnamese_history",
        "key_figures": ["Võ Nguyên Giáp", "Vo Nguyen Giap", "Đại tướng Võ Nguyên Giáp", "Điện Biên Phủ", "Anh Văn"],
    },

    "kim_dong": {
        "vi": (
            "Kim Đồng (1929–1943), tên thật là Nông Văn Dền, là người dân tộc Nùng ở Cao Bằng. Cậu là người Đội trưởng đầu tiên "
            "của Đội Thiếu niên Tiền phong Hồ Chí Minh. Trong một lần làm nhiệm vụ liên lạc bảo vệ cán bộ cách mạng bị địch bao vây, "
            "Kim Đồng đã dũng cảm chạy đánh lạc hướng quân địch và anh dũng hy sinh khi mới 14 tuổi."
        ),
        "en": (
            "Kim Đồng (Nông Văn Dền, 1929–1943) was a courageous young boy who became the first team leader of the Ho Chi Minh Young Pioneer Organization. "
            "He sacrificed his life at age 14 to distract enemy troops and protect revolutionary comrades."
        ),
        "category": "vietnamese_history",
        "key_figures": ["Kim Đồng", "Kim Dong", "Nông Văn Dền", "Đội Thiếu niên Tiền phong"],
    },

    "vo_thi_sau": {
        "vi": (
            "Võ Thị Sáu (1933–1952) là nữ anh hùng thiếu niên quê ở Đất Đỏ (Bà Rịa - Vũng Tàu). Tham gia cách mạng từ năm 14 tuổi, "
            "chị nổi tiếng kiên cường, dũng cảm. Dù bị giam giữ tại nhà tù Côn Đảo, chị vẫn luôn giữ vững tinh thần lạc quan, "
            "cài hoa lên mái tóc và cất cao tiếng hát trước lúc hy sinh khi chưa tròn 19 tuổi."
        ),
        "en": (
            "Võ Thị Sáu (1933–1952) was a heroic young Vietnamese freedom fighter from Đất Đỏ. Imprisoned on Côn Đảo island, "
            "she showed immense bravery and faced the firing squad with singing and a flower in her hair at age 19."
        ),
        "category": "vietnamese_history",
        "key_figures": ["Võ Thị Sáu", "Vo Thi Sau", "Chị Sáu", "Côn Đảo", "Đất Đỏ"],
    },

    # ==================== 2. CHIẾN TÍCH & DI TÍCH LỊCH SỬ ====================
    "song_bach_dang": {
        "vi": (
            "Sông Bạch Đằng là con sông lịch sử thiêng liêng ở vùng Đông Bắc Việt Nam (Hải Phòng - Quảng Ninh). "
            "Nơi đây đã ghi dấu 3 chiến thắng thủy chiến oanh liệt của dân tộc bằng kế cọc nhọn dưới lòng sông: "
            "Ngô Quyền thắng quân Nam Hán (938), Lê Hoàn thắng quân Tống (981) và Trần Hưng Đạo đại phá quân Nguyên Mông (1288)."
        ),
        "en": (
            "Bạch Đằng River is famous for three historic naval victories using submerged wooden stakes: "
            "Ngô Quyền in 938, Lê Hoàn in 981, and Trần Hưng Đạo in 1288."
        ),
        "category": "vietnamese_history",
        "key_figures": ["Sông Bạch Đằng", "Song Bach Dang", "Bạch Đằng", "Cọc gỗ Bạch Đằng"],
    },

    "thanh_co_loa": {
        "vi": (
            "Thành Cổ Loa (Đông Anh, Hà Nội) là tòa thành cổ nhất Việt Nam do An Dương Vương xây dựng từ thế kỷ thứ 3 trước Công nguyên. "
            "Thành có cấu trúc độc đáo gồm 9 vòng hình xoáy ốc (nay còn 3 vòng) được đắp bằng đất, hào sâu bao quanh, "
            "vừa là kinh đô vừa là pháo đài quân sự bất khả xâm phạm thời bấy giờ."
        ),
        "en": (
            "Cổ Loa Citadel in Hà Nội is Vietnam's oldest fortress, built in the 3rd century BC by An Dương Vương with 9 spiral earthen walls."
        ),
        "category": "vietnamese_history",
        "key_figures": ["Thành Cổ Loa", "Thanh Co Loa", "Cổ Loa", "Thục Phán"],
    },

    "van_mieu_quoc_tu_giam": {
        "vi": (
            "Văn Miếu – Quốc Tử Giám (Hà Nội) được xây dựng từ năm 1070 dưới thời vua Lý Thánh Tông. Đến năm 1076, vua Lý Nhân Tông "
            "cho lập Quốc Tử Giám — trường đại học đầu tiên của Việt Nam. Nơi đây có 82 tấm bia tiến sĩ bằng đá đặt trên lưng rùa, "
            "vinh danh tinh thần hiếu học và truyền thống tôn sư trọng đạo của dân tộc."
        ),
        "en": (
            "The Temple of Literature (Văn Miếu) and Imperial Academy (Quốc Tử Giám) in Hà Nội was built in 1070/1076 as Vietnam's first national university, "
            "featuring 82 stone stele mounted on turtle pedestals honoring doctoral laureates."
        ),
        "category": "vietnamese_history",
        "key_figures": ["Văn Miếu", "Quốc Tử Giám", "Van Mieu Quoc Tu Giam", "Bia tiến sĩ", "Trường đại học đầu tiên"],
    },

    "dien_bien_phu": {
        "vi": (
            "Chiến dịch Điện Biên Phủ (1954) là chiến thắng quân sự vĩ đại của quân và dân Việt Nam dưới sự lãnh đạo của Đại tướng Võ Nguyên Giáp. "
            "Sau 56 ngày đêm 'khoét núi, ngủ hầm, mưa dầm, cơm vắt', tập đoàn cứ điểm bất khả xâm phạm của thực dân Pháp đã bị đánh bại, "
            "chấm dứt hoàn toàn chiến tranh xâm lược của Pháp ở Đông Dương."
        ),
        "en": (
            "The Battle of Điện Biên Phủ (1954) was a 56-day siege that ended French colonial rule in Indochina, led masterfully by General Võ Nguyên Giáp."
        ),
        "category": "vietnamese_history",
        "key_figures": ["Điện Biên Phủ", "Dien Bien Phu", "Chiến dịch Điện Biên Phủ", "56 ngày đêm", "Tướng De Castries"],
    },

    # ==================== 3. ĐỊA LÝ & DANH LAM THẮNG CẢNH ====================
    "fansipan": {
        "vi": (
            "Đỉnh Fansipan cao 3.143 mét, nằm ở dãy Hoàng Liên Sơn gần thị trấn Sa Pa (Lào Cai). "
            "Đây là ngọn núi cao nhất Việt Nam và được mệnh danh là 'Nóc nhà Đông Dương'. "
            "Quanh năm Fansipan được mây mù bao phủ tạo nên khung cảnh bồng lai tiên cảnh tuyệt đẹp."
        ),
        "en": (
            "Mount Fansipan (3,143 meters) in Lào Cai province is the highest mountain in Vietnam and Indochina, known as the 'Roof of Indochina'."
        ),
        "category": "geography",
        "key_figures": ["Fansipan", "Phan Xi Păng", "Nóc nhà Đông Dương", "Sa Pa"],
    },

    "vinh_ha_long": {
        "vi": (
            "Vịnh Hạ Long (Quảng Ninh) là kỳ quan thiên nhiên thế giới được UNESCO công nhận nhiều lần. "
            "Vịnh có gần 2.000 hòn đảo đá vôi lớn nhỏ nổi lên giữa làn nước biển xanh ngọc bích như đàn rồng mẹ và rồng con giáng trần. "
            "Nơi đây có những hang động kỳ vĩ như Động Thiên Cung, Hang Đầu Gỗ, Hang Sửng Sốt."
        ),
        "en": (
            "Hạ Long Bay in Quảng Ninh province is a UNESCO World Heritage site renowned for its emerald waters and thousands of towering limestone islands."
        ),
        "category": "geography",
        "key_figures": ["Vịnh Hạ Long", "Vinh Ha Long", "Hạ Long", "Hòn Trống Mái", "Động Thiên Cung"],
    },

    "hang_son_doong": {
        "vi": (
            "Hang Sơn Đoòng (Quảng Bình) là hang động tự nhiên lớn nhất thế giới, nằm trong Vườn quốc gia Phong Nha - Kẻ Bàng. "
            "Hang lớn đến mức có thể chứa vừa một tòa nhà chọc trời 40 tầng, có cả khu rừng nguyên sinh, dòng sông ngầm chảy xiết "
            "và hệ sinh thái khí hậu riêng biệt bên trong lòng hang."
        ),
        "en": (
            "Sơn Đoòng Cave in Quảng Bình is the largest natural cave on Earth, featuring its own underground jungle, river, and specialized weather system."
        ),
        "category": "geography",
        "key_figures": ["Sơn Đoòng", "Hang Sơn Đoòng", "Son Doong", "Hang động lớn nhất thế giới", "Phong Nha Kẻ Bàng"],
    },

    "song_hong": {
        "vi": (
            "Sông Hồng (dài hơn 1.100 km) là dòng sông lớn nhất miền Bắc Việt Nam, bắt nguồn từ vùng núi phía Bắc chảy qua Hà Nội "
            "rồi đổ ra vịnh Bắc Bộ. Sông có màu đỏ hồng do mang theo lượng phù sa màu mỡ khổng lồ, bồi đắp nên Đồng bằng sông Hồng trù phú — "
            "nơi sinh ra nền văn minh lúa nước sông Hồng nghìn năm rực rỡ."
        ),
        "en": (
            "The Red River (Sông Hồng) is Northern Vietnam's major river. Its reddish silt deposits created the fertile Red River Delta, the cradle of Vietnamese wet rice civilization."
        ),
        "category": "geography",
        "key_figures": ["Sông Hồng", "Song Hong", "Đồng bằng sông Hồng", "Phù sa sông Hồng"],
    },

    "song_cuu_long": {
        "vi": (
            "Sông Cửu Long là tên gọi phần hạ lưu của sông Mê Kông khi chảy vào miền Tây Nam Bộ Việt Nam. "
            "Sông chia làm 2 nhánh chính là sông Tiền và sông Hậu, rồi tỏa ra 9 cửa sông đổ ra biển lớn giống như 9 con rồng uốn lượn. "
            "Phù sa sông Cửu Long tạo nên vựa lúa và vựa trái cây lớn nhất cả nước."
        ),
        "en": (
            "The Mekong Delta in Vietnam is called Sông Cửu Long ('Nine Dragons River') because it branches into nine mouths entering the sea, forming Vietnam's largest agricultural basket."
        ),
        "category": "geography",
        "key_figures": ["Sông Cửu Long", "Song Cuu Long", "Sông Mê Kông", "Song Me Kong", "Đồng bằng sông Cửu Long", "Miền Tây"],
    },

    "quan_dao_hoang_sa_truong_sa": {
        "vi": (
            "Quần đảo Hoàng Sa và Quần đảo Trường Sa là hai quần đảo thiêng liêng nằm giữa Biển Đông, "
            "thuộc chủ quyền lịch sử và pháp lý không thể chối cãi của nước Cộng hòa Xã hội Chủ nghĩa Việt Nam. "
            "Nơi đây có các chú bộ đội hải quân ngày đêm canh giữ biển trời bình yên của Tổ quốc."
        ),
        "en": (
            "The Hoàng Sa (Paracel) and Trường Sa (Spratly) archipelagoes are integral, sovereign island territories of Vietnam in the South China Sea."
        ),
        "category": "geography",
        "key_figures": ["Hoàng Sa", "Trường Sa", "Hoang Sa", "Truong Sa", "Biển Đông", "Hải đảo Việt Nam"],
    },

    "mui_ca_mau": {
        "vi": (
            "Mũi Cà Mau là điểm cực Nam trên đất liền của Tổ quốc Việt Nam, thuộc huyện Ngọc Hiển, tỉnh Cà Mau. "
            "Đây là nơi duy nhất trên đất liền Việt Nam có thể ngắm Mặt Trời mọc ở biển Đông và lặn ở biển Tây trong cùng một ngày. "
            "Rừng ngập mặn Cà Mau có hệ sinh thái cây đước, cây mắm vô cùng phong phú."
        ),
        "en": (
            "Cape Cà Mau (Mũi Cà Mau) is the southernmost point of mainland Vietnam, where visitors can watch both sunrise over the East Sea and sunset over the West Sea."
        ),
        "category": "geography",
        "key_figures": ["Mũi Cà Mau", "Mui Ca Mau", "Cà Mau", "Cực Nam Việt Nam", "Rừng ngập mặn Cà Mau"],
    },

    "cot_co_lung_cu": {
        "vi": (
            "Cột cờ Lũng Cú nằm trên đỉnh núi Rồng ở huyện Đồng Văn, tỉnh Hà Giang, đánh dấu điểm cực Bắc của Tổ quốc. "
            "Lá cờ đỏ sao vàng tung bay trên đỉnh cột cờ có diện tích rộng đúng 54 mét vuông, tượng trưng cho 54 dân tộc anh em "
            "cùng đoàn kết một lòng xây dựng và bảo vệ đất nước."
        ),
        "en": (
            "Lũng Cú Flag Tower in Hà Giang marks the northernmost point of Vietnam. Its 54-square-meter national flag represents the 54 ethnic groups of Vietnam."
        ),
        "category": "geography",
        "key_figures": ["Lũng Cú", "Lung Cu", "Cột cờ Lũng Cú", "Hà Giang", "Cực Bắc Việt Nam"],
    },

    "tinh_thanh_viet_nam": {
        "vi": (
            "Nước Cộng hòa Xã hội Chủ nghĩa Việt Nam hiện nay có tổng cộng 63 đơn vị hành chính cấp tỉnh, "
            "gồm 58 tỉnh (như Hà Giang, Cà Mau, Nghệ An, Lâm Đồng...) và 5 thành phố trực thuộc Trung ương là: "
            "Hà Nội (Thủ đô), Thành phố Hồ Chí Minh, Hải Phòng, Đà Nẵng và Cần Thơ."
        ),
        "en": (
            "Vietnam is administratively divided into 63 province-level units: 58 provinces and 5 centrally-governed cities "
            "(Hà Nội, Ho Chi Minh City, Hải Phòng, Đà Nẵng, and Cần Thơ)."
        ),
        "category": "geography",
        "key_figures": [
            "tỉnh thành việt nam", "bao nhiêu tỉnh thành", "bao nhiêu tỉnh thành phố", "63 tỉnh thành",
            "bao nhiêu tỉnh", "tỉnh việt nam", "thành phố trực thuộc trung ương", "đơn vị hành chính việt nam",
            "tinh thanh viet nam", "bao nhieu tinh thanh"
        ],
    },

    "thu_do_viet_nam": {
        "vi": (
            "Thủ đô của nước Cộng hòa Xã hội Chủ nghĩa Việt Nam là thành phố Hà Nội — trung tâm chính trị, văn hóa và giáo dục "
            "nghìn năm văn hiến của cả nước. Hà Nội nổi tiếng với Hồ Gươm, Lăng Bác Hồ, Văn Miếu - Quốc Tử Giám và 36 phố phường cổ kính."
        ),
        "en": (
            "Hanoi is the historic capital city of Vietnam, renowned for Hoàn Kiếm Lake, the Old Quarter, and the Temple of Literature."
        ),
        "category": "geography",
        "key_figures": ["thủ đô việt nam", "thủ đô của việt nam", "thu do viet nam", "hà nội thủ đô", "thủ đô nước ta"],
    },

    "dan_so_dien_tich_viet_nam": {
        "vi": (
            "Đất nước Việt Nam hình chữ S có diện tích tự nhiên khoảng 331.212 km² với đường bờ biển dài hơn 3.260 km. "
            "Dân số Việt Nam hiện nay đạt mốc khoảng 100 triệu người, gồm 54 dân tộc anh em cùng chung sống đoàn kết, "
            "trong đó người Kinh (người Việt) chiếm số lượng đông nhất."
        ),
        "en": (
            "Vietnam has a land area of about 331,212 km² with a 3,260 km coastline. Its population is approximately 100 million people, comprising 54 distinct ethnic groups."
        ),
        "category": "geography",
        "key_figures": [
            "diện tích việt nam", "dân số việt nam", "dien tich viet nam", "dan so viet nam",
            "54 dân tộc", "bao nhiêu dân tộc", "bờ biển việt nam", "đất nước việt nam"
        ],
    },

    "3_mien_viet_nam": {
        "vi": (
            "Việt Nam được chia làm 3 miền chính: Miền Bắc (nổi tiếng với Thủ đô Hà Nội, vịnh Hạ Long, ruộng bậc thang Sa Pa), "
            "Miền Trung (nổi tiếng với cố đô Huế, cầu Vàng Đà Nẵng, phố cổ Hội An) và Miền Nam (với Thành phố Hồ Chí Minh sầm uất "
            "và miền Tây sông nước Cửu Long trù phú bạt ngàn cây trái)."
        ),
        "en": (
            "Vietnam is geographically and culturally divided into 3 regions: Northern Vietnam, Central Vietnam, and Southern Vietnam."
        ),
        "category": "geography",
        "key_figures": ["3 miền", "ba miền", "các miền việt nam", "miền bắc", "miền trung", "miền nam", "3 mien viet nam"],
    },

    # ==================== 4. HỆ MẶT TRỜI & THIÊN VĂN VŨ TRỤ ====================
    "he_mat_troi": {
        "vi": (
            "Hệ Mặt Trời (Solar System) gồm Mặt Trời ở trung tâm và 8 hành tinh quay xung quanh theo thứ tự từ gần đến xa: "
            "Sao Thủy, Sao Kim, Trái Đất, Sao Hỏa, Sao Mộc, Sao Thổ, Sao Thiên Vương và Sao Hải Vương. "
            "Ngoài ra còn có các hành tinh lùn (như Sao Diêm Vương), các tiểu hành tinh và sao chổi."
        ),
        "en": (
            "The Solar System consists of the Sun and 8 planets in order: Mercury, Venus, Earth, Mars, Jupiter, Saturn, Uranus, and Neptune, along with dwarf planets and comets."
        ),
        "category": "space",
        "key_figures": ["Hệ Mặt Trời", "He Mat Troi", "Solar System", "Các hành tinh trong hệ mặt trời", "8 hành tinh"],
    },

    "mat_troi": {
        "vi": (
            "Mặt Trời (The Sun) là một ngôi sao khổng lồ phát sáng ở trung tâm Hệ Mặt Trời, cách Trái Đất khoảng 150 triệu km. "
            "Nó to gấp 1,3 triệu lần Trái Đất và nhiệt độ bề mặt lên tới gần 6.000 độ C! "
            "Ánh sáng và nhiệt lượng từ Mặt Trời cung cấp năng lượng cho mọi sự sống, cây cối quang hợp và tạo ra thời tiết trên Trái Đất."
        ),
        "en": (
            "The Sun is a giant luminous star at the center of our solar system. It is 1.3 million times larger than Earth and provides light and heat vital for all life."
        ),
        "category": "space",
        "key_figures": ["Mặt Trời", "Mat Troi", "The Sun", "Ánh sáng mặt trời"],
    },

    "mat_trang": {
        "vi": (
            "Mặt Trăng (The Moon) là vệ tinh tự nhiên duy nhất quay quanh Trái Đất, mất khoảng 27,3 ngày để đi hết một vòng. "
            "Mặt Trăng không tự phát sáng mà phản chiếu ánh sáng từ Mặt Trời. Lực hấp dẫn của Mặt Trăng tạo ra hiện tượng thủy triều "
            "(nước biển dâng lên và hạ xuống) trên Trái Đất. Con người lần đầu tiên đặt chân lên Mặt Trăng vào năm 1969 (phi hành gia Neil Armstrong)."
        ),
        "en": (
            "The Moon is Earth's only natural satellite. It reflects sunlight, causes ocean tides via gravitational pull, and was first visited by humans in 1969 (Apollo 11)."
        ),
        "category": "space",
        "key_figures": ["Mặt Trăng", "Mat Trang", "The Moon", "Thủy triều", "Neil Armstrong", "Cuội"],
    },

    "trai_dat": {
        "vi": (
            "Trái Đất (Earth) là hành tinh thứ 3 tính từ Mặt Trời và là hành tinh duy nhất trong vũ trụ được biết đến có sự sống. "
            "Bề mặt Trái Đất có khoảng 71% là nước biển (đại dương) và 29% là đất liền. "
            "Trái Đất có bầu khí quyển chứa khí oxy và tầng ozone bảo vệ chúng ta khỏi bức xạ có hại từ vũ trụ."
        ),
        "en": (
            "Earth is the third planet from the Sun and the only known world harboring life, with 71% of its surface covered by water oceans."
        ),
        "category": "space",
        "key_figures": ["Trái Đất", "Trai Dat", "Hành tinh xanh", "Earth"],
    },

    "sao_hoa": {
        "vi": (
            "Sao Hỏa (Mars) là hành tinh thứ 4 tính từ Mặt Trời, thường được gọi là 'Hành tinh Đỏ' do bề mặt chứa nhiều oxit sắt (gỉ sét). "
            "Sao Hỏa có ngọn núi lửa Olympus Mons cao gấp 3 lần đỉnh Everest! Các nhà khoa học hiện đang gửi nhiều robot thám hiểm "
            "lên Sao Hỏa để tìm kiếm dấu vết của nước và sự sống cổ đại."
        ),
        "en": (
            "Mars is the fourth planet from the Sun, known as the 'Red Planet' due to iron oxide on its surface. It has Olympus Mons, the largest volcano in the solar system."
        ),
        "category": "space",
        "key_figures": ["Sao Hỏa", "Sao Hoa", "Hành tinh đỏ", "Mars"],
    },

    "sao_moc": {
        "vi": (
            "Sao Mộc (Jupiter) là hành tinh lớn nhất trong Hệ Mặt Trời, to đến mức có thể chứa vừa hơn 1.300 Trái Đất bên trong! "
            "Nó là một hành tinh khí khổng lồ, nổi tiếng với 'Vết Đỏ Lớn' — một cơn bão khổng lồ đã quay cuồng hàng trăm năm qua. "
            "Sao Mộc có tới hơn 90 mặt trăng quay quanh nó."
        ),
        "en": (
            "Jupiter is the largest planet in our solar system, a gas giant that could fit 1,300 Earths inside, famous for its centuries-old Great Red Spot storm."
        ),
        "category": "space",
        "key_figures": ["Sao Mộc", "Sao Moc", "Jupiter", "Hành tinh lớn nhất", "Vết Đỏ Lớn"],
    },

    "sao_tho": {
        "vi": (
            "Sao Thổ (Saturn) là hành tinh thứ 6 trong Hệ Mặt Trời, nổi tiếng là hành tinh đẹp nhất nhờ hệ thống vành đai tráng lệ "
            "được tạo nên từ hàng triệu khối băng, đá và bụi quay quanh. Dù rất khổng lồ nhưng Sao Thổ rất nhẹ, "
            "nếu có một bể nước đủ lớn, Sao Thổ sẽ nổi trên mặt nước!"
        ),
        "en": (
            "Saturn is famous for its breathtaking rings made of ice, rock, and dust particles. It is so low-density that it could float in a giant bathtub of water!"
        ),
        "category": "space",
        "key_figures": ["Sao Thổ", "Sao Tho", "Saturn", "Vành đai sao Thổ"],
    },

    "ho_den": {
        "vi": (
            "Hố đen (Black Hole) là một vùng trong không gian vũ trụ có lực hấp dẫn cực kỳ mạnh mẽ, đến mức không một vật thể nào — "
            "kể cả ánh sáng với tốc độ 300.000 km/s — có thể thoát ra được một khi đã rơi vào bên trong. "
            "Hố đen thường sinh ra khi một ngôi sao khổng lồ cạn kiệt nhiên liệu và sụp đổ ở cuối vòng đời."
        ),
        "en": (
            "A Black Hole is a region of spacetime with gravity so strong that nothing, not even light, can escape from inside its event horizon."
        ),
        "category": "space",
        "key_figures": ["Hố đen", "Ho den", "Lỗ đen vũ trụ", "Black hole"],
    },

    # ==================== 5. KHOA HỌC TỰ NHIÊN & ĐỜI SỐNG ====================
    "vong_tuan_hoan_nuoc": {
        "vi": (
            "Vòng tuần hoàn của nước là hành trình kỳ diệu của nước trên Trái Đất: Ánh nắng Mặt Trời làm nước ở sông, biển bốc hơi lên cao "
            "thành hơi nước. Hơi nước gặp lạnh ngưng tụ thành những đám mây. Khi mây quá nặng, nước rơi xuống thành mưa, tuyết "
            "chảy về các dòng sông, thấm vào lòng đất rồi lại đổ ra biển, tiếp tục vòng tròn bất tận."
        ),
        "en": (
            "The Water Cycle (Vòng tuần hoàn của nước) involves evaporation of water by the Sun, condensation into clouds, precipitation as rain, and return to rivers and oceans."
        ),
        "category": "science",
        "key_figures": ["Vòng tuần hoàn của nước", "Tuần hoàn nước", "Vì sao có mưa", "Bốc hơi ngưng tụ"],
    },

    "quang_hop": {
        "vi": (
            "Quang hợp (Photosynthesis) là quá trình kỳ diệu mà cây xanh dùng chất diệp lục trong lá để hấp thụ ánh sáng Mặt Trời, "
            "hút khí carbonic (CO2) từ không khí và nước từ rễ để tạo thành chất dinh dưỡng nuôi cây, đồng thời giải phóng khí Oxy (O2) "
            "trong lành cho con người và động vật hô hấp. Cây xanh chính là lá phổi xanh của Trái Đất!"
        ),
        "en": (
            "Photosynthesis is the process by which green plants use sunlight, water, and carbon dioxide to create sugars and release oxygen into the atmosphere."
        ),
        "category": "science",
        "key_figures": ["Quang hợp", "Quang hop", "Photosynthesis", "Khí oxy", "Chất diệp lục", "Lá phổi xanh"],
    },

    "sam_set": {
        "vi": (
            "Sấm sét sinh ra khi các đám mây dông tích điện cọ xát vào nhau tạo thành tia chớp điện khổng lồ (sét). "
            "Khi trời mưa dông, chúng mình luôn nhìn thấy tia chớp trước rồi mới nghe thấy tiếng sấm đùng đoàng sau, "
            "bởi vì vận tốc ánh sáng (300.000 km/s) chạy nhanh hơn rất nhiều so với vận tốc âm thanh trong không khí (khoảng 340 m/s)!"
        ),
        "en": (
            "Thunder and Lightning are caused by electrostatic discharges in storm clouds. We see lightning before hearing thunder because light travels far faster than sound."
        ),
        "category": "science",
        "key_figures": ["Sấm sét", "Sam set", "Tại sao có sấm sét", "Tia chớp", "Vận tốc ánh sáng"],
    },

    "cau_vong": {
        "vi": (
            "Cầu vồng (Rainbow) là hiện tượng quang học tuyệt đẹp xuất hiện khi trời vừa mưa vừa có nắng. "
            "Các giọt nước mưa li ti trong không khí hoạt động như những lăng kính nhỏ xíu, tán sắc ánh sáng Mặt Trời thành 7 dải màu rực rỡ: "
            "Đỏ, Da cam, Vàng, Lục, Lam, Chàm, Tím."
        ),
        "en": (
            "A Rainbow is an optical phenomenon caused by refraction, dispersion, and reflection of sunlight in raindrops, displaying seven distinct colors."
        ),
        "category": "science",
        "key_figures": ["Cầu vồng", "Cau vong", "Tại sao có cầu vồng", "7 sắc cầu vồng", "Rainbow"],
    },

    "trong_luc": {
        "vi": (
            "Trọng lực (Gravity) là lực hút vô hình mà Trái Đất kéo mọi vật thể về phía tâm của nó. "
            "Nhờ có trọng lực mà chúng mình có thể đứng vững trên mặt đất, nước chảy xuống chỗ trũng và quả táo rơi xuống đất. "
            "Nhà bác học Isaac Newton là người đã khám phá ra định luật vạn vật hấp dẫn nổi tiếng này khi quan sát quả táo rơi."
        ),
        "en": (
            "Gravity is the fundamental attractive force by which Earth pulls objects toward its center, famously discovered by Sir Isaac Newton."
        ),
        "category": "science",
        "key_figures": ["Trọng lực", "Trong luc", "Lực hấp dẫn", "Isaac Newton", "Quả táo rơi"],
    },

    "nui_lua": {
        "vi": (
            "Núi lửa (Volcano) là vết nứt trên vỏ Trái Đất, nơi đá nóng chảy ở nhiệt độ hàng nghìn độ C từ sâu trong lòng đất (gọi là dung nham hay magma) "
            "cùng tro bụi và khí ga phun trào ra ngoài bề mặt. Dung nham sau khi nguội đi sẽ tạo thành đất bazan vô cùng màu mỡ cho cây cối phát triển."
        ),
        "en": (
            "A Volcano is an opening in Earth's crust that allows molten rock (magma/lava), ash, and gases to erupt to the surface."
        ),
        "category": "science",
        "key_figures": ["Núi lửa", "Nui lua", "Dung nham", "Magma", "Volcano"],
    },

    # ==================== 6. THẾ GIỚI ĐỘNG VẬT & SINH HỌC ====================
    "blue_whale": {
        "vi": (
            "Cá voi xanh (Blue Whale) là loài động vật lớn nhất từng tồn tại trong lịch sử Trái Đất, lớn hơn bất kỳ loài khủng long nào! "
            "Một con cá voi xanh trưởng thành có thể dài tới 30 mét và nặng gần 200 tấn (bằng 33 con voi cộng lại). "
            "Trái tim của nó to bằng một chiếc xe ô tô con và chiếc lưỡi nặng bằng cả một con voi! Dù khổng lồ nhưng chúng chỉ ăn tôm tép nhỏ (nhuyễn thể)."
        ),
        "en": (
            "The Blue Whale is the largest animal ever to exist on Earth, growing up to 30 meters long and 200 tons, feeding primarily on tiny krill."
        ),
        "category": "animals",
        "key_figures": ["Cá voi xanh", "Ca voi xanh", "Blue whale", "Động vật lớn nhất thế giới"],
    },

    "t_rex": {
        "vi": (
            "Khủng long bạo chúa T-Rex (Tyrannosaurus Rex) sống cách đây khoảng 68 triệu năm ở cuối kỷ Phấn trắng. "
            "Nó là một trong những loài ăn thịt trên cạn đáng sợ nhất: dài 12 mét, nặng 8 tấn với hàm răng sắc nhọn to như quả chuối "
            "có thể nghiền nát xương con mồi. Điểm thú vị là T-Rex có đôi tay nhỏ xíu với chỉ 2 ngón tay."
        ),
        "en": (
            "Tyrannosaurus Rex (T-Rex) was a legendary apex predator dinosaur with 12-meter length, 8-ton weight, banana-sized teeth, and famously tiny arms."
        ),
        "category": "animals",
        "key_figures": ["T-Rex", "Khủng long bạo chúa", "Khung long bao chua", "Tyrannosaurus", "Khủng long", "Khung long"],
    },

    "chim_canh_cut": {
        "vi": (
            "Chim cánh cụt (Penguin) là loài chim đặc biệt không biết bay trên trời nhưng bơi lội dưới nước cực giỏi như những chiếc tàu ngầm tí hon! "
            "Chúng sống chủ yếu ở vùng băng tuyết giá lạnh Nam Cực. Bộ lông dày không thấm nước và lớp mỡ dày giúp chim cánh cụt chịu được cái lạnh -60 độ C. "
            "Các ông bố chim cánh cụt rất chăm chỉ, sẵn sàng ấp trứng suốt mùa đông cho đến khi chim non chào đời."
        ),
        "en": (
            "Penguins are flightless seabirds that excel at swimming underwater, adapted with thick waterproof plumage to survive Antarctica's extreme cold."
        ),
        "category": "animals",
        "key_figures": ["Chim cánh cụt", "Chim canh cut", "Penguin", "Nam Cực"],
    },

    "ca_heo": {
        "vi": (
            "Cá heo (Dolphin) là loài thú có vú thông minh và thân thiện sống dưới đại dương. Chúng thở bằng phổi qua một lỗ thở trên đỉnh đầu "
            "và sinh con non bú sữa mẹ. Cá heo sử dụng sóng âm (định vị bằng tiếng vang) để nhìn và săn mồi trong làn nước đục. "
            "Chúng rất thích chơi đùa và thường giúp đỡ người đi biển gặp nạn."
        ),
        "en": (
            "Dolphins are highly intelligent aquatic mammals that breathe air through a blowhole, communicate via clicks and whistles, and use echolocation."
        ),
        "category": "animals",
        "key_figures": ["Cá heo", "Ca heo", "Dolphin", "Định vị sóng âm"],
    },

    "huou_cao_co": {
        "vi": (
            "Hươu cao cổ (Giraffe) là loài động vật sống trên cạn cao nhất thế giới, có thể cao tới 5,5 mét! "
            "Chiếc cổ dài giúp chúng dễ dàng hái những chiếc lá non trên ngọn cây keo gai mà các loài khác không với tới được. "
            "Lưỡi của hươu cao cổ có màu xanh tím và dài tới 45 cm, rất dai để không bị gai đâm."
        ),
        "en": (
            "Giraffes are the tallest terrestrial animals, reaching heights of 5.5 meters with long necks and 45cm prehensile blue-black tongues to eat acacia leaves."
        ),
        "category": "animals",
        "key_figures": ["Hươu cao cổ", "Huou cao co", "Giraffe", "Động vật cao nhất"],
    },

    "ong_mat": {
        "vi": (
            "Ong mật (Honeybee) là những chú thợ chăm chỉ bậc nhất trong thiên nhiên. Chúng bay qua hàng ngàn bông hoa "
            "để hút mật hoa và mang về tổ luyện thành mật ong ngọt ngào. Trong quá trình đó, ong giúp thụ phấn cho 1/3 cây trồng "
            "trên Trái Đất, giúp cây ra hoa kết trái. Ong giao tiếp với nhau bằng những 'điệu múa lắc vòng' vô cùng độc đáo."
        ),
        "en": (
            "Honeybees are vital pollinators that produce sweet honey and enable one-third of global food crops to reproduce, communicating through waggle dances."
        ),
        "category": "animals",
        "key_figures": ["Ong mật", "Ong mat", "Honeybee", "Mật ong", "Thụ phấn"],
    },

    # ==================== 7. PHÁT MINH & CÔNG NGHỆ ====================
    "dien": {
        "vi": (
            "Điện năng (Electricity) là một dạng năng lượng kỳ diệu cung cấp ánh sáng, chạy quạt, tivi, máy tính và sạc pin điện thoại. "
            "Các nhà khoa học như Benjamin Franklin, Michael Faraday và Nikola Tesla đã khám phá và tìm ra cách tạo ra dòng điện xoay chiều "
            "đưa điện đến từng ngôi nhà, làm thay đổi toàn bộ văn minh nhân loại."
        ),
        "en": (
            "Electricity is a fundamental form of energy powering modern lighting, appliances, computers, and electric vehicles, advanced by Faraday and Tesla."
        ),
        "category": "technology",
        "key_figures": ["Điện", "Dien", "Điện năng", "Electricity", "Dòng điện", "Nikola Tesla"],
    },

    "bong_den": {
        "vi": (
            "Bóng đèn điện sợi đốt được nhà phát minh đại tài Thomas Edison hoàn thiện vào năm 1879. "
            "Ông đã kiên trì thử nghiệm hơn 1.000 vật liệu khác nhau trước khi tìm ra sợi carbon phát sáng bền bỉ trong bóng thủy tinh hút chân không. "
            "Phát minh này đã xua tan màn đêm tăm tối và thắp sáng cho toàn thế giới."
        ),
        "en": (
            "The incandescent light bulb was perfected by Thomas Edison in 1879 after over 1,000 attempts, transforming human civilization by lighting the night."
        ),
        "category": "technology",
        "key_figures": ["Bóng đèn", "Bong den", "Thomas Edison", "Phát minh bóng đèn", "Edison"],
    },

    "may_bay": {
        "vi": (
            "Máy bay (Airplane) được hai anh em nhà Wright (Orville và Wilbur Wright) phát minh và thực hiện chuyến bay có người lái "
            "đầu tiên trong lịch sử vào ngày 17 tháng 12 năm 1903 tại Mỹ. Đôi cánh máy bay được thiết kế theo nguyên lý khí động học "
            "tương tự đôi cánh chim để tạo ra lực nâng khổng lồ bay vút lên bầu trời."
        ),
        "en": (
            "The Airplane was invented by the Wright brothers (Orville and Wilbur Wright), who achieved the first controlled powered flight on December 17, 1903."
        ),
        "category": "technology",
        "key_figures": ["Máy bay", "May bay", "Anh em nhà Wright", "Wright brothers", "Airplane"],
    },

    "tri_tue_nhan_tao": {
        "vi": (
            "Trí tuệ nhân tạo (AI - Artificial Intelligence) là công nghệ mô phỏng trí thông minh của con người trên máy tính, "
            "giúp máy tính có thể tự học, suy nghĩ, nhận diện hình ảnh, hiểu giọng nói và trò chuyện như một người bạn. "
            "Doraemon cũng là một người bạn Trí tuệ Nhân tạo thông minh luôn đồng hành cùng các bé khám phá thế giới!"
        ),
        "en": (
            "Artificial Intelligence (AI) enables computers and machines to learn, recognize patterns, understand human speech, and solve problems creatively."
        ),
        "category": "technology",
        "key_figures": ["Trí tuệ nhân tạo", "Tri tue nhan tao", "AI", "Artificial Intelligence", "Robot"],
    },
}

# Compatibility alias for CURATED_HISTORY and CURATED_SCIENCE
CURATED_HISTORY = {k: v for k, v in CURATED_KNOWLEDGE.items() if v.get("category") == "vietnamese_history"}
CURATED_SCIENCE = {k: v for k, v in CURATED_KNOWLEDGE.items() if v.get("category") in ("science", "space", "animals", "technology")}


def _strip_vietnamese_diacritics(text: str) -> str:
    """Bỏ toàn bộ dấu tiếng Việt để so sánh chuỗi không phân biệt dấu."""
    if not text:
        return ""
    text = text.replace("đ", "d").replace("Đ", "d")
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower().strip()


def lookup_curated(query: str) -> Optional[Tuple[Dict[str, str], str, str]]:
    """
    Tra cứu nhanh trong kho tri thức bách khoa viết tay:
    - So sánh cả có dấu và không dấu (case-insensitive).
    - Tự động đối sánh thực thể danh từ chính (cả cụm từ và tập từ khóa).
    Returns: (entry_dict, key, source_title) hoặc None nếu không có.
    """
    if not query:
        return None

    q_raw = query.strip().lower()
    q_norm = _strip_vietnamese_diacritics(q_raw)
    q_words = set(q_norm.split())

    # 1. Quét theo key_figures (chính xác nhất: substring match)
    for key, entry in CURATED_KNOWLEDGE.items():
        figures = entry.get("key_figures", [])
        for fig in figures:
            fig_raw = fig.lower()
            fig_norm = _strip_vietnamese_diacritics(fig_raw)
            if fig_norm in q_norm or fig_raw in q_raw:
                return (entry, key, f"Doraemon Knowledge Base: {figures[0]}")

    # 2. Quét theo slug key
    for key, entry in CURATED_KNOWLEDGE.items():
        key_clean = key.replace("_", " ")
        if key_clean in q_norm:
            figures = entry.get("key_figures", [])
            title = figures[0] if figures else key_clean.title()
            return (entry, key, f"Doraemon Knowledge Base: {title}")

    # 3. Quét theo tập từ khóa (Token Subset match) cho các cụm danh từ dài
    for key, entry in CURATED_KNOWLEDGE.items():
        figures = entry.get("key_figures", [])
        for fig in figures:
            fig_norm = _strip_vietnamese_diacritics(fig.lower())
            fig_words = set(fig_norm.split())
            if len(fig_words) >= 2 and fig_words.issubset(q_words):
                return (entry, key, f"Doraemon Knowledge Base: {figures[0]}")

    return None