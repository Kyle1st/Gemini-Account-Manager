import threading
import queue
import time
import random

import customtkinter as ctk
from tkinter import messagebox

from account_manager import AccountManager
from google_pw_changer import GooglePasswordChanger
from password_generator import generate_password
from ui_account_selector import AccountSelectionPanel


class PwChangeTab:
    """批量改密 Tab：接入 AccountSelectionPanel，支持本地改密和在线改密。"""

    def __init__(self, parent, account_manager: AccountManager,
                 log_callback, status_callback, on_data_changed):
        self.account_manager = account_manager
        self.log_callback = log_callback
        self.status_callback = status_callback
        self.on_data_changed = on_data_changed
        self._parent = parent

        parent.grid_columnconfigure(1, weight=1)
        parent.grid_rowconfigure(0, weight=1)

        # ── Left: Account selection panel ──
        self.selector = AccountSelectionPanel(parent, account_manager)
        self.selector.grid(row=0, column=0, sticky="nsw", padx=(10, 5), pady=10)

        # ── Right: Controls ──
        right = ctk.CTkFrame(parent, fg_color="transparent")
        right.grid(row=0, column=1, sticky="nsew", padx=(5, 10), pady=10)
        right.grid_columnconfigure(0, weight=1)
        right.grid_rowconfigure(4, weight=1)

        # Row 0: Options
        opt_frame = ctk.CTkFrame(right, fg_color="transparent")
        opt_frame.grid(row=0, column=0, sticky="ew", pady=(0, 5))

        ctk.CTkLabel(opt_frame, text="密码长度:", font=ctk.CTkFont(size=12)).pack(side="left")
        self.pw_len_var = ctk.IntVar(value=16)
        ctk.CTkSlider(opt_frame, from_=8, to=32, number_of_steps=24,
                      variable=self.pw_len_var, width=180).pack(side="left", padx=(5, 5))
        self.pw_len_label = ctk.CTkLabel(opt_frame, text="16", width=30,
                                          font=ctk.CTkFont(size=12))
        self.pw_len_label.pack(side="left")
        self.pw_len_var.trace_add("write",
                                  lambda *_: self.pw_len_label.configure(text=str(self.pw_len_var.get())))

        ctk.CTkButton(opt_frame, text="生成随机密码", width=130, height=32,
                      fg_color="#e67e22", hover_color="#d35400",
                      command=self._on_batch_pwchange).pack(side="left", padx=(20, 0))
        ctk.CTkButton(opt_frame, text="加载选中账号", width=130, height=32,
                      fg_color=("gray70", "gray35"), hover_color=("gray60", "gray45"),
                      command=self._on_load_current_accounts).pack(side="left", padx=(10, 0))

        # Row 1: Custom password
        custom_frame = ctk.CTkFrame(right, fg_color="transparent")
        custom_frame.grid(row=1, column=0, sticky="ew", pady=5)
        ctk.CTkLabel(custom_frame, text="自定义密码:", font=ctk.CTkFont(size=12)).pack(side="left")
        self.custom_pw_var = ctk.StringVar()
        ctk.CTkEntry(custom_frame, textvariable=self.custom_pw_var,
                     font=ctk.CTkFont(family="Consolas", size=12), height=32, width=250,
                     placeholder_text="输入你想要的新密码").pack(side="left", padx=(5, 0))
        ctk.CTkButton(custom_frame, text="应用到选中账号", width=130, height=32,
                      fg_color="#3498db", hover_color="#2980b9",
                      command=self._on_apply_custom_pw).pack(side="left", padx=(10, 0))

        # Row 3: Label
        ctk.CTkLabel(right, text="编辑区（格式：邮箱----密码----辅助邮箱----TOTP密钥）",
                     font=ctk.CTkFont(size=12, weight="bold")).grid(
            row=3, column=0, sticky="w", pady=(10, 3))

        # Row 4: Textbox
        self.pwchange_textbox = ctk.CTkTextbox(
            right, font=ctk.CTkFont(family="Consolas", size=12), corner_radius=8)
        self.pwchange_textbox.grid(row=4, column=0, sticky="nsew", pady=(0, 5))

        # Row 5: Buttons
        bottom = ctk.CTkFrame(right, fg_color="transparent")
        bottom.grid(row=5, column=0, sticky="ew", pady=(5, 5))
        ctk.CTkButton(bottom, text="应用新密码并保存", width=160, height=36,
                      font=ctk.CTkFont(size=13, weight="bold"),
                      fg_color="#2ecc71", hover_color="#27ae60",
                      command=self._on_apply_pwchange).pack(side="left")
        ctk.CTkButton(bottom, text="复制结果", width=100, height=36,
                      fg_color=("gray70", "gray35"), hover_color=("gray60", "gray45"),
                      command=self._copy_pwchange_result).pack(side="left", padx=(10, 0))

        # Row 6: Real password change section
        real_frame = ctk.CTkFrame(right, fg_color="transparent")
        real_frame.grid(row=6, column=0, sticky="ew", pady=(5, 3))
        ctk.CTkLabel(real_frame, text="在线改密（通过浏览器自动登录 Google 修改密码）",
                     font=ctk.CTkFont(size=12, weight="bold")).pack(side="left")

        # Row 7: Real change buttons
        real_btn_frame = ctk.CTkFrame(right, fg_color="transparent")
        real_btn_frame.grid(row=7, column=0, sticky="ew", pady=(0, 5))

        self.real_pwchange_btn = ctk.CTkButton(
            real_btn_frame, text="执行真正改密", width=160, height=36,
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="#e74c3c", hover_color="#c0392b",
            command=self._on_real_pwchange,
        )
        self.real_pwchange_btn.pack(side="left")

        self.headless_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            real_btn_frame, text="后台静默模式", variable=self.headless_var,
            font=ctk.CTkFont(size=12),
        ).pack(side="left", padx=(15, 0))

        self.stop_pwchange_btn = ctk.CTkButton(
            real_btn_frame, text="停止", width=80, height=36,
            fg_color=("gray70", "gray35"), hover_color=("gray60", "gray45"),
            command=self._on_stop_pwchange, state="disabled",
        )
        self.stop_pwchange_btn.pack(side="left", padx=(10, 0))

        # Row 8: Progress
        self.pwchange_progress_var = ctk.StringVar(value="")
        ctk.CTkLabel(
            right, textvariable=self.pwchange_progress_var,
            font=ctk.CTkFont(size=12), anchor="w",
        ).grid(row=8, column=0, sticky="ew", pady=(0, 10))

        self._pending_pw_changes: dict[str, str] = {}
        self._pwchange_queue: queue.Queue = queue.Queue()
        self._pwchange_running = False
        self._pwchange_stop_flag = False

    # ── Local password operations ─────────────────────────

    def _on_apply_custom_pw(self):
        custom_pw = self.custom_pw_var.get()
        if not custom_pw:
            messagebox.showwarning("提示", "请先输入自定义密码")
            return
        accounts = self.selector.get_selected_accounts()
        if not accounts:
            messagebox.showwarning("提示", "请先在左侧勾选需要修改的账号")
            return
        self.pwchange_textbox.delete("1.0", "end")
        lines = [AccountManager.format_line({
            "email": acc["email"], "password": custom_pw,
            "recovery_email": acc.get("recovery_email", ""),
            "totp_secret": acc.get("totp_secret", ""),
        }) for acc in accounts]
        self.pwchange_textbox.insert("1.0", "\n".join(lines))
        self.status_callback(f"已为 {len(accounts)} 个账号设置自定义密码（未保存）")

    def _on_load_current_accounts(self):
        accounts = self.selector.get_selected_accounts()
        if not accounts:
            messagebox.showwarning("提示", "请先在左侧勾选需要加载的账号")
            return
        self.pwchange_textbox.delete("1.0", "end")
        lines = [AccountManager.format_line(acc) for acc in accounts]
        self.pwchange_textbox.insert("1.0", "\n".join(lines))
        self.status_callback(f"已加载 {len(accounts)} 个账号，可直接编辑密码")

    def _on_batch_pwchange(self):
        accounts = self.selector.get_selected_accounts()
        if not accounts:
            messagebox.showwarning("提示", "请先在左侧勾选需要修改的账号")
            return
        length = self.pw_len_var.get()
        self._pending_pw_changes.clear()
        self.pwchange_textbox.delete("1.0", "end")
        lines = []
        for acc in accounts:
            new_pw = generate_password(length=length)
            self._pending_pw_changes[acc["id"]] = new_pw
            lines.append(AccountManager.format_line({
                "email": acc["email"], "password": new_pw,
                "recovery_email": acc.get("recovery_email", ""),
                "totp_secret": acc.get("totp_secret", ""),
            }))
        self.pwchange_textbox.insert("1.0", "\n".join(lines))
        self.status_callback(f"已为 {len(accounts)} 个账号生成新密码（未保存）")

    def _on_apply_pwchange(self):
        text = self.pwchange_textbox.get("1.0", "end").strip()
        if not text:
            messagebox.showwarning("提示", "文本框为空，请先生成或手动输入密码")
            return
        all_accounts = self.account_manager.get_all_accounts()
        email_to_id = {acc["email"]: acc["id"] for acc in all_accounts}
        updates = []
        for line in text.splitlines():
            parsed = AccountManager.parse_batch_line(line)
            if parsed and parsed["email"] in email_to_id:
                updates.append((email_to_id[parsed["email"]], parsed))
        if not updates:
            messagebox.showwarning("提示", "没有匹配到任何已有账号，请检查邮箱是否一致")
            return
        if not messagebox.askyesno("确认", f"确定要为 {len(updates)} 个账号更新密码吗？\n此操作不可撤销"):
            return
        count = 0
        for acc_id, parsed in updates:
            fields = {"password": parsed["password"]}
            if parsed["recovery_email"]:
                fields["recovery_email"] = parsed["recovery_email"]
            if parsed["totp_secret"]:
                fields["totp_secret"] = parsed["totp_secret"]
            if self.account_manager.update_account(acc_id, **fields):
                count += 1
        self.on_data_changed()
        self.status_callback(f"已更新 {count} 个账号的密码")
        messagebox.showinfo("完成", f"已成功更新 {count} 个账号的密码")

    def _copy_pwchange_result(self):
        text = self.pwchange_textbox.get("1.0", "end").strip()
        if text:
            self._parent.clipboard_clear()
            self._parent.clipboard_append(text)
            self.status_callback("改密结果已复制到剪贴板")

    # ── Real password change (browser automation) ─────────

    def _on_real_pwchange(self):
        text = self.pwchange_textbox.get("1.0", "end").strip()
        if not text:
            messagebox.showwarning("提示", "文本框为空，请先生成或加载账号数据")
            return
        all_accounts = self.account_manager.get_all_accounts()
        email_to_acc = {acc["email"]: acc for acc in all_accounts}
        tasks = []
        for line in text.splitlines():
            parsed = AccountManager.parse_batch_line(line)
            if not parsed or parsed["email"] not in email_to_acc:
                continue
            existing = email_to_acc[parsed["email"]]
            tasks.append({
                "email": parsed["email"],
                "password": existing["password"],
                "new_password": parsed["password"],
                "totp_secret": existing.get("totp_secret", "") or parsed.get("totp_secret", ""),
            })
        if not tasks:
            messagebox.showwarning("提示", "没有匹配到任何已有账号")
            return
        missing_totp = [t["email"] for t in tasks if not t["totp_secret"]]
        if missing_totp:
            msg = f"以下 {len(missing_totp)} 个账号没有 TOTP 密钥，可能无法通过 2FA 验证:\n"
            msg += "\n".join(missing_totp[:5])
            if len(missing_totp) > 5:
                msg += f"\n...等共 {len(missing_totp)} 个"
            if not messagebox.askyesno("警告", msg + "\n\n是否继续？"):
                return
        same_pw = [t["email"] for t in tasks if t["password"] == t["new_password"]]
        if same_pw:
            messagebox.showwarning("提示", f"有 {len(same_pw)} 个账号新旧密码相同，请先修改密码")
            return
        if not messagebox.askyesno(
            "确认",
            f"即将通过浏览器自动登录并修改 {len(tasks)} 个 Google 账号的密码。\n"
            f"模式: {'后台静默' if self.headless_var.get() else '显示浏览器'}\n\n确定要继续吗？",
        ):
            return
        self._pwchange_running = True
        self._pwchange_stop_flag = False
        self.real_pwchange_btn.configure(state="disabled")
        self.stop_pwchange_btn.configure(state="normal")
        self.pwchange_progress_var.set(f"准备中... 共 {len(tasks)} 个账号")
        self.log_callback(f"━━━ 开始批量改密：共 {len(tasks)} 个账号 ━━━")
        threading.Thread(target=self._run_pwchange_thread, args=(tasks,), daemon=True).start()
        self._check_pwchange_queue()

    def _run_pwchange_thread(self, tasks: list[dict]):
        changer = GooglePasswordChanger(headless=self.headless_var.get())
        results = []
        total = len(tasks)
        for i, acc in enumerate(tasks):
            if self._pwchange_stop_flag:
                results.append({"email": acc["email"], "success": False, "message": "用户停止"})
                continue
            def step_cb(msg, idx=i):
                self._pwchange_queue.put(("progress", idx, total, acc["email"], msg))
            self._pwchange_queue.put(("progress", i, total, acc["email"], f"开始处理 ({i+1}/{total})"))
            result = changer.change_password(
                email=acc["email"], current_password=acc["password"],
                new_password=acc["new_password"],
                totp_secret=acc.get("totp_secret", ""), callback=step_cb,
            )
            results.append(result)
            if result["success"]:
                self._pwchange_queue.put(("update_local", acc["email"], acc["new_password"]))
            if i < total - 1 and not self._pwchange_stop_flag:
                time.sleep(random.uniform(1, 2))
        self._pwchange_queue.put(("done", results))

    def _check_pwchange_queue(self):
        try:
            while True:
                msg = self._pwchange_queue.get_nowait()
                kind = msg[0]
                if kind == "progress":
                    _, idx, total, email, status = msg
                    self.pwchange_progress_var.set(f"[{idx+1}/{total}] {email}: {status}")
                    self.status_callback(f"改密进度: {idx+1}/{total}")
                    self.log_callback(f"[改密 {idx+1}/{total}] {status}")
                elif kind == "update_local":
                    _, email, new_pw = msg
                    for acc in self.account_manager.get_all_accounts():
                        if acc["email"] == email:
                            self.account_manager.update_account(acc["id"], password=new_pw)
                            break
                elif kind == "done":
                    self._on_pwchange_finished(msg[1])
                    return
        except queue.Empty:
            pass
        if self._pwchange_running:
            self._parent.after(300, self._check_pwchange_queue)

    def _on_pwchange_finished(self, results: list[dict]):
        self._pwchange_running = False
        self.real_pwchange_btn.configure(state="normal")
        self.stop_pwchange_btn.configure(state="disabled")
        success = sum(1 for r in results if r["success"])
        failed = len(results) - success
        self.log_callback(f"━━━ 批量改密完成：成功 {success}, 失败 {failed} ━━━")
        saved = 0
        text = self.pwchange_textbox.get("1.0", "end").strip()
        if text:
            all_accounts = self.account_manager.get_all_accounts()
            email_to_id = {acc["email"]: acc["id"] for acc in all_accounts}
            success_emails = {r["email"] for r in results if r["success"]}
            for line in text.splitlines():
                parsed = AccountManager.parse_batch_line(line)
                if parsed and parsed["email"] in email_to_id and parsed["email"] in success_emails:
                    fields = {"password": parsed["password"]}
                    if parsed["recovery_email"]:
                        fields["recovery_email"] = parsed["recovery_email"]
                    if parsed["totp_secret"]:
                        fields["totp_secret"] = parsed["totp_secret"]
                    if self.account_manager.update_account(email_to_id[parsed["email"]], **fields):
                        saved += 1
        summary = "\n".join(
            f"{r['email']} → {'OK' if r['success'] else 'FAIL: ' + r['message']}"
            for r in results
        )
        self.pwchange_progress_var.set(f"完成! 成功 {success} 个, 失败 {failed} 个, 已保存 {saved} 个")
        self.on_data_changed()
        self.selector.refresh()
        self.status_callback(f"在线改密完成: 成功 {success}, 失败 {failed}, 已保存 {saved}")
        messagebox.showinfo("改密完成",
            f"成功: {success} 个\n失败: {failed} 个\n已自动保存: {saved} 个\n\n{summary}")

    def _on_stop_pwchange(self):
        if self._pwchange_running:
            self._pwchange_stop_flag = True
            self.pwchange_progress_var.set("正在停止...")
            self.stop_pwchange_btn.configure(state="disabled")
