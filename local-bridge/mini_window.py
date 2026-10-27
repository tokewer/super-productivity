"""
Super Productivity Enhanced Local Bridge - Frameless Modern Mini Timer Window
- Borderless & frameless modern dark theme (removes native Windows window chrome / "辐条").
- Smooth dragging, always-on-top toggle, compact/expanded mode, position memory.
- Real-time bidirectional synchronization with https://tokewer.github.io/super-productivity/
- Countdown Mode (倒计时模式 / 番茄钟) & Count-Up Mode (正计时模式).
- Full background continuity: remains active and accurate even when browser is minimized!
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
import ctypes

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
        self.config = self._load_config()
        self.port = self.config.get("port", 4567)
        self.token = self.config.get("auth_token", "")
        self.base_url = f"http://127.0.0.1:{self.port}"
        self.gh_pages_url = self.config.get(
            "web_url", "https://tokewer.github.io/super-productivity/"
        )

        # Mode: "count_up" (正计时) or "count_down" (倒计时)
        self.timer_mode = self.config.get("mini_window", {}).get("timer_mode", "count_down")
        # Default countdown duration: 25 minutes in ms (Pomodoro)
        self.countdown_target_ms = self.config.get("mini_window", {}).get(
            "countdown_target_ms", 25 * 60 * 1000
        )
        self.prefer_task_estimate = self.config.get("mini_window", {}).get(
            "prefer_task_estimate", True
        )

        # State tracking
        self.is_tracking = False
        self.active_title = "无活跃任务"
        self.current_time_ms = 0
        self.time_estimate_ms = 0
        self.tracking_started_at = None
        self.last_sync_time = time.time()
        self.web_online = False
        self.last_backup_status = "NOT_STARTED"
        self.is_always_on_top = self.config.get("mini_window", {}).get("always_on_top", True)
        self.is_compact = self.config.get("mini_window", {}).get("compact", False)

        # Theme Colors (Modern Obsidian Dark)
        self.c_bg = "#141518"         # Deepest matte background
        self.c_card = "#1c1e23"       # Card / container background
        self.c_border = "#2d3139"     # Subtle border outline
        self.c_header = "#181a1f"     # Header bar
        self.c_text = "#f3f4f6"       # Primary text
        self.c_text_dim = "#9ca3af"   # Secondary text
        self.c_green = "#22c55e"      # Tracking green
        self.c_amber = "#f59e0b"      # Paused amber
        self.c_red = "#ef4444"        # Overtime / Offline red
        self.c_blue = "#38bdf8"       # Accent cyan / countdown color
        self.c_btn = "#262932"        # Button background
        self.c_btn_hover = "#323642"  # Button hover

        # Drag tracking
        self._drag_start_x = 0
        self._drag_start_y = 0

        self._init_window()
        self._build_ui()
        self._setup_context_menu()
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
            cfg["mini_window"]["compact"] = self.is_compact
            cfg["mini_window"]["timer_mode"] = self.timer_mode
            cfg["mini_window"]["countdown_target_ms"] = self.countdown_target_ms
            cfg["mini_window"]["prefer_task_estimate"] = self.prefer_task_estimate
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def _init_window(self):
        # REMOVE WINDOWS NATIVE TITLEBAR & BORDERS (去掉windows自带的辐条/标题栏)
        self.root.overrideredirect(True)

        win_cfg = self.config.get("mini_window", {})
        x = win_cfg.get("x", 120)
        y = win_cfg.get("y", 120)
        self.full_width = 350
        self.full_height = 138
        self.compact_width = 210
        self.compact_height = 42

        w = self.compact_width if self.is_compact else self.full_width
        h = self.compact_height if self.is_compact else self.full_height

        self.root.geometry(f"{w}x{h}+{x}+{y}")
        self.root.wm_attributes("-topmost", self.is_always_on_top)
        self.root.configure(bg=self.c_border)

        # Enable Windows Taskbar representation for borderless window
        try:
            hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
            GWL_EXSTYLE = -20
            WS_EX_APPWINDOW = 0x00040000
            WS_EX_TOOLWINDOW = 0x00000080
            style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            style = (style & ~WS_EX_TOOLWINDOW) | WS_EX_APPWINDOW
            ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)
        except Exception:
            pass

    def _build_ui(self):
        # 1px border container
        self.border_frame = tk.Frame(self.root, bg=self.c_border, bd=0)
        self.border_frame.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)

        # Main inner container
        self.container = tk.Frame(self.border_frame, bg=self.c_bg, bd=0)
        self.container.pack(fill=tk.BOTH, expand=True)

        # Top Custom Draggable Bar
        self.header_bar = tk.Frame(self.container, bg=self.c_header, height=28)
        self.header_bar.pack(fill=tk.X, side=tk.TOP)
        self.header_bar.pack_propagate(False)

        # Status Dot & Title
        self.status_canvas = tk.Canvas(
            self.header_bar, width=12, height=12, bg=self.c_header, highlightthickness=0
        )
        self.status_canvas.pack(side=tk.LEFT, padx=(8, 4))
        self.status_dot = self.status_canvas.create_oval(2, 2, 10, 10, fill=self.c_red, outline="")

        self.title_label = tk.Label(
            self.header_bar,
            text="SP Mini",
            font=("Segoe UI", 9, "bold"),
            bg=self.c_header,
            fg=self.c_text_dim,
            cursor="fleur"
        )
        self.title_label.pack(side=tk.LEFT)

        # Mode Indicator Pill in Header (Click to toggle Countdown/Count-up)
        self.btn_mode = tk.Label(
            self.header_bar,
            text="⏳ 倒计时" if self.timer_mode == "count_down" else "⏱ 正计时",
            font=("Segoe UI", 8, "bold"),
            bg=self.c_btn,
            fg=self.c_blue if self.timer_mode == "count_down" else self.c_green,
            padx=6,
            pady=1,
            cursor="hand2"
        )
        self.btn_mode.pack(side=tk.LEFT, padx=8)
        self.btn_mode.bind("<Button-1>", lambda e: self._toggle_mode())

        # Window Controls on Right
        # Close button
        self.btn_close = tk.Label(
            self.header_bar,
            text="✕",
            font=("Segoe UI", 9, "bold"),
            bg=self.c_header,
            fg=self.c_text_dim,
            width=3,
            cursor="hand2"
        )
        self.btn_close.pack(side=tk.RIGHT)
        self.btn_close.bind("<Button-1>", lambda e: self._on_close())
        self.btn_close.bind("<Enter>", lambda e: self.btn_close.config(bg="#dc2626", fg="#ffffff"))
        self.btn_close.bind("<Leave>", lambda e: self.btn_close.config(bg=self.c_header, fg=self.c_text_dim))

        # Compact toggle button
        self.btn_compact = tk.Label(
            self.header_bar,
            text="🗕" if not self.is_compact else "🗖",
            font=("Segoe UI", 9),
            bg=self.c_header,
            fg=self.c_text_dim,
            width=3,
            cursor="hand2"
        )
        self.btn_compact.pack(side=tk.RIGHT)
        self.btn_compact.bind("<Button-1>", lambda e: self._toggle_compact())
        self.btn_compact.bind("<Enter>", lambda e: self.btn_compact.config(bg=self.c_btn_hover, fg="#ffffff"))
        self.btn_compact.bind("<Leave>", lambda e: self.btn_compact.config(bg=self.c_header, fg=self.c_text_dim))

        # Pin / Always on top button
        self.btn_pin = tk.Label(
            self.header_bar,
            text="📌",
            font=("Segoe UI", 8),
            bg=self.c_header,
            fg=self.c_blue if self.is_always_on_top else self.c_text_dim,
            width=3,
            cursor="hand2"
        )
        self.btn_pin.pack(side=tk.RIGHT)
        self.btn_pin.bind("<Button-1>", lambda e: self._toggle_pin())
        self.btn_pin.bind("<Enter>", lambda e: self.btn_pin.config(bg=self.c_btn_hover))
        self.btn_pin.bind("<Leave>", lambda e: self.btn_pin.config(bg=self.c_header))

        # Web App launch button
        self.btn_web_hdr = tk.Label(
            self.header_bar,
            text="🌐",
            font=("Segoe UI", 8),
            bg=self.c_header,
            fg=self.c_text_dim,
            width=3,
            cursor="hand2"
        )
        self.btn_web_hdr.pack(side=tk.RIGHT)
        self.btn_web_hdr.bind("<Button-1>", lambda e: self._open_web())
        self.btn_web_hdr.bind("<Enter>", lambda e: self.btn_web_hdr.config(bg=self.c_btn_hover, fg=self.c_blue))
        self.btn_web_hdr.bind("<Leave>", lambda e: self.btn_web_hdr.config(bg=self.c_header, fg=self.c_text_dim))

        # Body Frame (contains task title & timer controls)
        self.body_frame = tk.Frame(self.container, bg=self.c_bg, padx=10, pady=4)
        self.body_frame.pack(fill=tk.BOTH, expand=True)

        # Task Title Label
        self.task_label = tk.Label(
            self.body_frame,
            text="正在等待网页版连接...",
            font=("Microsoft YaHei UI", 10, "bold"),
            bg=self.c_bg,
            fg=self.c_text,
            anchor="w",
            cursor="fleur"
        )
        self.task_label.pack(fill=tk.X, pady=(0, 2))

        # Subtitle / Mode Info (e.g. 倒计时目标 / 进度)
        self.subtitle_label = tk.Label(
            self.body_frame,
            text="⏳ 倒计时目标: 25分钟 (点击切换)",
            font=("Segoe UI", 8),
            bg=self.c_bg,
            fg=self.c_text_dim,
            anchor="w",
            cursor="hand2"
        )
        self.subtitle_label.pack(fill=tk.X, pady=(0, 2))
        self.subtitle_label.bind("<Button-1>", lambda e: self._open_countdown_picker(e))

        # Bottom row: Big Timer & Action Buttons
        self.bottom_row = tk.Frame(self.body_frame, bg=self.c_bg)
        self.bottom_row.pack(fill=tk.X, side=tk.BOTTOM)

        # Time Display (Click to toggle Countdown/Count-up)
        self.time_label = tk.Label(
            self.bottom_row,
            text="25:00",
            font=("Segoe UI", 21, "bold"),
            bg=self.c_bg,
            fg=self.c_blue if self.timer_mode == "count_down" else self.c_text_dim,
            cursor="hand2"
        )
        self.time_label.pack(side=tk.LEFT)
        self.time_label.bind("<Button-1>", lambda e: self._toggle_mode())

        # Button group
        self.btn_box = tk.Frame(self.bottom_row, bg=self.c_bg)
        self.btn_box.pack(side=tk.RIGHT)

        # Play / Pause Pill Button
        self.play_btn = tk.Button(
            self.btn_box,
            text="▶ 开始",
            font=("Segoe UI", 9, "bold"),
            bg="#2e7d32",
            fg="#ffffff",
            activebackground="#388e3c",
            activeforeground="#ffffff",
            relief=tk.FLAT,
            bd=0,
            padx=10,
            pady=4,
            cursor="hand2",
            command=self._toggle_tracking
        )
        self.play_btn.pack(side=tk.LEFT, padx=3)

        # Backup Button
        self.backup_btn = tk.Button(
            self.btn_box,
            text="💾 备份",
            font=("Segoe UI", 8),
            bg=self.c_btn,
            fg=self.c_text,
            activebackground=self.c_btn_hover,
            activeforeground="#ffffff",
            relief=tk.FLAT,
            bd=0,
            padx=8,
            pady=4,
            cursor="hand2",
            command=self._trigger_backup
        )
        self.backup_btn.pack(side=tk.LEFT, padx=3)

        # Open Web Button
        self.web_btn = tk.Button(
            self.btn_box,
            text="🌐 网页",
            font=("Segoe UI", 8),
            bg=self.c_btn,
            fg=self.c_text,
            activebackground=self.c_btn_hover,
            activeforeground="#ffffff",
            relief=tk.FLAT,
            bd=0,
            padx=8,
            pady=4,
            cursor="hand2",
            command=self._open_web
        )
        self.web_btn.pack(side=tk.LEFT, padx=3)

        # Setup Drag Handlers across draggable components
        for widget in [self.header_bar, self.title_label, self.container, self.task_label]:
            widget.bind("<Button-1>", self._start_drag)
            widget.bind("<B1-Motion>", self._on_drag)

        if self.is_compact:
            self._apply_compact_mode()

    def _setup_context_menu(self):
        self.menu = tk.Menu(self.root, tearoff=0, bg=self.c_card, fg=self.c_text, activebackground=self.c_btn_hover)
        self.menu.add_command(label="⏳ 切换为倒计时模式", command=lambda: self._set_mode("count_down"))
        self.menu.add_command(label="⏱ 切换为正计时模式", command=lambda: self._set_mode("count_up"))
        self.menu.add_separator()
        self.menu.add_command(label="⚡ 倒计时目标: 15 分钟 (短冲刺)", command=lambda: self._set_countdown_target(15 * 60 * 1000))
        self.menu.add_command(label="🍅 倒计时目标: 25 分钟 (番茄钟)", command=lambda: self._set_countdown_target(25 * 60 * 1000))
        self.menu.add_command(label="🎯 倒计时目标: 45 分钟 (专注)", command=lambda: self._set_countdown_target(45 * 60 * 1000))
        self.menu.add_command(label="⏰ 倒计时目标: 60 分钟 (1小时)", command=lambda: self._set_countdown_target(60 * 60 * 1000))
        self.menu.add_command(label="📋 优先使用网页任务预估时间", command=self._toggle_prefer_task_estimate)
        self.menu.add_separator()
        self.menu.add_command(label="🌐 打开 Super Productivity 网页版", command=self._open_web)
        self.menu.add_command(label="📌 切换窗口置顶", command=self._toggle_pin)
        self.menu.add_command(label="🗕 切换极简悬浮条", command=self._toggle_compact)
        self.menu.add_command(label="💾 立即保存本地备份", command=self._trigger_backup)
        self.menu.add_separator()
        self.menu.add_command(label="✕ 退出本地助手", command=self._on_close)

        for w in [self.root, self.container, self.header_bar, self.body_frame, self.task_label, self.time_label, self.subtitle_label]:
            w.bind("<Button-3>", lambda e: self.menu.tk_popup(e.x_root, e.y_root))

    def _open_countdown_picker(self, event):
        menu = tk.Menu(self.root, tearoff=0, bg=self.c_card, fg=self.c_text, activebackground=self.c_btn_hover)
        menu.add_command(label="15 分钟 (短冲刺)", command=lambda: self._set_countdown_target(15 * 60 * 1000))
        menu.add_command(label="25 分钟 (标准番茄钟)", command=lambda: self._set_countdown_target(25 * 60 * 1000))
        menu.add_command(label="45 分钟 (高效学习)", command=lambda: self._set_countdown_target(45 * 60 * 1000))
        menu.add_command(label="60 分钟 (深度攻坚)", command=lambda: self._set_countdown_target(60 * 60 * 1000))
        menu.add_separator()
        menu.add_command(
            label="✓ 优先使用任务预估时间" if self.prefer_task_estimate else "使用固定倒计时目标",
            command=self._toggle_prefer_task_estimate
        )
        menu.tk_popup(event.x_root, event.y_root)

    def _set_mode(self, mode: str):
        self.timer_mode = mode
        self.btn_mode.config(
            text="⏳ 倒计时" if self.timer_mode == "count_down" else "⏱ 正计时",
            fg=self.c_blue if self.timer_mode == "count_down" else self.c_green
        )
        self._save_window_position()

    def _toggle_mode(self):
        new_mode = "count_up" if self.timer_mode == "count_down" else "count_down"
        self._set_mode(new_mode)

    def _set_countdown_target(self, ms: int):
        self.countdown_target_ms = ms
        self._set_mode("count_down")
        self._save_window_position()

    def _toggle_prefer_task_estimate(self):
        self.prefer_task_estimate = not self.prefer_task_estimate
        self._save_window_position()

    def _start_drag(self, event):
        self._drag_start_x = event.x_root - self.root.winfo_x()
        self._drag_start_y = event.y_root - self.root.winfo_y()

    def _on_drag(self, event):
        x = event.x_root - self._drag_start_x
        y = event.y_root - self._drag_start_y
        self.root.geometry(f"+{x}+{y}")
        self._save_window_position()

    def _toggle_pin(self):
        self.is_always_on_top = not self.is_always_on_top
        self.root.wm_attributes("-topmost", self.is_always_on_top)
        self.btn_pin.config(fg=self.c_blue if self.is_always_on_top else self.c_text_dim)
        self._save_window_position()

    def _toggle_compact(self):
        self.is_compact = not self.is_compact
        self._apply_compact_mode()
        self._save_window_position()

    def _apply_compact_mode(self):
        x = self.root.winfo_x()
        y = self.root.winfo_y()
        if self.is_compact:
            self.root.geometry(f"{self.compact_width}x{self.compact_height}+{x}+{y}")
            self.task_label.pack_forget()
            self.subtitle_label.pack_forget()
            self.backup_btn.pack_forget()
            self.web_btn.pack_forget()
            self.time_label.config(font=("Segoe UI", 13, "bold"))
            self.btn_compact.config(text="🗖")
        else:
            self.root.geometry(f"{self.full_width}{self.full_height}+{x}+{y}")
            self.task_label.pack(fill=tk.X, pady=(0, 2))
            self.subtitle_label.pack(fill=tk.X, pady=(0, 2))
            self.time_label.config(font=("Segoe UI", 21, "bold"))
            self.play_btn.pack(side=tk.LEFT, padx=3)
            self.backup_btn.pack(side=tk.LEFT, padx=3)
            self.web_btn.pack(side=tk.LEFT, padx=3)
            self.btn_compact.config(text="🗕")

    def _open_web(self):
        # Open web URL with seamless auto-handshake hash
        url = f"{self.gh_pages_url}#bridge_token={self.token}&bridge_port={self.port}"
        webbrowser.open(url)

    def _toggle_tracking(self):
        self._send_action("toggle_tracking")

    def _trigger_backup(self):
        self.backup_btn.config(text="⏳ 备份中", bg=self.c_amber)
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
                with urllib.request.urlopen(req, timeout=3):
                    pass
            except Exception:
                pass
        threading.Thread(target=_req, daemon=True).start()

    def _start_poll_thread(self):
        def _poll():
            while True:
                try:
                    # 1. Fetch live tracking state from bridge
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
                            self.time_estimate_ms = st.get("timeEstimateMs", 0)
                            self.tracking_started_at = st.get("trackingStartedAt")
                            self.last_sync_time = time.time()
                            self.web_online = bool(st.get("webOnline"))

                    # 2. Fetch health & backup status
                    with urllib.request.urlopen(f"{self.base_url}/api/health", timeout=2) as resp:
                        h_data = json.loads(resp.read().decode("utf-8"))
                        self.last_backup_status = h_data.get("backup_status", "NOT_STARTED")
                except Exception:
                    self.web_online = False

                time.sleep(0.8)

        t = threading.Thread(target=_poll, daemon=True)
        t.start()

    def _start_timer_loop(self):
        def _tick():
            # Real-time counter advance with full wall-clock accuracy
            # Runs accurately even when Chrome/Web is minimized to taskbar!
            now = time.time()
            if self.is_tracking and self.web_online:
                elapsed_since_sync = int((now - self.last_sync_time) * 1000)
                total_elapsed_ms = self.current_time_ms + elapsed_since_sync
            else:
                total_elapsed_ms = self.current_time_ms

            # Determine Countdown Target
            target_ms = self.countdown_target_ms
            is_using_task_estimate = False
            if self.prefer_task_estimate and self.time_estimate_ms > 0:
                target_ms = self.time_estimate_ms
                is_using_task_estimate = True

            # Calculate display according to active mode
            if self.timer_mode == "count_down":
                remaining_ms = target_ms - total_elapsed_ms
                if remaining_ms >= 0:
                    display_text = format_time(remaining_ms)
                    timer_color = self.c_blue if self.is_tracking else self.c_text
                    overtime = False
                else:
                    # Overtime mode: show +01:23 in warning red
                    display_text = f"+{format_time(abs(remaining_ms))}"
                    timer_color = self.c_red
                    overtime = True

                # Subtitle text
                target_mins = max(1, int(target_ms // 60000))
                elapsed_mins = int(total_elapsed_ms // 60000)
                if overtime:
                    sub_text = f"⏳ 倒计时 (已超时! 目标 {target_mins}m)"
                elif is_using_task_estimate:
                    sub_text = f"⏳ 倒计时 [预估 {target_mins}m | 进度 {elapsed_mins}m]"
                else:
                    sub_text = f"⏳ 倒计时 [番茄目标 {target_mins}m | 进度 {elapsed_mins}m]"
            else:
                # Count-up mode (正计时)
                display_text = format_time(total_elapsed_ms)
                timer_color = self.c_green if self.is_tracking else self.c_text
                sub_text = "⏱ 正计时模式 (点击切换倒计时)"

            self.time_label.config(text=display_text, fg=timer_color)
            if not self.is_compact:
                self.subtitle_label.config(text=sub_text)

            # Task title truncation
            raw_title = self.active_title
            if len(raw_title) > 22:
                raw_title = raw_title[:20] + "..."
            self.task_label.config(text=raw_title)

            # Update status LED, text colors & action buttons
            if not self.web_online:
                self.status_canvas.itemconfig(self.status_dot, fill=self.c_red)
                self.title_label.config(text="SP Mini (网页未连接)", fg=self.c_red)
                self.time_label.config(fg=self.c_text_dim)
                self.play_btn.config(text="▶ 开始", bg="#374151", state=tk.DISABLED)
                if not self.is_compact:
                    self.task_label.config(text="未连接网页版 (点击 🌐 启动)")
            elif self.is_tracking:
                self.status_canvas.itemconfig(self.status_dot, fill=self.c_green)
                mode_str = "倒计时" if self.timer_mode == "count_down" else "正计时"
                self.title_label.config(text=f"SP Mini ({mode_str}中)", fg=self.c_green)
                self.play_btn.config(text="⏸ 暂停", bg="#d97706", state=tk.NORMAL)
            else:
                self.status_canvas.itemconfig(self.status_dot, fill=self.c_amber)
                self.title_label.config(text="SP Mini (已就绪)", fg=self.c_text_dim)
                self.play_btn.config(text="▶ 开始", bg="#15803d", state=tk.NORMAL)

            # Backup button feedback reset
            if self.last_backup_status == "SUCCESS":
                self.backup_btn.config(text="🛡 备份OK", bg=self.c_btn)
            elif self.last_backup_status == "ERROR":
                self.backup_btn.config(text="❌ 备份失败", bg="#b91c1c")

            self.root.after(200, _tick)

        self.root.after(200, _tick)

    def _on_close(self):
        self._save_window_position()
        self.root.destroy()
        sys.exit(0)


def run_mini_window():
    root = tk.Tk()
    app = MiniTimerWidget(root)
    root.mainloop()


if __name__ == "__main__":
    run_mini_window()
