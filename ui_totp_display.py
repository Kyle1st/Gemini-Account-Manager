import customtkinter as ctk

from totp_engine import TOTPEngine


class TOTPDisplay(ctk.CTkFrame):

    def __init__(self, parent, status_callback=None):
        super().__init__(parent, fg_color=("gray95", "gray15"))
        self.current_secret = ""
        self.status_callback = status_callback

        title_frame = ctk.CTkFrame(self, fg_color=("gray95", "gray15"))
        title_frame.pack(fill="x", pady=(0, 5))
        ctk.CTkLabel(title_frame, text="2FA 验证码", font=ctk.CTkFont(size=13, weight="bold"), fg_color=("gray95", "gray15")).pack(side="left")
        
        # Add copy button directly to title row or card bottom? 
        # Title row is cleaner.
        self.copy_btn = ctk.CTkButton(
            title_frame, text="📋 复制", width=60, height=24,
            font=ctk.CTkFont(size=12),
            fg_color=("gray75", "gray30"), hover_color=("gray65", "gray40"),
            command=self._copy_code
        )
        self.copy_btn.pack(side="right")

        card = ctk.CTkFrame(self, corner_radius=10)
        card.pack(fill="x", pady=(0, 5))

        self.code_var = ctk.StringVar(value="— — — — — —")
        self.code_label = ctk.CTkLabel(
            card, textvariable=self.code_var,
            font=ctk.CTkFont(family="Consolas", size=32, weight="bold"),
            text_color=("#1a73e8", "#8ab4f8"),
        )
        self.code_label.pack(pady=(15, 5))

        self.progress_var = ctk.DoubleVar(value=1.0)
        self.progress_bar = ctk.CTkProgressBar(card, variable=self.progress_var, width=280, height=6)
        self.progress_bar.pack(pady=(0, 5), padx=20)

        self.seconds_var = ctk.StringVar(value="")
        self.seconds_label = ctk.CTkLabel(card, textvariable=self.seconds_var, font=ctk.CTkFont(size=11))
        self.seconds_label.pack(pady=(0, 12))
        
    def _copy_code(self):
        if not self.current_secret:
            return
        code = TOTPEngine.generate_code(self.current_secret)
        if code:
            self.clipboard_clear()
            self.clipboard_append(code)
            if self.status_callback:
                self.status_callback(f"验证码 {code} 已复制")

    def set_secret(self, secret: str):
        self.current_secret = secret.strip() if secret else ""
        if self.current_secret:
            self.tick()
        else:
            self.clear()

    def clear(self):
        self.current_secret = ""
        self.code_var.set("— — — — — —")
        self.seconds_var.set("")
        self.progress_var.set(1.0)

    def tick(self):
        if not self.current_secret:
            return
        remaining = TOTPEngine.get_remaining_seconds()
        code = TOTPEngine.generate_code(self.current_secret)
        if code:
            spaced = "  ".join(code[:3]) + "   " + "  ".join(code[3:])
            self.code_var.set(spaced)
            self.progress_var.set(remaining / 30.0)
            self.seconds_var.set(f"{remaining}s 后刷新")
        else:
            self.code_var.set("密钥无效")
            self.seconds_var.set("")
            self.progress_var.set(0)
