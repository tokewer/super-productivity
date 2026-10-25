"""
Super Productivity Enhanced Local Bridge - Backup Manager
Handles atomic writes, SHA-256 checksums, retention management, and integrity checks.
"""

import os
import json
import time
import hashlib
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple


class BackupManager:
    def __init__(self, backup_dir: str, max_backups: int = 100, retention_days: int = 30):
        self.backup_dir = os.path.abspath(backup_dir)
        self.max_backups = max_backups
        self.retention_days = retention_days
        os.makedirs(self.backup_dir, exist_ok=True)
        self.index_file = os.path.join(self.backup_dir, "backup_index.json")
        self._ensure_index()

    def _ensure_index(self):
        if not os.path.exists(self.index_file):
            self._save_index([])

    def _load_index(self) -> List[Dict[str, Any]]:
        try:
            if os.path.exists(self.index_file):
                with open(self.index_file, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            pass
        return []

    def _save_index(self, index_data: List[Dict[str, Any]]):
        tmp_file = self.index_file + f".tmp_{uuid.uuid4().hex}"
        try:
            with open(tmp_file, "w", encoding="utf-8") as f:
                json.dump(index_data, f, indent=2, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_file, self.index_file)
        finally:
            if os.path.exists(tmp_file):
                try:
                    os.remove(tmp_file)
                except Exception:
                    pass

    @staticmethod
    def calculate_sha256(content_bytes: bytes) -> str:
        return hashlib.sha256(content_bytes).hexdigest()

    @staticmethod
    def validate_backup_payload(data: Any) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Validates that the given payload looks like a valid Super Productivity AppDataComplete.
        """
        if not isinstance(data, dict):
            return False, "Payload must be a JSON object", {}

        # Check for core Super Productivity entities
        has_task = "task" in data or "tasks" in data
        has_project = "project" in data
        has_config = "globalConfig" in data

        if not (has_task or has_project or has_config):
            return False, "Missing core Super Productivity data keys (task, project, globalConfig)", {}

        # Count tasks and projects for metadata
        task_count = 0
        project_count = 0

        # Tasks model can be in 'task.ids' or dictionary of tasks
        task_data = data.get("task")
        if isinstance(task_data, dict):
            ids = task_data.get("ids", [])
            if isinstance(ids, list):
                task_count = len(ids)
            elif "entities" in task_data and isinstance(task_data["entities"], dict):
                task_count = len(task_data["entities"])

        project_data = data.get("project")
        if isinstance(project_data, dict):
            ids = project_data.get("ids", [])
            if isinstance(ids, list):
                project_count = len(ids)
            elif "entities" in project_data and isinstance(project_data["entities"], dict):
                project_count = len(project_data["entities"])

        # Near-empty check (if completely blank)
        if task_count == 0 and project_count == 0 and not has_config:
            return False, "State data is completely empty", {}

        stats = {
            "task_count": task_count,
            "project_count": project_count,
            "has_config": has_config,
            "has_archive": "archive" in data
        }
        return True, "Valid payload", stats

    def save_backup(self, payload: Any, source: str = "web") -> Dict[str, Any]:
        """
        Atomically saves a new verified backup file with SHA-256 checksum and updates index.
        """
        is_valid, reason, stats = self.validate_backup_payload(payload)
        if not is_valid:
            raise ValueError(f"Invalid backup data: {reason}")

        payload_str = json.dumps(payload, ensure_ascii=False)
        payload_bytes = payload_str.encode("utf-8")
        checksum = self.calculate_sha256(payload_bytes)

        now = datetime.now()
        timestamp_str = now.strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"backup_{timestamp_str}_{checksum[:8]}.json"
        target_path = os.path.join(self.backup_dir, filename)

        # Atomic write: write to temp file, sync, then rename
        tmp_filename = f".tmp_{filename}_{uuid.uuid4().hex}"
        tmp_path = os.path.join(self.backup_dir, tmp_filename)

        try:
            with open(tmp_path, "wb") as f:
                f.write(payload_bytes)
                f.flush()
                os.fsync(f.fileno())

            # Verify written file on disk matches checksum
            with open(tmp_path, "rb") as f:
                written_checksum = self.calculate_sha256(f.read())
            if written_checksum != checksum:
                raise IOError("Written file checksum mismatch! Write corrupted.")

            # Atomic replace
            os.replace(tmp_path, target_path)

            record = {
                "filename": filename,
                "timestamp": now.isoformat(),
                "timestamp_epoch": int(time.time()),
                "size_bytes": len(payload_bytes),
                "sha256": checksum,
                "source": source,
                "task_count": stats["task_count"],
                "project_count": stats["project_count"],
                "has_config": stats["has_config"]
            }

            # Update index
            index = self._load_index()
            # Avoid duplicate identical backup if hash already matches the last one
            if index and index[0].get("sha256") == checksum:
                record["note"] = "duplicate_hash_refreshed"
                index[0]["last_verified"] = now.isoformat()
            else:
                index.insert(0, record)

            self._prune_old_backups(index)
            self._save_index(index)

            return {
                "success": True,
                "filename": filename,
                "path": target_path,
                "sha256": checksum,
                "size": len(payload_bytes),
                "timestamp": now.isoformat(),
                "stats": stats
            }
        finally:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass

    def _prune_old_backups(self, index: List[Dict[str, Any]]):
        """
        Enforces retention policies while strictly preserving at least 1 verified backup.
        """
        if len(index) <= 1:
            return

        cutoff_epoch = int(time.time()) - (self.retention_days * 86400)
        retained = []
        to_delete = []

        for idx, item in enumerate(index):
            # Always keep at least 10 most recent backups regardless of age
            if idx < 10:
                retained.append(item)
            elif idx >= self.max_backups or item.get("timestamp_epoch", 0) < cutoff_epoch:
                to_delete.append(item)
            else:
                retained.append(item)

        # Safety check: never delete all
        if not retained and to_delete:
            retained.append(to_delete.pop(0))

        # Perform physical file deletion
        for item in to_delete:
            filepath = os.path.join(self.backup_dir, item["filename"])
            if os.path.exists(filepath):
                try:
                    os.remove(filepath)
                except Exception:
                    pass

        index.clear()
        index.extend(retained)

    def list_backups(self) -> List[Dict[str, Any]]:
        return self._load_index()

    def get_latest_backup(self) -> Optional[Dict[str, Any]]:
        index = self._load_index()
        if not index:
            return None
        latest_meta = index[0]
        filepath = os.path.join(self.backup_dir, latest_meta["filename"])
        if not os.path.exists(filepath):
            return None
        return latest_meta

    def load_backup_content(self, filename: str) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        # Path traversal guard
        safe_filename = os.path.basename(filename)
        filepath = os.path.join(self.backup_dir, safe_filename)

        if not os.path.exists(filepath):
            return False, f"File not found: {safe_filename}", None

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            is_valid, reason, _ = self.validate_backup_payload(data)
            if not is_valid:
                return False, f"Invalid backup payload format: {reason}", None
            return True, "Loaded successfully", data
        except Exception as e:
            return False, f"Failed to read backup: {str(e)}", None

    def verify_integrity(self, filename: str) -> Tuple[bool, str]:
        safe_filename = os.path.basename(filename)
        filepath = os.path.join(self.backup_dir, safe_filename)

        if not os.path.exists(filepath):
            return False, "File does not exist"

        try:
            with open(filepath, "rb") as f:
                content = f.read()
            computed_hash = self.calculate_sha256(content)
            data = json.loads(content.decode("utf-8"))
            is_valid, reason, _ = self.validate_backup_payload(data)
            if not is_valid:
                return False, f"Content invalid: {reason}"
            return True, f"Verified OK (SHA-256: {computed_hash})"
        except Exception as e:
            return False, f"Verification failed: {str(e)}"
