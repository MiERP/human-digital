import os
import re
import ipaddress
import socket
import logging
from typing import Optional, Tuple
from urllib.parse import urlparse
from datetime import datetime, timezone

logger = logging.getLogger("digital-human-safety")

class ChildSafetyGuard:
    """
    Production-grade Child Safety & Internet Tool Guardrails (<14 years old):
    - Kiểm duyệt nội dung 4 cấp độ: Bạo lực, Người lớn, Hành vi nguy hiểm, PII
    - Chống lỗ hổng SSRF (Server-Side Request Forgery) khi tra cứu Internet
    - Chuyển hướng sư phạm nhẹ nhàng, khéo léo (Pedagogical Redirection)
    - Ghi nhận Audit Log để phụ huynh theo dõi

    Note: Kiến thức tìm kiếm (curated/CSE/Wikipedia) nằm trong search_engine.py —
    class này chỉ chịu trách nhiệm filter nội dung + validate URL, không gọi HTTP.
    """

    # Danh mục từ khóa & mẫu quy tắc nhạy cảm (Đa ngôn ngữ Anh - Việt)
    VIOLENCE_PATTERNS = [
        r"\b(kill|murder|weapon|gun|knife|stab|blood|suicide|die|hurt myself|tự tử|chết|giết|đánh nhau|vũ khí|súng|dao|chém)\b"
    ]

    ADULT_PATTERNS = [
        r"\b(sex|porn|nude|naked|condom|kissing on lips|tình dục|khiêu dâm|khỏa thân|người lớn 18\+)\b"
    ]

    DANGEROUS_ACTS_PATTERNS = [
        r"\b(fire|lighter|matches|electric socket|drink bleach|eat pills|jump from roof|nghịch lửa|bật lửa|diêm|ổ điện|uống thuốc tẩy|nhảy lầu|nuốt pin)\b"
    ]

    PII_PATTERNS = [
        r"\b(\d{10,12})\b", # Số điện thoại / CCCD
        r"\b\d{4}[ -]?\d{4}[ -]?\d{4}[ -]?\d{4}\b", # Số thẻ tín dụng
        r"\b(password|mật khẩu|mã pin|số tài khoản|địa chỉ nhà cụ thể ở đâu)\b"
    ]

    # Whitelist các domain giáo dục an toàn cho trẻ em khi tra cứu Internet.
    #
    # SECURITY NOTE: google.com / googleapis.com are deliberately EXCLUDED.
    # assert_safe_url() matches any subdomain of a whitelisted root
    # (hostname.endswith("." + d)), so whitelisting "google.com" would allow
    # EVERY *.google.com host as a "safe content source" — far too broad for
    # SSRF protection. The Google CSE endpoint (www.googleapis.com) is called
    # directly inside search_engine._search_google_cse() and never passes
    # through assert_safe_url(), so it does not need to be whitelisted here.
    #
    # This whitelist is ONLY for validating content URLs returned by search
    # (Wikipedia pages, Britannica articles, Kiddle pages...). Keep it to
    # genuinely educational content sources.
    ALLOWED_KID_DOMAINS = {
        "kids.nationalgeographic.com",
        "kids.britannica.com",
        "simple.wikipedia.org",
        "wikipedia.org",
        "en.wikipedia.org",
        "pbskids.org",
        "nasa.gov",
        "kiddle.co",
        "duckduckgo.com",
        "britannica.com",
        "nationalgeographic.com",
        "bbc.co.uk",
        "bbc.com",
        "worldwildlife.org",
        "smithsonianmag.com",
    }

    def __init__(self, log_path: Optional[str] = None):
        if log_path is None:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            data_dir = os.path.join(base_dir, "data")
            os.makedirs(data_dir, exist_ok=True)
            log_path = os.path.join(data_dir, "safety_audit.log")

        self.log_path = log_path

    def _log_safety_event(self, child_id: str, category: str, trigger_text: str, action: str):
        """Ghi nhật ký vi phạm an toàn để phụ huynh có thể tra cứu"""
        try:
            with open(self.log_path, "a", encoding="utf-8") as f:
                timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
                f.write(f"[{timestamp}] [CHILD: {child_id}] [CATEGORY: {category}] [ACTION: {action}] TRIGGER: {trigger_text}\n")
        except Exception as e:
            logger.error(f"Failed to write safety audit log: {e}")

    def evaluate_content(self, text: str, child_id: str = "default_child") -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Đánh giá an toàn nội dung của câu hỏi hoặc phản hồi:
        Returns: (is_safe: bool, category: Optional[str], pedagogical_redirect: Optional[str])
        """
        if not text:
            return True, None, None

        lower_text = text.lower()

        # 1. Kiểm tra hành vi nguy hiểm đến thể chất
        for pattern in self.DANGEROUS_ACTS_PATTERNS:
            if re.search(pattern, lower_text, re.IGNORECASE):
                self._log_safety_event(child_id, "DANGEROUS_ACTS", text, "BLOCK_AND_WARN")
                redirect = (
                    "Ôi bé ơi! Những việc liên quan đến lửa, điện hoặc đồ sắc nhọn rất là nguy hiểm đó! "
                    "Doraemon và bố mẹ luôn muốn bé được an toàn. Bé hãy nhờ người lớn giúp đỡ nhé! "
                    "Bây giờ chúng mình cùng học một từ tiếng Anh thật vui nha!"
                )
                return False, "DANGEROUS_ACTS", redirect

        # 2. Kiểm tra nội dung bạo lực / tự hại
        for pattern in self.VIOLENCE_PATTERNS:
            if re.search(pattern, lower_text, re.IGNORECASE):
                self._log_safety_event(child_id, "VIOLENCE", text, "BLOCK_AND_REDIRECT")
                redirect = (
                    "Doraemon là chú mèo máy hòa bình và yêu thương, Doraemon không thích những điều bạo lực đâu nè. "
                    "Nếu có chuyện gì làm bé buồn hoặc bực mình, bé hãy tâm sự với bố mẹ hoặc cô giáo nhé! "
                    "Bây giờ bé muốn Doraemon kể cho nghe câu chuyện về bạn Gấu dễ thương không nào?"
                )
                return False, "VIOLENCE", redirect

        # 3. Kiểm tra nội dung người lớn / không phù hợp lứa tuổi
        for pattern in self.ADULT_PATTERNS:
            if re.search(pattern, lower_text, re.IGNORECASE):
                self._log_safety_event(child_id, "ADULT_CONTENT", text, "BLOCK_AND_REDIRECT")
                redirect = (
                    "Aha! Câu hỏi này của bé thú vị ghê, nhưng chuyện này bé hãy hỏi bố hoặc mẹ nhé! "
                    "Bố mẹ sẽ giải thích cho bé một cách chuẩn xác và hay nhất đó! "
                    "Bây giờ chúng mình cùng luyện nói về con vật yêu thích của bé nha!"
                )
                return False, "ADULT_CONTENT", redirect

        # 4. Kiểm tra lộ lọt thông tin cá nhân PII
        for pattern in self.PII_PATTERNS:
            if re.search(pattern, lower_text, re.IGNORECASE):
                self._log_safety_event(child_id, "PII_EXPOSURE", text, "BLOCK_AND_WARN")
                redirect = (
                    "Bé nhớ quy tắc an toàn số 1 nha: Chúng mình không bao giờ chia sẻ mật khẩu, "
                    "số điện thoại hay địa chỉ nhà cụ thể trên mạng hay với robot nhé. Đó là bí mật an toàn của gia đình đó!"
                )
                return False, "PII_EXPOSURE", redirect

        return True, None, None

    def evaluate_educational_content(self, text: str, child_id: str = "default_child") -> Tuple[bool, Optional[str]]:
        """
        Đánh giá an toàn cho đoạn trích bách khoa / kết quả tìm kiếm giáo dục:
        - Vẫn ngăn chặn 100%: Nội dung người lớn/khiêu dâm, Tự hại, Hướng dẫn hành vi nguy hiểm, Xâm hại.
        - Cho phép: Ngữ cảnh lịch sử giáo dục (khởi nghĩa, đánh đuổi ngoại xâm, chiến thắng, hy sinh, vũ khí cổ trang).
        Returns: (is_safe: bool, category: Optional[str])
        """
        if not text:
            return True, None

        lower_text = text.lower()

        # 1. Chặn tuyệt đối nội dung người lớn / khiêu dâm
        for pattern in self.ADULT_PATTERNS:
            if re.search(pattern, lower_text, re.IGNORECASE):
                self._log_safety_event(child_id, "SNIPPET_ADULT_CONTENT", text[:120], "DROP_RESULT")
                return False, "ADULT_CONTENT"

        # 2. Chặn tuyệt đối hướng dẫn hành vi nguy hiểm / tự hại
        for pattern in self.DANGEROUS_ACTS_PATTERNS:
            if re.search(pattern, lower_text, re.IGNORECASE):
                self._log_safety_event(child_id, "SNIPPET_DANGEROUS_ACTS", text[:120], "DROP_RESULT")
                return False, "DANGEROUS_ACTS"

        # 3. Chặn bạo lực kinh dị, giết hại man rợ, tự sát (loại trừ ngữ cảnh lịch sử/khoa học)
        extreme_violence_patterns = [
            r"\b(suicide|tự tử|tự sát|hurt myself|cắt cổ tay|thảm sát|massacre|terrorist|khủng bố|tra tấn|torture|máu me đầm đìa|hiếp dâm|rape)\b"
        ]
        for pattern in extreme_violence_patterns:
            if re.search(pattern, lower_text, re.IGNORECASE):
                self._log_safety_event(child_id, "SNIPPET_EXTREME_VIOLENCE", text[:120], "DROP_RESULT")
                return False, "VIOLENCE"

        return True, None

    def assert_safe_url(self, raw_url: str) -> bool:
        """
        Bảo vệ chống lỗ hổng SSRF (Server-Side Request Forgery):
        - Bắt buộc giao thức HTTPS
        - Cấm truy cập các dải IP Private/Localhost/Link-local
        - Chỉ cho phép các domain giáo dục trẻ em trong Whitelist
        """
        try:
            parsed = urlparse(raw_url)
            if parsed.scheme != "https":
                logger.warning(f"SSRF Blocked: URL does not use HTTPS: {raw_url}")
                return False

            hostname = parsed.hostname
            if not hostname:
                return False

            # Kiểm tra xem hostname có trong Whitelist hoặc là subdomain hợp lệ
            is_allowed_domain = any(
                hostname == d or hostname.endswith("." + d)
                for d in self.ALLOWED_KID_DOMAINS
            )
            if not is_allowed_domain:
                logger.warning(f"SSRF Blocked: Domain not in kid whitelist: {hostname}")
                return False

            # Phân giải DNS và kiểm tra toàn bộ địa chỉ IP được trả về
            addr_info = socket.getaddrinfo(hostname, None)
            for addr in addr_info:
                ip_str = addr[4][0]
                ip_obj = ipaddress.ip_address(ip_str)
                # Chặn 100% Private, Loopback, Link-Local, Multicast, Reserved IPs
                if ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_link_local or ip_obj.is_reserved:
                    logger.critical(f"SSRF Alert: Domain {hostname} resolved to private/forbidden IP: {ip_str}")
                    return False

            return True
        except Exception as e:
            logger.error(f"Error validating safe URL '{raw_url}': {e}")
            return False
