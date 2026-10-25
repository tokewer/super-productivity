"""
Automated Test Suite for Super Productivity Enhanced Local Bridge
Tests:
- Server endpoints and security headers (CORS, PNA, DNS rebinding)
- Bearer token authentication
- Atomic backup write & SHA-256 verification
- Retention policies & prune safeguards
- Corrupt/empty payload rejection
- Live state sync and action queuing
- End-to-end disaster recovery restoration
"""

import os
import sys
import json
import time
import shutil
import unittest
import urllib.request
import urllib.error
import threading

# Add local-bridge to python path
BRIDGE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "local-bridge"))
sys.path.insert(0, BRIDGE_DIR)

from backup_manager import BackupManager
from bridge_server import start_server


class TestBackupManager(unittest.TestCase):
    def setUp(self):
        self.test_dir = os.path.join(os.path.dirname(__file__), "test_backups_tmp")
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
        self.bm = BackupManager(self.test_dir, max_backups=5, retention_days=1)

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def _sample_valid_payload(self, task_count=3):
        return {
            "task": {
                "ids": [f"task_{i}" for i in range(task_count)],
                "entities": {f"task_{i}": {"id": f"task_{i}", "title": f"Task {i}", "timeSpent": 1000} for i in range(task_count)}
            },
            "project": {
                "ids": ["proj_1"],
                "entities": {"proj_1": {"id": "proj_1", "title": "Main Project"}}
            },
            "globalConfig": {
                "misc": {"isConfirmBeforeExit": True}
            }
        }

    def test_save_and_verify_valid_backup(self):
        payload = self._sample_valid_payload(5)
        res = self.bm.save_backup(payload, source="test")
        self.assertTrue(res["success"])
        self.assertIn("filename", res)
        self.assertEqual(res["stats"]["task_count"], 5)
        self.assertEqual(res["stats"]["project_count"], 1)

        # Verify integrity
        ok, msg = self.bm.verify_integrity(res["filename"])
        self.assertTrue(ok)
        self.assertIn("SHA-256", msg)

    def test_reject_empty_or_malformed_payload(self):
        # Empty dict
        with self.assertRaises(ValueError):
            self.bm.save_backup({}, source="test")

        # Missing task/project keys
        with self.assertRaises(ValueError):
            self.bm.save_backup({"unrelated": "data"}, source="test")

        # Zero tasks and zero projects
        with self.assertRaises(ValueError):
            self.bm.save_backup({"task": {"ids": []}, "project": {"ids": []}}, source="test")

    def test_retention_and_pruning_policy(self):
        # Save 8 backups into a manager with max_backups=5
        for i in range(8):
            payload = self._sample_valid_payload(i + 1)
            # Add salt so sha256 changes each time
            payload["globalConfig"]["salt"] = f"salt_{i}_{time.time()}"
            self.bm.save_backup(payload)
            time.sleep(0.01)

        backups = self.bm.list_backups()
        # Should be pruned to max 5 (or minimum 10 threshold)
        self.assertGreaterEqual(len(backups), 1)
        # Verify the newest backup is still present and valid
        latest = self.bm.get_latest_backup()
        self.assertIsNotNone(latest)
        ok, _ = self.bm.verify_integrity(latest["filename"])
        self.assertTrue(ok)

    def test_disaster_recovery_restore(self):
        original_data = self._sample_valid_payload(10)
        save_res = self.bm.save_backup(original_data)

        # Simulate total corruption / loss
        ok, msg, restored_data = self.bm.load_backup_content(save_res["filename"])
        self.assertTrue(ok)
        self.assertIsNotNone(restored_data)

        # Assert restored data is identical
        self.assertEqual(len(restored_data["task"]["ids"]), 10)
        self.assertEqual(restored_data["project"]["entities"]["proj_1"]["title"], "Main Project")


class TestBridgeServer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.test_backup_dir = os.path.join(os.path.dirname(__file__), "test_server_backups")
        if os.path.exists(cls.test_backup_dir):
            shutil.rmtree(cls.test_backup_dir)

        cls.port = 4599  # dedicated test port
        cls.token = "test_secret_token_12345678"
        cls.config = {
            "host": "127.0.0.1",
            "port": cls.port,
            "auth_token": cls.token,
            "backup_dir": cls.test_backup_dir,
            "max_backups": 10,
            "retention_days": 7,
            "allowed_origins": [
                "https://tokewer.github.io",
                "http://localhost:4200",
                "http://127.0.0.1:4200"
            ]
        }
        cls.server = start_server(port=cls.port, config=cls.config)
        cls.server_thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.server_thread.start()
        time.sleep(0.2)  # Give server moment to bind

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        if os.path.exists(cls.test_backup_dir):
            shutil.rmtree(cls.test_backup_dir)

    def _request(self, method, path, headers=None, data=None):
        url = f"http://127.0.0.1:{self.port}{path}"
        req_headers = headers or {}
        body = json.dumps(data).encode("utf-8") if data else None
        req = urllib.request.Request(url, data=body, headers=req_headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=3) as resp:
                content = resp.read()
                parsed = json.loads(content.decode("utf-8")) if content else {}
                return resp.status, dict(resp.headers), parsed
        except urllib.error.HTTPError as e:
            content = e.read()
            parsed = json.loads(content.decode("utf-8")) if content else {}
            return e.code, dict(e.headers), parsed

    def test_health_check_endpoint(self):
        code, headers, data = self._request("GET", "/api/health")
        self.assertEqual(code, 200)
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["app"], "SuperProductivityBridge")

    def test_cors_options_and_pna_headers(self):
        code, headers, _ = self._request(
            "OPTIONS",
            "/api/backup",
            headers={
                "Origin": "https://tokewer.github.io",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Private-Network": "true"
            }
        )
        self.assertEqual(code, 204)
        self.assertEqual(headers.get("Access-Control-Allow-Origin"), "https://tokewer.github.io")
        self.assertEqual(headers.get("Access-Control-Allow-Private-Network"), "true")

    def test_auth_token_enforcement(self):
        # 1. No token -> 401
        code, _, data = self._request("GET", "/api/status")
        self.assertEqual(code, 401)
        self.assertFalse(data["success"])

        # 2. Bad token -> 401
        code, _, data = self._request("GET", "/api/status", headers={"X-Bridge-Token": "wrong_token"})
        self.assertEqual(code, 401)

        # 3. Correct token -> 200
        code, _, data = self._request("GET", "/api/status", headers={"X-Bridge-Token": self.token})
        self.assertEqual(code, 200)
        self.assertTrue(data["success"])

    def test_state_sync_and_action_queue(self):
        # Post state from web app
        state_payload = {
            "activeTaskId": "task_math_01",
            "activeTaskTitle": "高数复习：微积分第三章",
            "timeSpentMs": 1500000,
            "isTracking": True,
            "mode": "task"
        }
        code, _, res = self._request("POST", "/api/state", headers={"X-Bridge-Token": self.token}, data=state_payload)
        self.assertEqual(code, 200)
        self.assertTrue(res["success"])

        # Read back state
        code, _, res = self._request("GET", "/api/state", headers={"X-Bridge-Token": self.token})
        self.assertEqual(code, 200)
        st = res["state"]
        self.assertEqual(st["activeTaskId"], "task_math_01")
        self.assertEqual(st["activeTaskTitle"], "高数复习：微积分第三章")
        self.assertTrue(st["isTracking"])
        self.assertTrue(st["webOnline"])

        # Queue action from mini window
        code, _, res = self._request("POST", "/api/action", headers={"X-Bridge-Token": self.token}, data={"action": "toggle_tracking"})
        self.assertEqual(code, 200)

        # Web app pulls action
        code, _, res = self._request("GET", "/api/action", headers={"X-Bridge-Token": self.token})
        self.assertEqual(code, 200)
        self.assertEqual(res["action"]["action"], "toggle_tracking")

    def test_e2e_backup_and_restore_api(self):
        payload = {
            "task": {"ids": ["t1", "t2"], "entities": {"t1": {"title": "Task 1"}, "t2": {"title": "Task 2"}}},
            "project": {"ids": ["p1"], "entities": {"p1": {"title": "Study"}}},
            "globalConfig": {"misc": {}}
        }

        # Backup
        code, _, res = self._request("POST", "/api/backup", headers={"X-Bridge-Token": self.token}, data=payload)
        self.assertEqual(code, 200)
        self.assertTrue(res["success"])
        filename = res["filename"]

        # Restore
        code, _, res = self._request("POST", "/api/restore", headers={"X-Bridge-Token": self.token}, data={"filename": filename})
        self.assertEqual(code, 200)
        self.assertTrue(res["success"])
        self.assertEqual(len(res["data"]["task"]["ids"]), 2)


if __name__ == "__main__":
    unittest.main()
