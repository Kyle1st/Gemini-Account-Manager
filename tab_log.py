import time
from datetime import datetime

import customtkinter as ctk


class LogTab:
    """日志 Tab：显示带时间戳和耗时的运行日志。"""

    def __init__(self, parent):
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(1, weight=1)

        btn_frame = ctk.CTkFrame(parent, fg_color="transparent")
        btn_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 5))

        ctk.CTkButton(btn_frame, text="清空日志", width=100, height=32,
                      fg_color=("gray70", "gray35"), hover_color=("gray60", "gray45"),
                      command=self._clear_log).pack(side="left")
        ctk.CTkButton(btn_frame, text="复制日志", width=100, height=32,
                      fg_color=("gray70", "gray35"), hover_color=("gray60", "gray45"),
                      command=self._copy_log).pack(side="left", padx=(10, 0))

        self._auto_scroll_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(btn_frame, text="自动滚动", variable=self._auto_scroll_var,
                        font=ctk.CTkFont(size=12)).pack(side="left", padx=(15, 0))

        self.log_textbox = ctk.CTkTextbox(
            parent, font=ctk.CTkFont(family="Consolas", size=11),
            corner_radius=8, state="disabled",
        )
        self.log_textbox.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))

        self._last_time: float = 0.0
        self._status_callback = None  # set by main after construction

    # ── Public API ─────────────────────────────────────────────

    def append(self, message: str):
        """Append a timestamped log entry with elapsed time since last entry."""
        now = time.time()
        ts = datetime.now().strftime("%H:%M:%S.") + f"{int(now * 1000) % 1000:03d}"
        elapsed_str = f" (+{now - self._last_time:.1f}s)" if self._last_time > 0 else ""
        self._last_time = now

        line = f"[{ts}]{elapsed_str} {message}\n"
        self.log_textbox.configure(state="normal")
        self.log_textbox.insert("end", line)
        self.log_textbox.configure(state="disabled")
        if self._auto_scroll_var.get():
            self.log_textbox.see("end")

    def reset_timer(self):
        self._last_time = 0.0

    # ── Internal ────────────────────────────────────────────────

    def _clear_log(self):
        self.log_textbox.configure(state="normal")
        self.log_textbox.delete("1.0", "end")
        self.log_textbox.configure(state="disabled")
        self._last_time = 0.0

    def _copy_log(self):
        text = self.log_textbox.get("1.0", "end").strip()
        if text:
            self.log_textbox.clipboard_clear()
            self.log_textbox.clipboard_append(text)
            if self._status_callback:
                self._status_callback("日志已复制到剪贴板")
