"""
Super Productivity Enhanced Local Bridge - Mini Timer Window
Ultra-lightweight floating desktop widget (Tkinter native, zero extra dependencies).
Always-on-top, draggable, position persistence, real-time timer sync with Super Productivity.
"""

import os
import sys
import json
import time
import urllib.request
import urllib.error
import webbrowser
import threading
import tkinter as tk
from tkinter import ttk, messagebox

BRIDGE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BRIDGE_DIR, "config.json")


def format_time(ms: int) -> str:
    total_seconds = max(0, int(ms // 1000))
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"


class MiniTimerWidget:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Super Productivity Mini")
        self.config = self._load_config()
        self.port = self.config.get("port", 4567)
        self.token = self.config.get("auth_token", "")
        self.base_url = f"http://127.0.0.1:{self.port}"
        self.gh_pages_url = self.config.get("web_url", "https://tokewer.github.io/super-productivity/")

        # State tracking
        self.is_tracking = False
        self.active_title = "无活跃任务"
        self.current_time_ms = 0
        self.last_sync_time = time.time()
        self.web_online = False
        self.last_backup_status = "NOT_STARTED"
        self.is_always_on_top = self.config.get("mini_window", {}).get("always_on_top", True)

        # Style configuration (Modern Dark Theme)
        self.bg_color = "#1e1e24"
        self.fg_color = "#f4f4f6"
        self.accent_green = "#4caf50"
        self.accent_amber = "#ff9800"
        self.accent_blue = "#2196f3"
        self.accent_gray = "#757575"
        self.accent_red = "#f44336"

        self._init_window()
        self._build_ui()
        self._start_poll_thread()
        self._start_timer_loop()

    def _load_config(self) -> dict:
        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def _save_window_position(self):
        try:
            x = self.root.winfo_x()
            y = self.root.winfo_y()
            cfg = self._load_config()
            if "mini_window" not in cfg:
                cfg["mini_window"] = {}
            cfg["mini_window"]["x"] = x
            cfg["mini_window"]["y"] = y
            cfg["mini_window"]["always_on_top"] = self.is_always_on_top
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def _init_window(self):
        self.root.configure(bg=self.bg_color)
        win_cfg = self.config.get("mini_window", {})
        x = win_cfg.get("x", 120)
        y = win_cfg.get("y", 120)
        width = win_cfg.get("width", 330)
        height = win_cfg.get("height", 140)

        self.root.geometry(f"{width}x{height}+{x}+{y}")
        self.root.minsize(280, 120)
        self.root.wm_attributes("-topmost", self.is_always_on_top)

        # Handle window close
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self):
        # Outer container
        self.main_frame = tk.Frame(self.root, bg=self.bg_color, padx=10, pady=8)
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        # Header row: Status pill & Window controls
        header_row = tk.Frame(self.main_frame, bg=self.bg_color)
        header_row.pack(fill=tk.X, side=tk.TOP)

        self.status_label = tk.Label(
            header_row,
            text="○ 等待连接",
            font=("Segoe UI", 9, "bold"),
            bg=self.bg_color,
            fg=self.accent_gray
        )
        self.status_label.pack(side=tk.LEFT)

        self.backup_badge = tk.Label(
            header_row,
            text="🛡 备份就绪",
            font=("Segoe UI", 8),
            bg=self.bg_color,
            fg="#9e9e9e"
        )
        self.backup_badge.pack(side=tk.LEFT, padx=10)

        # Pin button (Always on top toggle)
        self.pin_btn = tk.Button(
            header_row,
            text="📌 置顶" if self.is_always_on_top else "📍 取消置顶",
            font=("Segoe UI", 8),
            bg="#2c2c34",
            fg=self.fg_color,
            relief=tk.FLAT,
            padx=4,
            pady=1,
            command=self._toggle_pin
        )
        self.pin_btn.pack(side=tk.RIGHT)

        # Task Title
        self.task_label = tk.Label(
            self.main_frame,
            text="无活跃任务",
            font=("Segoe UI", 11, "bold"),
            bg=self.bg_color,
            fg=self.fg_color,
            anchor="w"
        )
        self.task_label.pack(fill=tk.X, pady=(6, 2))

        # Bottom row: Timer & Action Buttons
        bottom_row = tk.Frame(self.main_frame, bg=self.bg_color)
        bottom_row.pack(fill=tk.X, side=tk.BOTTOM, pady=(4, 0))

        # Time display
        self.time_label = tk.Label(
            bottom_row,
            text="00:00",
            font=("Segoe UI", 20, "bold"),
            bg=self.bg_color,
            fg=self.fg_color
        )
        self.time_label.pack(side=tk.LEFT)

        # Action Buttons container
        btn_box = tk.Frame(bottom_row, bg=self.bg_color)
        btn_box.pack(side=tk.RIGHT)

        self.play_btn = tk.Button(
            btn_box,
            text="▶ 开始",
            font=("Segoe UI", 9, "bold"),
            bg="#388e3c",
            fg="#ffffff",
            activebackground="#4caf50",
            activeforeground="#ffffff",
            relief=tk.FLAT,
            padx=8,
            pady=3,
            command=self._toggle_tracking
        )
        self.play_btn.pack(side=tk.LEFT, padx=3)

        self.backup_btn = tk.Button(
            btn_box,
            text="💾 备份",
            font=("Segoe UI", 9),
            bg="#2c2c34",
            fg=self.fg_color,
            activebackground="#3e3e4a",
            activeforeground="#ffffff",
            relief=tk.FLAT,
            padx=6,
            pady=3,
            command=self._trigger_backup
        )
        self.backup_btn.pack(side=tk.LEFT, padx=3)

        self.web_btn = tk.Button(
            btn_box,
            text="🌐 网页",
            font=("Segoe UI", 9),
            bg="#2c2c34",
            fg=self.fg_color,
            activebackground="#3e3e4a",
            activeforeground="#ffffff",
            relief=tk.FLAT,
            padx=6,
            pady=3,
            command=self._open_web
        )
        self.web_btn.pack(side=tk.LEFT, padx=3)

    def _toggle_pin(self):
        self.is_always_on_top = not self.is_always_on_top
        self.root.wm_attributes("-topmost", self.is_always_on_top)
        self.pin_btn.config(text="📌 置顶" if self.is_always_on_top else "📍 取消置顶")
        self._save_window_position()

    def _open_web(self):
        webbrowser.open(self.gh_pages_url)

    def _toggle_tracking(self):
        """Sends action to local bridge for web app to consume."""
        self._send_action("toggle_tracking")

    def _trigger_backup(self):
        """Sends backup trigger action to web app."""
        self.backup_badge.config(text="⏳ 正在备份...", fg=self.accent_amber)
        self._send_action("trigger_backup")

    def _send_action(self, action_name: str):
        def _req():
            try:
                url = f"{self.base_url}/api/action"
                payload = json.dumps({"action": action_name}).encode("utf-8")
                req = urllib.request.Request(
                    url,
                    data=payload,
                    headers={
                        "Content-Type": "application/json",
                        "X-Bridge-Token": self.token
                    },
                    method="POST"
                )
                with urllib.request.urlopen(req, timeout=3) as resp:
                    pass
            except Exception as e:
                pass
        threading.Thread(target=_req, daemon=True).start()

    def _start_poll_thread(self):
        def _poll():
            while True:
                try:
                    # 1. Fetch live state
                    req = urllib.request.Request(
                        f"{self.base_url}/api/state",
                        headers={"X-Bridge-Token": self.token}
                    )
                    with urllib.request.urlopen(req, timeout=2) as resp:
                        data = json.loads(resp.read().decode("utf-8"))
                        if data.get("success"):
                            st = data["state"]
                            self.active_title = st.get("activeTaskTitle") or "无活跃任务"
                            self.is_tracking = bool(st.get("isTracking"))
                            self.current_time_ms = st.get("timeSpentMs", 0)
                            self.last_sync_time = time.time()
                            self.web_online = bool(st.get("webOnline"))

                    # 2. Fetch health & backup status
                    with urllib.request.urlopen(f"{self.base_url}/api/health", timeout=2) as resp:
                        h_data = json.loads(resp.read().decode("utf-8"))
                        self.last_backup_status = h_data.get("backup_status", "NOT_STARTED")
                except Exception:
                    self.web_online = False

                time.sleep(1.0)

        t = threading.Thread(target=_poll, daemon=True)
        t.start()

    def _start_timer_loop(self):
        def _tick():
            # If tracking, advance display smoothly
            if self.is_tracking and self.web_online:
                elapsed_since_sync = int((time.time() - self.last_sync_time) * 1000)
                display_ms = self.current_time_ms + elapsed_since_sync
            else:
                display_ms = self.current_time_ms

            self.time_label.config(text=format_time(display_ms))

            # Task title truncation
            title_text = self.active_title
            if len(title_text) > 28:
                title_text = title_text[:26] + "..."
            self.task_label.config(text=title_text)

            # Update status badges and button text
            if not self.web_online:
                self.status_label.config(text="⚠ 网页未连接", fg=self.accent_red)
                self.play_btn.config(text="▶ 开始", bg="#424242", state=tk.DISABLED)
            elif self.is_tracking:
                self.status_label.config(text="● 正在计时", fg=self.accent_green)
                self.play_btn.config(text="⏸ 暂停", bg="#f57c00", state=tk.NORMAL)
            else:
                self.status_label.config(text="⏸ 计时暂停" if self.active_title != "无活跃任务" else "○ 计时空闲", fg=self.accent_amber if self.active_title != "无活跃任务" else self.accent_gray)
                self.play_btn.config(text="▶ 开始", bg="#388e3c", state=tk.NORMAL)

            # Backup badge
            if self.last_backup_status == "SUCCESS":
                self.backup_badge.config(text="🛡 备份正常", fg=self.accent_green)
            elif self.last_backup_status == "IN_PROGRESS":
                self.backup_badge.config(text="⏳ 正在备份", fg=self.accent_amber)
            elif self.last_backup_status == "ERROR":
                self.backup_badge.config(text="❌ 备份异常", fg=self.accent_red)

            self.root.after(200, _tick)

        self.root.after(200, _tick)

    def _on_close(self):
        self._save_window_position()
        self.root.destroy()


def run_mini_window():
    root = tk.Tk()
    app = MiniTimerWidget(root)
    root.mainloop()


if __name__ == "__main__":
    run_mini_window()
