import unittest
import time
from backend.key_pool import KeyPoolManager, KeyInfo

class TestKeyPoolManager(unittest.TestCase):

    def test_key_parsing_and_filtering(self):
        """Kiểm tra parse danh sách key dạng chuỗi phẩy, lọc key rác và placeholder."""
        raw = "AIzaSy_KEY_ONE_123456789, AIzaSy_YOUR_GEMINI_API_KEY_HERE, AIzaSy_KEY_TWO_987654321; AIzaSy_KEY_THREE_5555555"
        pool = KeyPoolManager(raw_keys=raw)
        self.assertEqual(pool.total_keys, 3)
        status = pool.get_pool_status()
        self.assertEqual(status["total_keys"], 3)
        self.assertEqual(status["healthy_keys"], 3)

    def test_least_active_connections_balancing(self):
        """Kiểm tra cân bằng tải theo số lượng kết nối đang hoạt động ít nhất."""
        raw = "AIzaSy_KEY_A_111111111, AIzaSy_KEY_B_222222222, AIzaSy_KEY_C_333333333"
        pool = KeyPoolManager(raw_keys=raw)

        # Lấy 3 key cho 3 phiên
        k1 = pool.acquire_key()
        k2 = pool.acquire_key()
        k3 = pool.acquire_key()

        # Mỗi key phải được gán 1 phiên
        keys_assigned = {k1, k2, k3}
        self.assertEqual(len(keys_assigned), 3)

        # Phiên thứ 4 sẽ gán vào key có total_sessions thấp nhất hoặc round-robin
        k4 = pool.acquire_key()
        self.assertIn(k4, keys_assigned)

        # Giải phóng k1 2 lần (k1 từ 2 xuống 0 kết nối)
        pool.release_key(k1)
        pool.release_key(k1)
        # Phiên thứ 5 chắc chắn chọn k1 vì k1 có active_connections = 0 trong khi k2, k3 có active_connections = 1
        k5 = pool.acquire_key()
        self.assertEqual(k5, k1)

    def test_cooldown_and_failover(self):
        """Kiểm tra tự động cooldown key khi gặp lỗi 429 và failover sang key khác."""
        raw = "AIzaSy_KEY_FAILING_11111, AIzaSy_KEY_HEALTHY_22222"
        pool = KeyPoolManager(raw_keys=raw)

        k1 = pool.acquire_key()
        # Giả lập k1 bị lỗi 429 Quota
        pool.report_quota_error(k1, cooldown_seconds=10.0)

        # Phiên tiếp theo phải chọn key còn lại (KEY_HEALTHY)
        k2 = pool.acquire_key()
        self.assertNotEqual(k1, k2)
        self.assertEqual(k2, "AIzaSy_KEY_HEALTHY_22222")

    def test_byok_client_override(self):
        """Kiểm tra phụ huynh truyền key riêng (BYOK) thì ưu tiên dùng key đó."""
        raw = "AIzaSy_SERVER_POOL_KEY_12345"
        pool = KeyPoolManager(raw_keys=raw)

        client_key = "AIzaSy_PARENT_OWN_KEY_99999"
        acquired = pool.acquire_key(client_api_key=client_key)
        self.assertEqual(acquired, client_key)

if __name__ == "__main__":
    unittest.main()
