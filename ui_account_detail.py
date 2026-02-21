import customtkinter as ctk
from tkinter import messagebox

from account_manager import AccountManager, TAG_OPTIONS
from totp_engine import TOTPEngine
from ui_totp_display import TOTPDisplay
from ui_password_dialog import PasswordGeneratorDialog


class AccountDetailPanel(ctk.CTkScrollableFrame):
    def __init__(self, parent, account_manager, status_callback):
        super().__init__(parent, corner_radius=0, fg_color=("gray95", "gray15"))
        self.account_manager = account_manager
        self.status_callback = status_callback
        self.current_account_id: str | None = None

        self._build_form()
        self.clear_form()

    def _build_form(self):
        font = ctk.CTkFont(size=13)
        label_font = ctk.CTkFont(size=12, weight="bold")

        # Title
        self.title_label = ctk.CTkLabel(self, text="新建账号",
                                         font=ctk.CTkFont(size=18, weight="bold"), fg_color=("gray95", "gray15"))
        self.title_label.pack(anchor="w", padx=20, pady=(15, 10))

        # Quick paste input
        ctk.CTkLabel(self, text="快速导入", font=label_font, fg_color=("gray95", "gray15")).pack(anchor="w", padx=20, pady=(0, 3))
        quick_frame = ctk.CTkFrame(self, fg_color=("gray95", "gray15"))
        quick_frame.pack(fill="x", padx=20, pady=(0, 12))
        self.quick_var = ctk.StringVar()
        quick_entry = ctk.CTkEntry(quick_frame, textvariable=self.quick_var, font=font,
                     height=36, placeholder_text="邮箱----密码----辅助邮箱----TOTP密钥")
        quick_entry.pack(side="left", fill="x", expand=True)
        ctk.CTkButton(quick_frame, text="填入", width=60, height=36,
                      fg_color="#e67e22", hover_color="#d35400",
                      command=self._on_quick_paste).pack(side="left", padx=(6, 0))
        ctk.CTkButton(quick_frame, text="直接保存", width=80, height=36,
                      fg_color="#2ecc71", hover_color="#27ae60",
                      command=self._on_quick_save).pack(side="left", padx=(6, 0))

        # Email
        ctk.CTkLabel(self, text="账号邮箱", font=label_font, fg_color=("gray95", "gray15")).pack(anchor="w", padx=20, pady=(0, 3))
        self.email_var = ctk.StringVar()
        ctk.CTkEntry(self, textvariable=self.email_var, font=font,
                     height=36, placeholder_text="example@gmail.com").pack(
            fill="x", padx=20, pady=(0, 12))

        # Password
        ctk.CTkLabel(self, text="密码", font=label_font, fg_color=("gray95", "gray15")).pack(anchor="w", padx=20, pady=(0, 3))
        pw_frame = ctk.CTkFrame(self, fg_color=("gray95", "gray15"))
        pw_frame.pack(fill="x", padx=20, pady=(0, 4))
        self.password_var = ctk.StringVar()
        self.password_entry = ctk.CTkEntry(pw_frame, textvariable=self.password_var,
                                            font=font, show="*", height=36)
        self.password_entry.pack(side="left", fill="x", expand=True)
        self.show_pw_var = ctk.BooleanVar(value=False)
        ctk.CTkButton(pw_frame, text="显示", width=50, height=36,
                      fg_color=("gray75", "gray30"), hover_color=("gray65", "gray40"),
                      command=self._toggle_password).pack(side="left", padx=(6, 0))
        ctk.CTkButton(pw_frame, text="复制", width=50, height=36,
                      fg_color=("gray75", "gray30"), hover_color=("gray65", "gray40"),
                      command=self._copy_password).pack(side="left", padx=(6, 0))

        btn_row = ctk.CTkFrame(self, fg_color=("gray95", "gray15"))
        btn_row.pack(fill="x", padx=20, pady=(0, 12))
        ctk.CTkButton(btn_row, text="生成随机密码", width=130, height=30,
                      font=ctk.CTkFont(size=12),
                      command=self._on_generate_password).pack(side="left")

        # Tags
        ctk.CTkLabel(self, text="账号标签", font=label_font, fg_color=("gray95", "gray15")).pack(anchor="w", padx=20, pady=(0, 3))
        tag_frame = ctk.CTkFrame(self, fg_color=("gray95", "gray15"))
        tag_frame.pack(fill="x", padx=20, pady=(0, 12))
        self.tag_vars: dict[str, ctk.BooleanVar] = {}
        tag_colors = {"家庭组": "#2980b9", "成品号": "#27ae60", "资格号": "#8e44ad"}
        for tag_name in TAG_OPTIONS:
            var = ctk.BooleanVar(value=False)
            self.tag_vars[tag_name] = var
            ctk.CTkCheckBox(
                tag_frame, text=tag_name, variable=var,
                font=ctk.CTkFont(size=12), checkbox_width=20, checkbox_height=20,
                corner_radius=4, fg_color=tag_colors.get(tag_name, "#3498db"),
                hover_color=tag_colors.get(tag_name, "#3498db"), bg_color=("gray95", "gray15")
            ).pack(side="left", padx=(0, 15))

        self.cookie_var = ctk.BooleanVar(value=False)
        self.cookie_checkbox = ctk.CTkCheckBox(
            tag_frame, text="已存 Cookie", variable=self.cookie_var,
            font=ctk.CTkFont(size=12), checkbox_width=20, checkbox_height=20,
            corner_radius=4, fg_color="#e67e22", hover_color="#d35400",
            bg_color=("gray95", "gray15"), state="disabled",
            text_color=("gray10", "gray90"), text_color_disabled=("gray10", "gray90")
        )
        self.cookie_checkbox.pack(side="left", padx=(10, 0))

        # Recovery email
        ctk.CTkLabel(self, text="辅助邮箱", font=label_font, fg_color=("gray95", "gray15")).pack(anchor="w", padx=20, pady=(0, 3))
        self.recovery_var = ctk.StringVar()
        ctk.CTkEntry(self, textvariable=self.recovery_var, font=font,
                     height=36, placeholder_text="recovery@example.com").pack(
            fill="x", padx=20, pady=(0, 12))

        # TOTP secret
        ctk.CTkLabel(self, text="TOTP 密钥", font=label_font, fg_color=("gray95", "gray15")).pack(anchor="w", padx=20, pady=(0, 3))
        totp_frame = ctk.CTkFrame(self, fg_color=("gray95", "gray15"))
        totp_frame.pack(fill="x", padx=20, pady=(0, 12))
        self.totp_var = ctk.StringVar()
        self.totp_var.trace_add("write", self._on_totp_changed)
        ctk.CTkEntry(totp_frame, textvariable=self.totp_var,
                     font=ctk.CTkFont(family="Consolas", size=13),
                     height=36, placeholder_text="Base32 密钥").pack(
            side="left", fill="x", expand=True)
        ctk.CTkButton(totp_frame, text="复制", width=50, height=36,
                      fg_color=("gray75", "gray30"), hover_color=("gray65", "gray40"),
                      command=self._copy_totp_secret).pack(side="left", padx=(6, 0))

        # TOTP display
        self.totp_display = TOTPDisplay(self, status_callback=self.status_callback)
        self.totp_display.pack(fill="x", padx=20, pady=(0, 12))


        # Notes
        ctk.CTkLabel(self, text="备注", font=label_font, fg_color=("gray95", "gray15")).pack(anchor="w", padx=20, pady=(0, 3))
        self.notes_textbox = ctk.CTkTextbox(self, height=80, font=font, corner_radius=8)
        self.notes_textbox.pack(fill="x", padx=20, pady=(0, 15))

        # Action buttons
        action_frame = ctk.CTkFrame(self, fg_color=("gray95", "gray15"))
        action_frame.pack(fill="x", padx=20, pady=(0, 20))
        ctk.CTkButton(action_frame, text="保存", width=120, height=38,
                      font=ctk.CTkFont(size=13, weight="bold"),
                      command=self._on_save).pack(side="left")
        ctk.CTkButton(action_frame, text="取消", width=100, height=38,
                      font=ctk.CTkFont(size=13),
                      fg_color=("gray70", "gray35"), hover_color=("gray60", "gray45"),
                      command=self._on_cancel).pack(side="left", padx=(10, 0))

    def load_account(self, account_id: str):
        acc = self.account_manager.get_account(account_id)
        if not acc:
            return
        self.current_account_id = account_id
        self.title_label.configure(text="编辑账号")
        self.email_var.set(acc["email"])
        self.password_var.set(acc["password"])
        self.recovery_var.set(acc.get("recovery_email", ""))
        self.totp_var.set(acc.get("totp_secret", ""))
        # Load tags
        acc_tags = acc.get("tags", [])
        for tag_name, var in self.tag_vars.items():
            var.set(tag_name in acc_tags)
            
        # Load Cookie status
        self.cookie_var.set(bool(acc.get("cookies")))
        self.notes_textbox.delete("1.0", "end")
        self.notes_textbox.insert("1.0", acc.get("notes", ""))

    def clear_form(self):
        self.current_account_id = None
        self.title_label.configure(text="新建账号")
        self.email_var.set("")
        self.password_var.set("")
        self.recovery_var.set("")
        self.totp_var.set("")
        for var in self.tag_vars.values():
            var.set(False)
        self.cookie_var.set(False)
        self.notes_textbox.delete("1.0", "end")
        self.totp_display.clear()

    def _toggle_password(self):
        showing = self.show_pw_var.get()
        self.show_pw_var.set(not showing)
        self.password_entry.configure(show="" if not showing else "*")

    def _copy_password(self):
        pw = self.password_var.get()
        if pw:
            self.clipboard_clear()
            self.clipboard_append(pw)
            self.status_callback("密码已复制到剪贴板")

    def _on_generate_password(self):
        PasswordGeneratorDialog(self.winfo_toplevel(), self._set_generated_password)

    def _set_generated_password(self, password: str):
        self.password_var.set(password)

    def _on_quick_paste(self):
        """Parse ---- format line and fill into form fields."""
        text = self.quick_var.get().strip()
        if not text:
            messagebox.showwarning("提示", "请先粘贴 ---- 格式的账号数据")
            return
        parsed = AccountManager.parse_batch_line(text)
        if not parsed or not parsed["email"]:
            messagebox.showwarning("提示", "格式无效，请使用：邮箱----密码----辅助邮箱----TOTP密钥")
            return
        self.clear_form()
        self.email_var.set(parsed["email"])
        self.password_var.set(parsed["password"])
        self.recovery_var.set(parsed["recovery_email"])
        self.totp_var.set(parsed["totp_secret"])
        self.quick_var.set("")
        self.status_callback(f"已填入: {parsed['email']}")

    def _on_quick_save(self):
        """Parse ---- format line and save directly."""
        text = self.quick_var.get().strip()
        if not text:
            messagebox.showwarning("提示", "请先粘贴 ---- 格式的账号数据")
            return
        parsed = AccountManager.parse_batch_line(text)
        if not parsed or not parsed["email"]:
            messagebox.showwarning("提示", "格式无效，请使用：邮箱----密码----辅助邮箱----TOTP密钥")
            return
        totp_secret = parsed["totp_secret"]
        if totp_secret:
            if not TOTPEngine.validate_secret(totp_secret):
                messagebox.showwarning("提示", "TOTP密钥格式无效，请检查")
                return
            totp_secret = TOTPEngine.clean_secret(totp_secret)
        acc = self.account_manager.add_account(
            email=parsed["email"],
            password=parsed["password"],
            recovery_email=parsed["recovery_email"],
            totp_secret=totp_secret,
        )
        self.current_account_id = acc["id"]
        self.email_var.set(parsed["email"])
        self.password_var.set(parsed["password"])
        self.recovery_var.set(parsed["recovery_email"])
        self.totp_var.set(totp_secret)
        self.quick_var.set("")
        self.title_label.configure(text="编辑账号")
        self.status_callback(f"已保存: {parsed['email']}")
        self.event_generate("<<AccountSaved>>")

    def _copy_totp_secret(self):
        secret = self.totp_var.get().strip()
        if secret:
            self.clipboard_clear()
            self.clipboard_append(secret)
            self.status_callback("TOTP 密钥已复制到剪贴板")

    def _on_totp_changed(self, *args):
        secret = self.totp_var.get().strip()
        self.totp_display.set_secret(secret)

    def _on_save(self):
        email = self.email_var.get().strip()
        password = self.password_var.get()
        recovery = self.recovery_var.get().strip()
        totp_secret = self.totp_var.get().strip()
        notes = self.notes_textbox.get("1.0", "end").strip()
        tags = [t for t, v in self.tag_vars.items() if v.get()]

        if not email:
            messagebox.showwarning("提示", "账号邮箱不能为空")
            return

        if totp_secret and not TOTPEngine.validate_secret(totp_secret):
            messagebox.showwarning("提示", "TOTP密钥格式无效，请检查")
            return
        if totp_secret:
            totp_secret = TOTPEngine.clean_secret(totp_secret)

        if self.current_account_id:
            self.account_manager.update_account(
                self.current_account_id,
                email=email, password=password, recovery_email=recovery,
                totp_secret=totp_secret, notes=notes, tags=tags,
            )
            self.status_callback(f"已更新: {email}")
        else:
            acc = self.account_manager.add_account(
                email=email, password=password, recovery_email=recovery,
                totp_secret=totp_secret, notes=notes, tags=tags,
            )
            self.current_account_id = acc["id"]
            self.status_callback(f"已添加: {email}")

        self.event_generate("<<AccountSaved>>")

    def _on_cancel(self):
        if self.current_account_id:
            self.load_account(self.current_account_id)
        else:
            self.clear_form()
