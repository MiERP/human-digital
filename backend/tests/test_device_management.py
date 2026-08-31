import unittest
import tempfile
import os
import shutil
import asyncio
from backend.memory_manager import MemoryManager
from backend.connection_tracker import ActiveConnectionTracker

class TestDeviceManagementAndBan(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.test_dir, "test_devices.db")
        self.memory = MemoryManager(db_path=self.db_path)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_device_registration_and_update(self):
        """Kiểm tra lưu thông tin thiết bị và cập nhật lần cuối."""
        fingerprint = "hw_sha256_samsung_galaxy_a23_xyz123"
        dev = self.memory.register_device(
            device_fingerprint=fingerprint,
            child_id="kid_sam_01",
            device_model="Samsung Galaxy A23",
            android_version="Android 14",
            app_version="1.0.0",
            ip="113.185.47.98"
        )
        self.assertEqual(dev["device_fingerprint"], fingerprint)
        self.assertEqual(dev["device_model"], "Samsung Galaxy A23")
        self.assertEqual(dev["is_blocked"], 0)

        # Lần kết nối sau với IP khác
        dev2 = self.memory.register_device(
            device_fingerprint=fingerprint,
            child_id="kid_sam_01",
            ip="14.232.12.99"
        )
        self.assertEqual(dev2["last_ip"], "14.232.12.99")
        self.assertEqual(dev2["device_model"], "Samsung Galaxy A23")

    def test_hardware_ban_and_unban(self):
        """Kiểm tra khóa thiết bị bất biến và mở khóa."""
        fingerprint = "hw_banned_device_999"
        self.memory.register_device(
            device_fingerprint=fingerprint,
            child_id="kid_troublemaker",
            device_model="Xiaomi Redmi Note 12"
        )

        # Ban đầu không bị khóa
        is_blocked, _ = self.memory.is_device_blocked(device_fingerprint=fingerprint)
        self.assertFalse(is_blocked)

        # Khóa thiết bị
        success = self.memory.set_device_block_status(
            device_fingerprint=fingerprint,
            is_blocked=True,
            reason="Spam audio packets"
        )
        self.assertTrue(success)

        # Kiểm tra trạng thái sau khi khóa
        is_blocked, reason = self.memory.is_device_blocked(device_fingerprint=fingerprint)
        self.assertTrue(is_blocked)
        self.assertIn("Spam", reason)

        # Giả lập người dùng xóa app và cài lại (tạo child_id mới nhưng giữ nguyên fingerprint)
        is_blocked_reinstall, _ = self.memory.is_device_blocked(
            device_fingerprint=fingerprint,
            child_id="new_kid_id_after_reinstall"
        )
        self.assertTrue(is_blocked_reinstall, "Phải khóa được thiết bị kể cả khi gỡ app tạo child_id mới!")

        # Mở khóa thiết bị
        self.memory.set_device_block_status(device_fingerprint=fingerprint, is_blocked=False)
        is_blocked_after_unban, _ = self.memory.is_device_blocked(device_fingerprint=fingerprint)
        self.assertFalse(is_blocked_after_unban)

    def test_device_metrics_and_listing(self):
        """Kiểm tra thống kê tổng số thiết bị, thiết bị bị khóa và danh sách."""
        self.memory.register_device("dev_1", "kid_1", "Pixel 7")
        self.memory.register_device("dev_2", "kid_2", "Galaxy S23")
        self.memory.register_device("dev_3", "kid_3", "iPhone 15")

        self.memory.set_device_block_status("dev_2", is_blocked=True, reason="Abuse")
        self.memory.update_device_session_stats("dev_1", duration_sec=600)

        metrics = self.memory.get_device_metrics()
        self.assertEqual(metrics["total_devices"], 3)
        self.assertEqual(metrics["blocked_devices"], 1)
        self.assertEqual(metrics["active_devices"], 2)

        devices = self.memory.get_all_devices()
        self.assertEqual(len(devices), 3)

    def test_active_connection_tracker(self):
        """Kiểm tra bộ theo dõi session và kick ngắt kết nối."""
        tracker = ActiveConnectionTracker()
        
        async def run_tracker_test():
            # Giả lập đối tượng WebSocket
            class DummyWS:
                def __init__(self):
                    self.closed = False
                    self.close_code = None
                    self.sent_messages = []
                async def send_text(self, text):
                    self.sent_messages.append(text)
                async def close(self, code=1000):
                    self.closed = True
                    self.close_code = code

            ws1 = DummyWS()
            ws2 = DummyWS()

            await tracker.register("s1", ws1, "kid_1", "fp_1", "Galaxy A23", "1.1.1.1", "AIzaSyAA...")
            await tracker.register("s2", ws2, "kid_2", "fp_2", "Pixel 6", "2.2.2.2", "AIzaSyBB...")

            self.assertEqual(tracker.online_count, 2)
            active = await tracker.get_active_sessions()
            self.assertEqual(len(active), 2)

            # Kick thiết bị 1
            kicked = await tracker.kick_by_fingerprint("fp_1", reason="Admin kicked you")
            self.assertEqual(kicked, 1)
            self.assertTrue(ws1.closed)
            self.assertEqual(ws1.close_code, 1008)
            self.assertIn("Admin kicked you", ws1.sent_messages[0])

            # Unregister
            await tracker.unregister("s1")
            await tracker.unregister("s2")
            self.assertEqual(tracker.online_count, 0)

        asyncio.run(run_tracker_test())

if __name__ == "__main__":
    unittest.main()
