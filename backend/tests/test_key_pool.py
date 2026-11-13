import unittest
import time
import hashlib
import os
import sys
import tempfile
from unittest import mock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from key_pool import KeyPoolManager, KeyInfo

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

    def test_reconnect_prefers_the_key_that_issued_the_handle(self):
        first = "AIzaSy_SERVER_POOL_KEY_FIRST_12345"
        second = "AIzaSy_SERVER_POOL_KEY_SECOND_67890"
        pool = KeyPoolManager(raw_keys=f"{first},{second}")
        pool.acquire_key()
        preferred_id = hashlib.sha256(first.encode()).hexdigest()[:16]

        self.assertEqual(pool.acquire_key(preferred_key_id=preferred_id), first)

    def test_admin_add_and_remove_key(self):
        """Key thêm từ admin được lưu file; key từ .env không xóa qua admin."""
        env_key = "AIzaSy_ENV_KEY_123456789"
        admin_key = "AIzaSy_ADMIN_KEY_987654321"

        with tempfile.TemporaryDirectory() as tmp:
            storage = os.path.join(tmp, "gemini_keys.json")
            pool = KeyPoolManager(raw_keys=env_key, storage_path=storage)

            ok, _ = pool.add_key(admin_key)
            self.assertTrue(ok)
            self.assertEqual(pool.total_keys, 2)
            self.assertTrue(os.path.exists(storage))

            # Không cho thêm trùng
            ok, _ = pool.add_key(admin_key)
            self.assertFalse(ok)

            # Không cho thêm key rác
            ok, _ = pool.add_key("short")
            self.assertFalse(ok)

            details = pool.get_pool_status()["keys_detail"]
            admin_entry = next(k for k in details if k["masked_key"].startswith("AIzaSy_A"))
            self.assertEqual(admin_entry["source"], "file")

            # Key từ .env không thể xóa qua admin
            env_id = hashlib.sha256(env_key.encode()).hexdigest()[:16]
            ok, _ = pool.remove_key(env_id)
            self.assertFalse(ok)

            # Key thêm từ admin xóa được
            admin_id = hashlib.sha256(admin_key.encode()).hexdigest()[:16]
            ok, _ = pool.remove_key(admin_id)
            self.assertTrue(ok)
            self.assertEqual(pool.total_keys, 1)

    def test_admin_keys_reload_after_restart(self):
        """Key đã thêm vẫn còn sau khi tạo lại KeyPoolManager (container restart)."""
        admin_key = "AIzaSy_ADMIN_KEY_RELOAD_123456"
        with tempfile.TemporaryDirectory() as tmp:
            storage = os.path.join(tmp, "gemini_keys.json")
            pool = KeyPoolManager(raw_keys="", storage_path=storage)
            self.assertTrue(pool.add_key(admin_key)[0])

            with mock.patch.dict(os.environ, {"GEMINI_API_KEY": "", "GEMINI_API_KEYS": ""}):
                restarted = KeyPoolManager(storage_path=storage)

            self.assertEqual(restarted.total_keys, 1)
            self.assertEqual(
                restarted.get_pool_status()["keys_detail"][0]["source"], "file"
            )

if __name__ == "__main__":
    unittest.main()
