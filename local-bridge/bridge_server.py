"""
Super Productivity Enhanced Local Bridge - Secure HTTP Server
Listens strictly on 127.0.0.1, enforces token auth, PNA headers, and origin verification.
"""

import os
import sys
import json
import time
import secrets
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from urllib.parse import urlparse, parse_qs
from backup_manager import BackupManager

# Configuration and Paths
BRIDGE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BRIDGE_DIR, "config.json")
LOG_PATH = os.path.join(BRIDGE_DIR, "bridge.log")

# Setup Logging (Sanitized, no tokens or private task data in logs)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_PATH, encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("BridgeServer")


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True


class BridgeState:
    """In-memory thread-safe state container."""
    def __init__(self, config: dict):
        self.config = config
        self.token = config.get("auth_token", "")
        self.port = config.get("port", 4567)
        self.allowed_origins = config.get("allowed_origins", [
            "https://tokewer.github.io",
            "http://localhost:4200",
            "http://127.0.0.1:4200",
            "http://localhost:8080",
            "http://127.0.0.1:8080"
        ])
        self.backup_mgr = BackupManager(
            backup_dir=config.get("backup_dir", os.path.join(BRIDGE_DIR, "backups")),
            max_backups=config.get("max_backups", 100),
            retention_days=config.get("retention_days", 30)
        )
        self.current_state = {
            "activeTaskId": None,
            "activeTaskTitle": "无活跃任务",
            "timeSpentMs": 0,
            "isTracking": False,
            "mode": "task",
            "lastTick": int(time.time() * 1000),
            "webOnline": False
        }
        self.pending_actions = []
        self.last_backup_status = {
            "status": "NOT_STARTED",  # NOT_STARTED, SUCCESS, ERROR, IN_PROGRESS
            "last_success_time": None,
            "last_error": None
        }


def load_or_create_config() -> dict:
    default_cfg = {
        "host": "127.0.0.1",
        "port": 4567,
        "auth_token": secrets.token_hex(24),
        "backup_dir": os.path.join(BRIDGE_DIR, "backups"),
        "max_backups": 100,
        "retention_days": 30,
        "allowed_origins": [
            "https://tokewer.github.io",
            "http://localhost:4200",
            "http://127.0.0.1:4200",
            "http://localhost:8080",
            "http://127.0.0.1:8080"
        ],
        "mini_window": {
            "x": 100,
            "y": 100,
            "width": 320,
            "height": 130,
            "always_on_top": True
        }
    }

    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                for k, v in default_cfg.items():
                    if k not in cfg:
                        cfg[k] = v
                return cfg
        except Exception as e:
            logger.warning(f"Error loading config.json, resetting: {e}")

    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(default_cfg, f, indent=2, ensure_ascii=False)
    logger.info("Generated new config.json with secure random token.")
    return default_cfg


def save_config(cfg: dict):
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Failed to save config: {e}")


class BridgeRequestHandler(BaseHTTPRequestHandler):
    server_version = "SuperProductivityBridge/1.0"

    @property
    def state(self) -> BridgeState:
        return self.server.bridge_state

    def _is_origin_allowed(self, origin: str) -> bool:
        if not origin:
            return True  # Native apps or scripts without Origin header
        origin = origin.strip().rstrip("/")
        for allowed in self.state.allowed_origins:
            if allowed.endswith("*"):
                prefix = allowed[:-1]
                if origin.startswith(prefix):
                    return True
            elif origin == allowed:
                return True
        # Allow any github.io subdomain
        if origin.startswith("https://") and origin.endswith(".github.io"):
            return True
        # Allow localhost with any port
        if origin.startswith("http://localhost:") or origin.startswith("http://127.0.0.1:"):
            return True
        return False

    def _set_cors_headers(self):
        origin = self.headers.get("Origin")
        if origin and self._is_origin_allowed(origin):
            self.send_header("Access-Control-Allow-Origin", origin)
        else:
            self.send_header("Access-Control-Allow-Origin", "*")

        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Bridge-Token, Authorization")
        self.send_header("Access-Control-Allow-Private-Network", "true")
        self.send_header("Vary", "Origin")

    def do_OPTIONS(self):
        """Handle CORS Preflight and Chromium Private Network Access (PNA)."""
        self.send_response(204)
        self._set_cors_headers()
        self.end_headers()

    def _verify_auth(self) -> bool:
        """Verifies random bearer token from X-Bridge-Token or Authorization header."""
        auth_header = self.headers.get("X-Bridge-Token")
        if not auth_header:
            auth = self.headers.get("Authorization", "")
            if auth.startswith("Bearer "):
                auth_header = auth[7:]

        if not auth_header:
            # Check query params for beacon requests
            parsed = urlparse(self.path)
            qs = parse_qs(parsed.query)
            if "token" in qs:
                auth_header = qs["token"][0]

        expected_token = self.state.token
        if not auth_header or not secrets.compare_digest(auth_header, expected_token):
            return False
        return True

    def _send_json(self, status_code: int, data: dict):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._set_cors_headers()
        self.end_headers()
        self.wfile.write(body)

    def _send_error(self, status_code: int, message: str):
        self._send_json(status_code, {"error": message, "success": False})

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        # 1. Health check (no auth required for ping/discovery)
        if path == "/api/health":
            latest = self.state.backup_mgr.get_latest_backup()
            self._send_json(200, {
                "status": "ok",
                "app": "SuperProductivityBridge",
                "version": "1.0.0",
                "total_backups": len(self.state.backup_mgr.list_backups()),
                "last_backup_time": latest["timestamp"] if latest else None,
                "backup_status": self.state.last_backup_status["status"]
            })
            return

        # Host Header Check against DNS Rebinding
        host = self.headers.get("Host", "")
        if not (host.startswith("127.0.0.1") or host.startswith("localhost")):
            self._send_error(403, "Forbidden host header (DNS rebinding protection)")
            return

        # 2. Authenticated Endpoints
        if not self._verify_auth():
            self._send_error(401, "Unauthorized: Invalid or missing X-Bridge-Token")
            return

        if path == "/api/status":
            latest = self.state.backup_mgr.get_latest_backup()
            self._send_json(200, {
                "success": True,
                "current_state": self.state.current_state,
                "backup_status": self.state.last_backup_status,
                "total_backups": len(self.state.backup_mgr.list_backups()),
                "latest_backup": latest
            })
        elif path == "/api/state":
            # Check if web state is still considered fresh (< 15 seconds)
            time_since_tick = time.time() - (self.state.current_state.get("lastTick", 0) / 1000)
            self.state.current_state["webOnline"] = time_since_tick < 15
            self._send_json(200, {
                "success": True,
                "state": self.state.current_state
            })
        elif path == "/api/action":
            # Web app pulls actions to execute
            action = self.state.pending_actions.pop(0) if self.state.pending_actions else None
            self._send_json(200, {"success": True, "action": action})
        elif path == "/api/backups":
            backups = self.state.backup_mgr.list_backups()
            self._send_json(200, {"success": True, "backups": backups})
        elif path == "/api/backup/latest":
            latest = self.state.backup_mgr.get_latest_backup()
            if not latest:
                self._send_error(404, "No backup found")
                return
            ok, msg, content = self.state.backup_mgr.load_backup_content(latest["filename"])
            if not ok:
                self._send_error(500, msg)
                return
            self._send_json(200, {"success": True, "meta": latest, "data": content})
        else:
            self._send_error(404, "Endpoint not found")

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        # Host Header Check
        host = self.headers.get("Host", "")
        if not (host.startswith("127.0.0.1") or host.startswith("localhost")):
            self._send_error(403, "Forbidden host header (DNS rebinding protection)")
            return

        if not self._verify_auth():
            self._send_error(401, "Unauthorized: Invalid or missing X-Bridge-Token")
            return

        # Read JSON body safely
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length > 100 * 1024 * 1024:  # 100MB limit
            self._send_error(413, "Payload too large")
            return

        body = self.rfile.read(content_length)
        try:
            data = json.loads(body.decode("utf-8")) if body else {}
        except Exception as e:
            self._send_error(400, f"Malformed JSON: {str(e)}")
            return

        if path == "/api/backup":
            self.state.last_backup_status["status"] = "IN_PROGRESS"
            try:
                result = self.state.backup_mgr.save_backup(data, source="web_push")
                self.state.last_backup_status["status"] = "SUCCESS"
                self.state.last_backup_status["last_success_time"] = result["timestamp"]
                self.state.last_backup_status["last_error"] = None
                logger.info(f"Backup succeeded: {result['filename']} (tasks: {result['stats']['task_count']})")
                self._send_json(200, result)
            except Exception as e:
                self.state.last_backup_status["status"] = "ERROR"
                self.state.last_backup_status["last_error"] = str(e)
                logger.error(f"Backup failed: {e}")
                self._send_error(500, f"Backup write failed: {str(e)}")

        elif path == "/api/state":
            # Update live tracking state from web app
            self.state.current_state.update({
                "activeTaskId": data.get("activeTaskId"),
                "activeTaskTitle": data.get("activeTaskTitle") or "无活跃任务",
                "timeSpentMs": data.get("timeSpentMs", 0),
                "isTracking": bool(data.get("isTracking")),
                "mode": data.get("mode", "task"),
                "lastTick": int(time.time() * 1000),
                "webOnline": True
            })
            self._send_json(200, {"success": True})

        elif path == "/api/action":
            action_type = data.get("action")
            if not action_type:
                self._send_error(400, "Missing action parameter")
                return
            self.state.pending_actions.append(data)
            logger.info(f"Queued action from mini window: {action_type}")
            self._send_json(200, {"success": True, "queued": action_type})

        elif path == "/api/restore":
            filename = data.get("filename")
            if not filename:
                latest = self.state.backup_mgr.get_latest_backup()
                if not latest:
                    self._send_error(404, "No backups available to restore")
                    return
                filename = latest["filename"]

            ok, msg, content = self.state.backup_mgr.load_backup_content(filename)
            if not ok:
                self._send_error(400, msg)
                return
            self._send_json(200, {"success": True, "filename": filename, "data": content})

        else:
            self._send_error(404, "Endpoint not found")

    def log_message(self, format, *args):
        # Suppress verbose access log for periodic polls (/api/state) to avoid log spam
        if args and len(args) > 0 and "/api/state" in str(args[0]):
            return
        logger.info(f"{self.address_string()} - {format % args}")


def start_server(port: int = None, config: dict = None) -> ThreadedHTTPServer:
    cfg = config or load_or_create_config()
    server_port = port or cfg.get("port", 4567)
    server_address = ("127.0.0.1", server_port)
    server = ThreadedHTTPServer(server_address, BridgeRequestHandler)
    server.bridge_state = BridgeState(cfg)
    logger.info(f"Super Productivity Bridge Server listening on http://127.0.0.1:{server_port}")
    logger.info(f"Auth Token configured. Backups stored in: {cfg['backup_dir']}")
    return server


if __name__ == "__main__":
    cfg = load_or_create_config()
    server = start_server(config=cfg)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Server shutting down...")
        server.server_close()
