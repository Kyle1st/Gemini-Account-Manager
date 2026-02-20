import threading
import queue
import time
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED

import customtkinter as ctk
from tkinter import messagebox

from account_manager import AccountManager
from google_pw_changer import GooglePasswordChanger
from ui_account_selector import AccountSelectionPanel


class ClosePaymentParallelTab:
    """批量并发关闭支付资料 Tab：接入 AccountSelectionPanel，支持并发关闭支付资料。"""

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

        # Keep browser open option
        opt_frame2 = ctk.CTkFrame(config_card, fg_color="transparent")
        opt_frame2.pack(fill="x", padx=18, pady=(0, 14))

        self.keep_open_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            opt_frame2,
            text="🕶️ 完成后保留浏览器",
            variable=self.keep_open_var,
            font=ctk.CTkFont(size=13), checkbox_width=22, checkbox_height=22, corner_radius=4
        ).pack(side="left")

        # 2. Action Card
        action_card = ctk.CTkFrame(right, fg_color=("gray95", "gray20"), corner_radius=10)
        action_card.pack(fill="x", pady=(0, 12))

        ctk.CTkLabel(action_card, text="🚀 操作控制", 
                     font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold")).pack(anchor="w", padx=18, pady=(12, 8))
        
        # Helper text inside card
        ctk.CTkLabel(
            action_card,
            text="ℹ️ 功能：自动登录账号并关闭支付资料 (Close Payments Profile)",
            font=ctk.CTkFont(size=12), text_color=("gray50", "gray70")
        ).pack(anchor="w", padx=18, pady=(0, 8))

        btn_frame = ctk.CTkFrame(action_card, fg_color="transparent")
        btn_frame.pack(fill="x", padx=18, pady=(0, 18))

        self.real_btn = ctk.CTkButton(
            btn_frame, text="▶ 执行并发关闭", width=160, height=42,
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            fg_color="#e74c3c", hover_color="#c0392b", corner_radius=8,
            command=self._on_start_parallel,
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
            btn_frame, text="📥 加载选中账号", width=130, height=42,
            font=ctk.CTkFont(family="Segoe UI", size=14),
            fg_color="gray60", hover_color="gray50", corner_radius=8,
            command=self._on_load_selected,
        ).pack(side="left")

        ctk.CTkButton(
            btn_frame, text="📋 复制结果", width=110, height=42,
            font=ctk.CTkFont(family="Segoe UI", size=14),
            fg_color="gray60", hover_color="gray50", corner_radius=8,
            command=self._copy_result,
        ).pack(side="left", padx=(12, 0))

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
        self.status_callback(f"已加载 {len(accounts)} 个账号")

    def _copy_result(self):
        text = self.textbox.get("1.0", "end").strip()
        if text:
            self._parent.clipboard_clear()
            self._parent.clipboard_append(text)
            self.status_callback("结果已复制到剪贴板")

    def _on_start_parallel(self):
        if self._running:
            return

        accounts = self.selector.get_selected_accounts()
        if not accounts:
            messagebox.showwarning("提示", "请先在左侧勾选需要操作的账号")
            return

        workers = int(float(self.workers_var.get()))
        workers = max(1, min(8, workers))
        self.workers_var.set(workers)

        if not messagebox.askyesno(
            "确认",
            f"即将为 {len(accounts)} 个 Google 账号并发关闭支付资料。\n"
            f"并发数: {workers}\n"
            f"模式: {'后台静默' if self.headless_var.get() else '显示浏览器'}\n\n"
            "确定要继续吗？",
        ):
            return

        self._running = True
        self._stop_flag = False
        self._completed_count = 0
        self._total_count = len(accounts)

        self.real_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.progress_var.set(f"准备中... 共 {len(accounts)} 个账号")
        self.textbox.delete("1.0", "end")
        
        self.log_callback(f"━━━ 开始多并发关闭支付资料：共 {len(accounts)} 个账号，并发数 {workers} ━━━")

        threading.Thread(
            target=self._run_thread,
            args=(accounts, workers, self.headless_var.get(), self.keep_open_var.get()),
            daemon=True,
        ).start()
        self._check_queue()

    def _run_thread(self, accounts: list[dict], max_workers: int, headless: bool, keep_browser_open: bool):
        total = len(accounts)
        results: list[dict | None] = [None] * total

        def run_one(idx: int, acc: dict) -> dict:
            if self._stop_flag:
                return {
                    "email": acc["email"],
                    "success": False,
                    "message": "用户停止",
                }

            def step_cb(msg: str, _idx=idx, _email=acc["email"]):
                self._queue.put(("progress", _idx, total, _email, msg))

            self._queue.put(
                ("progress", idx, total, acc["email"], f"开始处理 ({idx+1}/{total})")
            )

            changer = GooglePasswordChanger(headless=headless)
            return changer.login_and_close_payments(
                email=acc["email"],
                password=acc["password"],
                totp_secret=acc.get("totp_secret", ""),
                callback=step_cb,
                keep_browser_open=keep_browser_open,
            )

        futures: dict = {}
        next_idx = 0

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            while next_idx < total and len(futures) < max_workers and not self._stop_flag:
                futures[executor.submit(run_one, next_idx, accounts[next_idx])] = next_idx
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
                    acc = accounts[idx]
                    try:
                        result = fut.result()
                    except Exception as e:
                        result = {
                            "email": acc["email"],
                            "success": False,
                            "message": f"操作失败: {str(e)[:200]}",
                        }

                    results[idx] = result

                    self._queue.put(
                        (
                            "item_done",
                            idx,
                            total,
                            acc["email"],
                            result["success"],
                            result.get("message", ""),
                        )
                    )

                while (
                    next_idx < total
                    and len(futures) < max_workers
                    and not self._stop_flag
                ):
                    futures[executor.submit(run_one, next_idx, accounts[next_idx])] = next_idx
                    next_idx += 1

        for idx, acc in enumerate(accounts):
            if results[idx] is None:
                results[idx] = {
                    "email": acc["email"],
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
                    self.status_callback(f"关闭支付资料进度: {self._completed_count}/{self._total_count}")
                    self.log_callback(f"[关闭支付资料 {idx+1}/{total}] {status}")

                elif kind == "item_done":
                    _, idx, total, email, ok, detail = msg
                    self._completed_count += 1
                    short = "成功" if ok else "失败"
                    self.progress_var.set(
                        f"进度 {self._completed_count}/{self._total_count} | {email}: {short}"
                    )
                    self.log_callback(f"[关闭支付资料 {idx+1}/{total}] {email}: {short} {detail}")

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
        self.log_callback(f"━━━ 多并发关闭支付资料完成：成功 {success}, 失败 {failed} ━━━")

        self.textbox.delete("1.0", "end")
        summary = "\n".join(
             f"{r['email']} - {'✅ ' + r.get('message', '成功') if r['success'] else '❌ ' + r.get('message', '失败')}"
             for r in results
        )
        
        self.textbox.insert("1.0", summary)
        
        self.progress_var.set(f"完成! 成功 {success}, 失败 {failed}")
        self.on_data_changed()
        self.selector.refresh()
        messagebox.showinfo("多并发关闭支付资料完成", f"成功: {success}\n失败: {failed}\n\n{summary[:500]}...")

    def _on_stop(self):
        if self._running:
            self._stop_flag = True
            self.progress_var.set("正在停止，等待已开始任务结束...")
            self.stop_btn.configure(state="disabled")
