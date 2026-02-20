import threading
import queue
import time
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED

import customtkinter as ctk
from tkinter import messagebox

from account_manager import AccountManager
from google_pw_changer import GooglePasswordChanger
from password_generator import generate_password
from ui_account_selector import AccountSelectionPanel


class PwChangeParallelTab:
    """批量并发改密 Tab：接入 AccountSelectionPanel，支持并发修改密码。"""

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
        self.selector = AccountSelectionPanel(parent, account_manager, width=280)
        self.selector.grid(row=0, column=0, sticky="nsw", padx=(10, 5), pady=10)

        # ── Right: Controls ──
        right = ctk.CTkFrame(parent, fg_color="transparent")
        right.grid(row=0, column=1, sticky="nsew", padx=(5, 10), pady=10)
        right.grid_columnconfigure(0, weight=1)
        right.grid_rowconfigure(3, weight=1)

        # 1. Configuration Card
        config_card = ctk.CTkFrame(right, fg_color=("gray95", "gray20"), corner_radius=10)
        config_card.pack(fill="x", pady=(0, 12))

        ctk.CTkLabel(config_card, text="⚙️ 参数配置", 
                     font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold")).pack(anchor="w", padx=18, pady=(12, 8))

        opt_frame = ctk.CTkFrame(config_card, fg_color="transparent")
        opt_frame.pack(fill="x", padx=18, pady=(0, 18))

        ctk.CTkLabel(opt_frame, text="并发线程数:", font=ctk.CTkFont(size=13)).pack(side="left")
        self.workers_var = ctk.IntVar(value=3)
        self.workers_label = ctk.CTkLabel(opt_frame, text="3", width=24, font=ctk.CTkFont(size=14, weight="bold"))
        self.workers_label.pack(side="left", padx=(5, 0))
        
        ctk.CTkSlider(
            opt_frame, from_=1, to=8, number_of_steps=7,
            variable=self.workers_var, width=180, height=20
        ).pack(side="left", padx=(8, 20))
        
        self.workers_var.trace_add(
            "write", lambda *_: self.workers_label.configure(text=str(int(float(self.workers_var.get()))))
        )

        self.headless_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            opt_frame, text="后台静默模式 (不显示浏览器)", variable=self.headless_var,
            font=ctk.CTkFont(size=13), checkbox_width=22, checkbox_height=22, corner_radius=4
        ).pack(side="left")

        # 1.5 Local Password Editor Card
        local_card = ctk.CTkFrame(right, fg_color=("gray95", "gray20"), corner_radius=10)
        local_card.pack(fill="x", pady=(0, 12))

        ctk.CTkLabel(local_card, text="📝 本地密码编辑", 
                     font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold")).pack(anchor="w", padx=18, pady=(12, 8))

        local_opt1 = ctk.CTkFrame(local_card, fg_color="transparent")
        local_opt1.pack(fill="x", padx=18, pady=(0, 8))

        ctk.CTkLabel(local_opt1, text="密码长度:", font=ctk.CTkFont(size=13)).pack(side="left")
        self.pw_len_var = ctk.IntVar(value=16)
        ctk.CTkSlider(local_opt1, from_=8, to=32, number_of_steps=24,
                      variable=self.pw_len_var, width=150, height=16).pack(side="left", padx=(8, 5))
        self.pw_len_label = ctk.CTkLabel(local_opt1, text="16", width=24, font=ctk.CTkFont(size=13))
        self.pw_len_label.pack(side="left")
        self.pw_len_var.trace_add("write", lambda *_: self.pw_len_label.configure(text=str(self.pw_len_var.get())))

        ctk.CTkButton(local_opt1, text="🎲 生成随机密码", width=120, height=32, font=ctk.CTkFont(size=13),
                      fg_color="#e67e22", hover_color="#d35400", corner_radius=6,
                      command=self._on_batch_pwchange).pack(side="left", padx=(15, 0))

        local_opt2 = ctk.CTkFrame(local_card, fg_color="transparent")
        local_opt2.pack(fill="x", padx=18, pady=(0, 16))

        ctk.CTkLabel(local_opt2, text="自定义密码:", font=ctk.CTkFont(size=13)).pack(side="left")
        self.custom_pw_var = ctk.StringVar()
        ctk.CTkEntry(local_opt2, textvariable=self.custom_pw_var,
                     font=ctk.CTkFont(family="Consolas", size=13), height=32, width=170,
                     placeholder_text="统一的新密码").pack(side="left", padx=(5, 0))
        ctk.CTkButton(local_opt2, text="✍️ 应用自定义", width=120, height=32, font=ctk.CTkFont(size=13),
                      fg_color="#3498db", hover_color="#2980b9", corner_radius=6,
                      command=self._on_apply_custom_pw).pack(side="left", padx=(10, 0))

        # 2. Action Card
        action_card = ctk.CTkFrame(right, fg_color=("gray95", "gray20"), corner_radius=10)
        action_card.pack(fill="x", pady=(0, 12))

        ctk.CTkLabel(action_card, text="🚀 操作控制", 
                     font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold")).pack(anchor="w", padx=18, pady=(12, 8))
        
        # Helper text inside card
        ctk.CTkLabel(
            action_card,
            text="ℹ️ 提示：请先在主“批量改密”Tab中生成新密码，并加载到此处",
            font=ctk.CTkFont(size=12), text_color=("gray50", "gray70")
        ).pack(anchor="w", padx=18, pady=(0, 8))

        btn_frame = ctk.CTkFrame(action_card, fg_color="transparent")
        btn_frame.pack(fill="x", padx=18, pady=(0, 18))

        self.real_btn = ctk.CTkButton(
            btn_frame, text="▶ 执行并发改密", width=160, height=42,
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            fg_color="#e74c3c", hover_color="#c0392b", corner_radius=8,
            command=self._on_real_pwchange_parallel,
        )
        self.real_btn.pack(side="left")

        self.stop_btn = ctk.CTkButton(
            btn_frame, text="⏹ 停止", width=90, height=42,
            font=ctk.CTkFont(family="Segoe UI", size=14),
            fg_color="gray50", hover_color="gray40", corner_radius=8,
            state="disabled", command=self._on_stop,
        )
        self.stop_btn.pack(side="left", padx=12)
        
        ctk.CTkButton(
            btn_frame, text="📥 加载选中账号", width=120, height=42,
            font=ctk.CTkFont(family="Segoe UI", size=14),
            fg_color="gray60", hover_color="gray50", corner_radius=8,
            command=self._on_load_selected
        ).pack(side="left")

        ctk.CTkButton(
            btn_frame, text="💾 保存文本框密码", width=140, height=42,
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            fg_color="#f39c12", hover_color="#d68910", corner_radius=8,
            command=self._on_apply_pwchange
        ).pack(side="left", padx=12)

        # 3. Progress & Log
        log_frame = ctk.CTkFrame(right, fg_color="transparent")
        log_frame.pack(fill="both", expand=True)
        
        self.progress_var = ctk.StringVar(value="准备就绪")
        ctk.CTkLabel(log_frame, textvariable=self.progress_var, anchor="w",
                     font=ctk.CTkFont(size=13), text_color="gray70").pack(fill="x", pady=(0, 6))

        # Textbox
        self.textbox = ctk.CTkTextbox(
            log_frame, font=ctk.CTkFont(family="Consolas", size=13), corner_radius=8
        )
        self.textbox.pack(fill="both", expand=True)
        self.textbox.insert("1.0", "# 请在此处输入需要改密的账号信息 (格式: 邮箱----当前密码----辅助邮箱----TOTP)\n# 注意：你需要自己指定新密码，目前此工具仅展示如何读取文本框\n# 为了简单，本Tab复用 '邮箱----新密码----...' 格式，\n# 请确保文本框内的密码是你想要的【新密码】。\n# 实际执行时，程序会用账号列表里的【旧密码】登录，修改为文本框里的【新密码】。\n")

        self._queue: queue.Queue = queue.Queue()
        self._running = False
        self._stop_flag = False
        self._completed_count = 0
        self._total_count = 0

    def _on_load_selected(self):
        accounts = self.selector.get_selected_accounts()
        if not accounts:
            messagebox.showwarning("提示", "请先在左侧勾选账号")
            return
        
        self.textbox.delete("1.0", "end")
        lines = [AccountManager.format_line(acc) for acc in accounts]
        self.textbox.insert("1.0", "\n".join(lines))
        self.status_callback(f"已加载 {len(accounts)} 个账号，可直接编辑文本框中的密码")

    def _on_apply_custom_pw(self):
        custom_pw = self.custom_pw_var.get()
        if not custom_pw:
            messagebox.showwarning("提示", "请先输入自定义密码")
            return
        accounts = self.selector.get_selected_accounts()
        if not accounts:
            messagebox.showwarning("提示", "请先在左侧勾选需要修改的账号")
            return
        self.textbox.delete("1.0", "end")
        lines = [AccountManager.format_line({
            "email": acc["email"], "password": custom_pw,
            "recovery_email": acc.get("recovery_email", ""),
            "totp_secret": acc.get("totp_secret", ""),
        }) for acc in accounts]
        self.textbox.insert("1.0", "\n".join(lines))
        self.status_callback(f"已为 {len(accounts)} 个账号设置自定义密码（未保存）")

    def _on_batch_pwchange(self):
        accounts = self.selector.get_selected_accounts()
        if not accounts:
            messagebox.showwarning("提示", "请先在左侧勾选需要修改的账号")
            return
        length = self.pw_len_var.get()
        self.textbox.delete("1.0", "end")
        lines = []
        for acc in accounts:
            new_pw = generate_password(length=length)
            lines.append(AccountManager.format_line({
                "email": acc["email"], "password": new_pw,
                "recovery_email": acc.get("recovery_email", ""),
                "totp_secret": acc.get("totp_secret", ""),
            }))
        self.textbox.insert("1.0", "\n".join(lines))
        self.status_callback(f"已为 {len(accounts)} 个账号生成新密码（未保存）")

    def _on_apply_pwchange(self):
        text = self.textbox.get("1.0", "end").strip()
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
        if not messagebox.askyesno("确认", f"确定要为 {len(updates)} 个账号在本地保存新密码吗？\n注意：这仅保存在本地表格中，还需执行并发改密才会真正修改 Google 密码！"):
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
        self.status_callback(f"已在本地更新 {count} 个账号的密码")
        messagebox.showinfo("完成", f"已在本地更新 {count} 个账号的密码，可现在点击执行并发改密。")

    def _on_real_pwchange_parallel(self):
        if self._running:
            return

        text = self.textbox.get("1.0", "end").strip()
        if not text:
             messagebox.showwarning("提示", "文本框为空")
             return

        # Parse text box to get target (email -> new_password)
        # We assume the text box contains lines with the NEW password.
        target_updates = {}
        for line in text.splitlines():
            if line.strip().startswith("#"): continue
            parsed = AccountManager.parse_batch_line(line)
            if parsed:
                target_updates[parsed["email"]] = parsed

        if not target_updates:
            messagebox.showwarning("提示", "未找到有效的账号行")
            return

        # Match with existing accounts (to get OLD password and TOTP)
        all_accounts = self.account_manager.get_all_accounts()
        email_to_acc = {acc["email"]: acc for acc in all_accounts}

        tasks = []
        for email, new_data in target_updates.items():
            if email not in email_to_acc:
                continue
            existing = email_to_acc[email]
            
            # Check if new password is different
            if existing["password"] == new_data["password"]:
                # If they are same, maybe user didn't update text box? 
                # We warn but allow if user insists? 
                pass 
            
            tasks.append({
                "email": email,
                "password": existing["password"], # Old password for login
                "new_password": new_data["password"], # New password to set
                "totp_secret": existing.get("totp_secret", "") or new_data.get("totp_secret", "")
            })

        if not tasks:
            messagebox.showwarning("提示", "没有匹配到任何已有账号（需确保邮箱在数据库中存在）")
            return
            
        # Check for same passwords
        same_pw = [t["email"] for t in tasks if t["password"] == t["new_password"]]
        if same_pw:
            if not messagebox.askyesno("确认", f"有 {len(same_pw)} 个账号新旧密码相同（文本框内的密码与数据库一致）。\n这可能导致改密失败（Google 不允许设置相同密码）。\n是否仍要继续？"):
                return

        workers = int(float(self.workers_var.get()))
        workers = max(1, min(8, workers))
        self.workers_var.set(workers)

        if not messagebox.askyesno(
            "确认",
            f"即将并发修改 {len(tasks)} 个 Google 账号的密码。\n"
            f"并发数: {workers}\n"
            f"模式: {'后台静默' if self.headless_var.get() else '显示浏览器'}\n\n"
            "确定要继续吗？",
        ):
            return

        self._running = True
        self._stop_flag = False
        self._completed_count = 0
        self._total_count = len(tasks)

        self.real_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.progress_var.set(f"准备中... 共 {len(tasks)} 个账号")
        
        self.log_callback(f"━━━ 开始多并发改密：共 {len(tasks)} 个账号，并发数 {workers} ━━━")

        threading.Thread(
            target=self._run_thread,
            args=(tasks, workers, self.headless_var.get()),
            daemon=True,
        ).start()
        self._check_queue()

    def _run_thread(self, tasks: list[dict], max_workers: int, headless: bool):
        total = len(tasks)
        results: list[dict | None] = [None] * total

        def run_one(idx: int, task: dict) -> dict:
            if self._stop_flag:
                return {
                    "email": task["email"],
                    "success": False,
                    "message": "用户停止",
                }

            def step_cb(msg: str, _idx=idx, _email=task["email"]):
                self._queue.put(("progress", _idx, total, _email, msg))

            self._queue.put(
                ("progress", idx, total, task["email"], f"开始处理 ({idx+1}/{total})")
            )

            changer = GooglePasswordChanger(headless=headless)
            return changer.change_password(
                email=task["email"],
                current_password=task["password"],
                new_password=task["new_password"],
                totp_secret=task.get("totp_secret", ""),
                callback=step_cb,
            )

        futures: dict = {}
        next_idx = 0

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            while next_idx < total and len(futures) < max_workers and not self._stop_flag:
                futures[executor.submit(run_one, next_idx, tasks[next_idx])] = next_idx
                next_idx += 1

            while futures:
                done, _ = wait(
                    list(futures.keys()),
                    timeout=0.3,
                    return_when=FIRST_COMPLETED,
                )
                if not done:
                    continue

                for fut in done:
                    idx = futures.pop(fut)
                    task = tasks[idx]
                    try:
                        result = fut.result()
                    except Exception as e:
                        result = {
                            "email": task["email"],
                            "success": False,
                            "message": f"操作失败: {str(e)[:200]}",
                        }

                    results[idx] = result

                    if result["success"]:
                        self._queue.put(
                            ("update_local", task["email"], task["new_password"])
                        )

                    self._queue.put(
                        (
                            "item_done",
                            idx,
                            total,
                            task["email"],
                            result["success"],
                            result.get("message", ""),
                        )
                    )

                while (
                    next_idx < total
                    and len(futures) < max_workers
                    and not self._stop_flag
                ):
                    futures[executor.submit(run_one, next_idx, tasks[next_idx])] = next_idx
                    next_idx += 1

        for idx, task in enumerate(tasks):
            if results[idx] is None:
                results[idx] = {
                    "email": task["email"],
                    "success": False,
                    "message": "用户停止",
                }

        self._queue.put(("done", results))

    def _check_queue(self):
        try:
            while True:
                msg = self._queue.get_nowait()
                kind = msg[0]

                if kind == "progress":
                    _, idx, total, email, status = msg
                    self.progress_var.set(f"[{idx+1}/{total}] {email}: {status}")
                    self.status_callback(f"并发改密进度: {self._completed_count}/{self._total_count}")
                    self.log_callback(f"[并发改密 {idx+1}/{total}] {status}")

                elif kind == "item_done":
                    _, idx, total, email, ok, detail = msg
                    self._completed_count += 1
                    short = "成功" if ok else "失败"
                    self.progress_var.set(
                        f"进度 {self._completed_count}/{self._total_count} | {email}: {short}"
                    )
                    self.log_callback(f"[并发改密 {idx+1}/{total}] {email}: {short} {detail}")

                elif kind == "update_local":
                    _, email, new_password = msg
                    for acc in self.account_manager.get_all_accounts():
                        if acc["email"] == email:
                            self.account_manager.update_account(acc["id"], password=new_password)
                            break

                elif kind == "done":
                    self._on_finished(msg[1])
                    return

        except queue.Empty:
            pass

        if self._running:
            self._parent.after(300, self._check_queue)

    def _on_finished(self, results: list[dict]):
        self._running = False
        self.real_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")

        success = sum(1 for r in results if r["success"])
        failed = len(results) - success
        self.log_callback(f"━━━ 多并发改密完成：成功 {success}, 失败 {failed} ━━━")
        
        summary = "\n".join(
             f"{r['email']} - {'OK' if r['success'] else 'FAIL: ' + r.get('message', '')}"
             for r in results
        )
        
        self.progress_var.set(f"完成! 成功 {success}, 失败 {failed}")
        self.on_data_changed()
        self.selector.refresh()
        messagebox.showinfo("多并发改密完成", f"成功: {success}\n失败: {failed}\n\n{summary}")

    def _on_stop(self):
        if self._running:
            self._stop_flag = True
            self.progress_var.set("正在停止，等待已开始任务结束...")
            self.stop_btn.configure(state="disabled")

