from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]


class DeploySafetyTests(unittest.TestCase):
    def test_vps_deploy_only_updates_existing_backend(self):
        script = (ROOT / "deploy_vps.sh").read_text(encoding="utf-8")
        self.assertIn("docker compose up -d --no-deps --build backend", script)
        self.assertIn("docker compose ps -q backend", script)
        self.assertNotIn("docker compose down", script)
        self.assertNotIn("systemctl restart nginx", script)
        self.assertNotIn("/etc/nginx/", script)
        self.assertNotIn("ufw ", script)
        self.assertNotIn("apt-get ", script)

    def test_vps_deploy_backs_up_live_data_and_checks_health(self):
        script = (ROOT / "deploy_vps.sh").read_text(encoding="utf-8")
        self.assertIn("docker cp", script)
        self.assertIn("sqlite3", script)
        self.assertIn("/app/data/child_memory.db", script)
        self.assertIn("/health", script)
        self.assertIn("git fetch", script)

    def test_windows_launcher_does_not_transmit_secret_or_copy_sources(self):
        script = (ROOT / "deploy_to_vps.ps1").read_text(encoding="utf-8")
        self.assertNotIn("GeminiApiKey", script)
        self.assertNotIn("Read-Host", script)
        self.assertNotIn("scp ", script)
        self.assertIn("deploy_vps.sh", script)
        self.assertIn("old_commit=$(git rev-parse HEAD)", script)
        self.assertIn('PREVIOUS_COMMIT="$old_commit"', script)


if __name__ == "__main__":
    unittest.main()
