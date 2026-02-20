import customtkinter as ctk

from password_generator import generate_password


class PasswordGeneratorDialog(ctk.CTkToplevel):
    def __init__(self, parent, callback):
        super().__init__(parent)
        self.callback = callback
        self.title("密码生成器")
        self.geometry("450x380")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        self.after(10, self.focus_force)

        pad = {"padx": 20, "pady": (0, 0)}

        # Length
        length_frame = ctk.CTkFrame(self, fg_color="transparent")
        length_frame.pack(fill="x", **pad, pady=(20, 10))
        ctk.CTkLabel(length_frame, text="密码长度:", font=ctk.CTkFont(size=13)).pack(side="left")
        self.length_var = ctk.IntVar(value=16)
        self.length_label = ctk.CTkLabel(length_frame, textvariable=self.length_var,
                                         font=ctk.CTkFont(size=13, weight="bold"), width=30)
        self.length_label.pack(side="right")
        self.length_slider = ctk.CTkSlider(self, from_=8, to=64, number_of_steps=56,
                                           variable=self.length_var, width=380)
        self.length_slider.pack(padx=20, pady=(0, 15))

        # Character types
        type_frame = ctk.CTkFrame(self, corner_radius=10)
        type_frame.pack(fill="x", padx=20, pady=(0, 15))
        ctk.CTkLabel(type_frame, text="字符类型", font=ctk.CTkFont(size=12, weight="bold")).pack(
            anchor="w", padx=15, pady=(10, 5))

        self.upper_var = ctk.BooleanVar(value=True)
        self.lower_var = ctk.BooleanVar(value=True)
        self.digit_var = ctk.BooleanVar(value=True)
        self.special_var = ctk.BooleanVar(value=True)

        checks = [
            ("大写字母 A-Z", self.upper_var),
            ("小写字母 a-z", self.lower_var),
            ("数字 0-9", self.digit_var),
            ("特殊字符 !@#$...", self.special_var),
        ]
        for text, var in checks:
            ctk.CTkCheckBox(type_frame, text=text, variable=var,
                            font=ctk.CTkFont(size=12)).pack(anchor="w", padx=20, pady=2)
        # bottom padding in type_frame
        ctk.CTkLabel(type_frame, text="", height=5).pack()

        # Result
        result_frame = ctk.CTkFrame(self, fg_color="transparent")
        result_frame.pack(fill="x", padx=20, pady=(0, 15))
        self.result_var = ctk.StringVar()
        self.result_entry = ctk.CTkEntry(result_frame, textvariable=self.result_var,
                                         font=ctk.CTkFont(family="Consolas", size=13),
                                         state="readonly", height=36)
        self.result_entry.pack(side="left", fill="x", expand=True)
        ctk.CTkButton(result_frame, text="复制", width=50, height=36, command=self._copy).pack(
            side="left", padx=(8, 0))

        # Buttons
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=(0, 20))
        ctk.CTkButton(btn_frame, text="生成", width=100, command=self._generate).pack(side="left")
        ctk.CTkButton(btn_frame, text="使用此密码", width=120, fg_color="#2ecc71",
                      hover_color="#27ae60", command=self._use).pack(side="left", padx=(10, 0))
        ctk.CTkButton(btn_frame, text="取消", width=80, fg_color="gray",
                      hover_color="#666", command=self.destroy).pack(side="right")

        self._generate()

    def _generate(self):
        try:
            pw = generate_password(
                length=self.length_var.get(),
                use_uppercase=self.upper_var.get(),
                use_lowercase=self.lower_var.get(),
                use_digits=self.digit_var.get(),
                use_special=self.special_var.get(),
            )
            self.result_var.set(pw)
        except ValueError as e:
            self.result_var.set(f"错误: {e}")

    def _copy(self):
        pw = self.result_var.get()
        if pw and not pw.startswith("错误"):
            self.clipboard_clear()
            self.clipboard_append(pw)

    def _use(self):
        pw = self.result_var.get()
        if pw and not pw.startswith("错误"):
            self.callback(pw)
            self.destroy()
