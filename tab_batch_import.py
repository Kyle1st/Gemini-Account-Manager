import customtkinter as ctk
from tkinter import messagebox

from account_manager import AccountManager
from ui_account_selector import AccountSelectionPanel


class BatchImportTab:
    """批量导入 Tab：支持重复账号检测（跳过/覆盖/逐一确认）。"""

    def __init__(self, parent, account_manager: AccountManager,
                 status_callback, on_import_done):
        self.account_manager = account_manager
        self.status_callback = status_callback
        self.on_import_done = on_import_done  # callable: refresh list + count

        parent.grid_columnconfigure(0, weight=1)
        parent.grid_columnconfigure(1, weight=2)
        parent.grid_rowconfigure(0, weight=1)

        # Left Side (Selection Panel)
        self.selector_panel = AccountSelectionPanel(parent, account_manager)
        self.selector_panel.grid(row=0, column=0, sticky="nsew", padx=(15, 5), pady=15)

        # Right Side (Import Area)
        right_frame = ctk.CTkFrame(parent, fg_color="transparent")
        right_frame.grid(row=0, column=1, sticky="nsew", padx=(5, 15))
        right_frame.grid_columnconfigure(0, weight=1)
        right_frame.grid_rowconfigure(1, weight=1)

        info_text = (
            "格式：邮箱----密码----辅助邮箱----TOTP密钥\n"
            "示例：user@gmail.com----mypassword----recovery@site.com----JBSWY3DPEHPK3PXP\n"
            "密码、辅助邮箱、TOTP密钥可省略"
        )
        ctk.CTkLabel(right_frame, text=info_text, font=ctk.CTkFont(size=12),
                     justify="left", anchor="w").grid(
            row=0, column=0, sticky="ew", padx=15, pady=(10, 5))

        self.textbox = ctk.CTkTextbox(
            right_frame, font=ctk.CTkFont(family="Consolas", size=12), corner_radius=8)
        self.textbox.grid(row=1, column=0, sticky="nsew", padx=15, pady=5)

        btn_frame = ctk.CTkFrame(right_frame, fg_color="transparent")
        btn_frame.grid(row=2, column=0, sticky="ew", padx=15, pady=(5, 15))

        ctk.CTkButton(btn_frame, text="导入全部", width=120, height=36,
                      font=ctk.CTkFont(size=13, weight="bold"),
                      command=self._on_import).pack(side="left")
        ctk.CTkButton(btn_frame, text="📥 加载选中账号", width=130, height=36,
                      font=ctk.CTkFont(size=13),
                      fg_color="gray60", hover_color="gray50",
                      command=self._on_load_existing).pack(side="left", padx=(10, 0))
        ctk.CTkButton(btn_frame, text="清空", width=80, height=36,
                      fg_color=("gray70", "gray35"), hover_color=("gray60", "gray45"),
                      command=lambda: self.textbox.delete("1.0", "end")
                      ).pack(side="left", padx=(10, 0))

        self.result_var = ctk.StringVar(value="")
        ctk.CTkLabel(btn_frame, textvariable=self.result_var,
                     font=ctk.CTkFont(size=12)).pack(side="left", padx=(15, 0))

    # ── Import logic ───────────────────────────────────────────

    def _on_load_existing(self):
        accounts = self.selector_panel.get_selected_accounts()
        if not accounts:
            messagebox.showwarning("提示", "请在右侧先勾选需要加载的账号")
            return
        self.textbox.delete("1.0", "end")
        lines = [AccountManager.format_line(acc) for acc in accounts]
        self.textbox.insert("1.0", "\n".join(lines))
        self.status_callback(f"已加载 {len(accounts)} 个选中账号")

    def _on_import(self):
        text = self.textbox.get("1.0", "end").strip()
        if not text:
            messagebox.showwarning("提示", "请先粘贴账号数据")
            return

        parsed_lines = []
        skipped_parse = 0
        for line in text.splitlines():
            parsed = AccountManager.parse_batch_line(line)
            if parsed:
                parsed_lines.append(parsed)
            else:
                skipped_parse += 1

        if not parsed_lines:
            messagebox.showwarning("提示", f"未解析到有效行（跳过 {skipped_parse} 行）")
            return

        # Classify: new vs duplicate
        existing_emails = {acc["email"] for acc in self.account_manager.get_all_accounts()}
        new_lines = [p for p in parsed_lines if p["email"] not in existing_emails]
        dup_lines = [p for p in parsed_lines if p["email"] in existing_emails]

        # If no duplicates, just import
        if not dup_lines:
            self._do_import(new_lines, [], "skip")
            return

        # Ask user how to handle duplicates
        strategy = self._ask_dup_strategy(len(new_lines), dup_lines)
        if strategy is None:
            return  # user cancelled

        if strategy == "confirm":
            overwrite_list = self._confirm_each(dup_lines)
            if overwrite_list is None:
                return
            self._do_import(new_lines, overwrite_list, "overwrite_list")
        else:
            self._do_import(new_lines, dup_lines, strategy)

    def _ask_dup_strategy(self, new_count: int, dup_lines: list) -> str | None:
        """Show a dialog to choose duplicate handling strategy.
        Returns 'skip', 'overwrite', 'confirm', or None (cancel)."""
        dialog = ctk.CTkToplevel()
        dialog.title("重复账号处理")
        dialog.geometry("420x280")
        dialog.resizable(False, False)
        dialog.grab_set()
        dialog.transient()

        result = [None]

        ctk.CTkLabel(dialog,
                     text=f"发现 {len(dup_lines)} 个重复账号（邮箱已存在），{new_count} 个新账号。\n请选择重复账号的处理方式：",
                     font=ctk.CTkFont(size=13), wraplength=380, justify="left"
                     ).pack(padx=20, pady=(20, 10))

        # Show first few duplicates
        preview = "\n".join(p["email"] for p in dup_lines[:5])
        if len(dup_lines) > 5:
            preview += f"\n...等共 {len(dup_lines)} 个"
        ctk.CTkLabel(dialog, text=preview, font=ctk.CTkFont(family="Consolas", size=11),
                     justify="left", text_color=("gray40", "gray70")).pack(padx=20, pady=(0, 15))

        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack(padx=20, pady=(0, 10))

        def pick(val):
            result[0] = val
            dialog.destroy()

        ctk.CTkButton(btn_frame, text="全部跳过", width=110, height=34,
                      fg_color=("gray70", "gray35"), hover_color=("gray60", "gray45"),
                      command=lambda: pick("skip")).pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="全部覆盖", width=110, height=34,
                      fg_color="#e67e22", hover_color="#d35400",
                      command=lambda: pick("overwrite")).pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="逐一确认", width=110, height=34,
                      fg_color="#3498db", hover_color="#2980b9",
                      command=lambda: pick("confirm")).pack(side="left", padx=5)

        ctk.CTkButton(dialog, text="取消", width=80, height=30,
                      fg_color=("gray70", "gray35"), hover_color=("gray60", "gray45"),
                      command=dialog.destroy).pack(pady=(0, 15))

        dialog.wait_window()
        return result[0]

    def _confirm_each(self, dup_lines: list) -> list | None:
        """Let user pick which duplicates to overwrite. Returns list or None (cancel)."""
        dialog = ctk.CTkToplevel()
        dialog.title("选择要覆盖的重复账号")
        dialog.geometry("420x500")
        dialog.resizable(False, True)
        dialog.grab_set()
        dialog.transient()

        result = [None]

        ctk.CTkLabel(dialog, text="勾选要覆盖（更新）的账号：",
                     font=ctk.CTkFont(size=13, weight="bold")).pack(
            anchor="w", padx=15, pady=(15, 5))

        check_vars = []
        scroll = ctk.CTkScrollableFrame(dialog, corner_radius=6)
        scroll.pack(fill="both", expand=True, padx=15, pady=(0, 10))

        for p in dup_lines:
            var = ctk.BooleanVar(value=False)
            ctk.CTkCheckBox(scroll, text=p["email"], variable=var,
                            font=ctk.CTkFont(size=12), height=30,
                            corner_radius=4).pack(fill="x", pady=1)
            check_vars.append((p, var))

        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack(fill="x", padx=15, pady=(0, 15))

        def confirm():
            result[0] = [p for p, var in check_vars if var.get()]
            dialog.destroy()

        ctk.CTkButton(btn_frame, text="确认", width=100, height=34,
                      fg_color="#2ecc71", hover_color="#27ae60",
                      command=confirm).pack(side="left")
        ctk.CTkButton(btn_frame, text="取消", width=80, height=34,
                      fg_color=("gray70", "gray35"), hover_color=("gray60", "gray45"),
                      command=dialog.destroy).pack(side="left", padx=(10, 0))

        dialog.wait_window()
        return result[0]

    def _do_import(self, new_lines: list, dup_lines: list, strategy: str):
        """Perform the actual import."""
        imported = 0
        updated = 0

        for p in new_lines:
            self.account_manager.add_account(
                email=p["email"], password=p["password"],
                recovery_email=p["recovery_email"], totp_secret=p["totp_secret"],
            )
            imported += 1

        if strategy == "overwrite":
            overwrite_targets = dup_lines
        elif strategy == "overwrite_list":
            overwrite_targets = dup_lines  # already filtered by _confirm_each
        else:
            overwrite_targets = []

        if overwrite_targets:
            all_accs = self.account_manager.get_all_accounts()
            email_to_id = {acc["email"]: acc["id"] for acc in all_accs}
            for p in overwrite_targets:
                acc_id = email_to_id.get(p["email"])
                if acc_id:
                    fields = {}
                    if p["password"]:
                        fields["password"] = p["password"]
                    if p["recovery_email"]:
                        fields["recovery_email"] = p["recovery_email"]
                    if p["totp_secret"]:
                        fields["totp_secret"] = p["totp_secret"]
                    if fields:
                        self.account_manager.update_account(acc_id, **fields)
                        updated += 1

        self.on_import_done()
        skipped = len(dup_lines) - updated if strategy != "overwrite_list" else 0
        msg = f"成功导入 {imported} 个"
        if updated:
            msg += f"，覆盖 {updated} 个"
        if skipped:
            msg += f"，跳过重复 {skipped} 个"
        self.result_var.set(msg)
        self.status_callback(f"批量导入 {imported} 个账号")
