import customtkinter as ctk
import threading
from tkinter import messagebox

from account_manager import AccountManager
from google_pw_changer import GooglePasswordChanger
from ui_account_list import AccountListPanel
from ui_account_detail import AccountDetailPanel


class ManageTab:
    """账号管理 Tab：左侧列表 + 右侧详情，支持拖拽分隔条调整宽度。"""

    def __init__(self, parent, account_manager: AccountManager,
                 log_callback, status_callback, on_account_saved):
        self.account_manager = account_manager
        self.log_callback = log_callback
        self.status_callback = status_callback
        self.on_account_saved_external = on_account_saved
        self._parent = parent

        parent.grid_columnconfigure(0, weight=0, minsize=280)
        parent.grid_columnconfigure(1, weight=0, minsize=6)   # sash
        parent.grid_columnconfigure(2, weight=1, minsize=300)
        parent.grid_rowconfigure(0, weight=1)

        # Left: Account list
        self.list_panel = AccountListPanel(
            parent, account_manager,
            on_select_callback=self._on_account_selected,
            on_new_callback=self._on_new_account,
        )
        self.list_panel.grid(row=0, column=0, sticky="nsew")

        # Draggable sash (thin vertical bar)
        self._sash = ctk.CTkFrame(parent, width=6, fg_color="transparent",
                                   corner_radius=0, cursor="sb_h_double_arrow")
        self._sash.grid(row=0, column=1, sticky="ns")
        self._sash.bind("<Button-1>", self._sash_start)
        self._sash.bind("<B1-Motion>", self._sash_drag)
        self._sash.bind("<Enter>", lambda e: self._sash.configure(fg_color=("gray80", "gray40")))
        self._sash.bind("<Leave>", lambda e: self._sash.configure(fg_color="transparent"))

        # Right: wrapper frame for login card + detail panel
        right_wrapper = ctk.CTkFrame(parent, fg_color="transparent", corner_radius=0)
        right_wrapper.grid(row=0, column=2, sticky="nsew")
        right_wrapper.grid_rowconfigure(1, weight=1)
        right_wrapper.grid_columnconfigure(0, weight=1)

        # ── Manual browser login card (top of right side) ──
        login_frame = ctk.CTkFrame(right_wrapper, fg_color=("gray95", "gray20"), corner_radius=10)
        login_frame.grid(row=0, column=0, sticky="ew", padx=15, pady=(10, 5))

        login_inner = ctk.CTkFrame(login_frame, fg_color="transparent")
        login_inner.pack(fill="x", padx=15, pady=10)

        ctk.CTkLabel(
            login_inner, text="🌐 手动浏览器登录获取 Cookie    适用于无 2FA 密钥的账号",
            font=ctk.CTkFont(family="Segoe UI", size=12),
        ).pack(side="left")

        self._login_btn = ctk.CTkButton(
            login_inner, text="🌐 浏览器登录", width=120, height=32,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#3498db", hover_color="#2980b9", corner_radius=8,
            command=self._on_manual_login,
        )
        self._login_btn.pack(side="right")

        self._stop_login_btn = ctk.CTkButton(
            login_inner, text="⏹ 停止", width=60, height=32,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#e74c3c", hover_color="#c0392b", corner_radius=8,
            command=self._on_stop_manual_login,
        )
        # We pack it later only when login is active, or pack it now but disabled
        
        self._active_changer = None

        # ── Account detail panel (below login card) ──
        self.detail_panel = AccountDetailPanel(
            right_wrapper, account_manager,
            status_callback=status_callback,
        )
        self.detail_panel.grid(row=1, column=0, sticky="nsew")
        self.detail_panel.bind("<<AccountSaved>>", self._on_account_saved)

        # Set initial left panel width after the window is mapped
        self._left_width = 400
        parent.after(100, lambda: parent.grid_columnconfigure(0, minsize=self._left_width))

    # ── Sash drag ───────────────────────────────────────────────

    def _sash_start(self, event):
        self._drag_start_x = event.x_root
        self._drag_start_width = self.list_panel.winfo_width()

    def _sash_drag(self, event):
        dx = event.x_root - self._drag_start_x
        new_width = max(280, min(self._drag_start_width + dx,
                                  self._parent.winfo_width() - 350))
        self._left_width = new_width
        self._parent.grid_columnconfigure(0, minsize=new_width)

    # ── Callbacks ───────────────────────────────────────────────

    def _on_account_selected(self, account_id: str | None):
        if account_id:
            self.detail_panel.load_account(account_id)
        else:
            self.detail_panel.clear_form()

    def _on_new_account(self):
        self.detail_panel.clear_form()

    def _on_account_saved(self, event=None):
        account_id = self.detail_panel.current_account_id
        self.list_panel.refresh_list(self.list_panel.search_var.get())
        if account_id:
            self.list_panel.select_account_by_id(account_id)
        self.on_account_saved_external()

    # ── Manual browser login ────────────────────────────────────

    def _on_stop_manual_login(self):
        if self._active_changer:
            self._active_changer.cancel_manual_login()
            self._stop_login_btn.configure(state="disabled", text="Stopping...")

    def _on_manual_login(self):
        """Open browser for manual login, extract cookies for the form account."""
        email = self.detail_panel.email_var.get().strip()
        if not email:
            email = ""  # Allowing empty email to let user type it in browser
        
        password = self.detail_panel.password_var.get().strip()

        # If it's a new account, we might warn them, but let's just proceed
        self._login_btn.configure(state="disabled", text="⏳ 等待登录...")
        self._stop_login_btn.configure(state="normal", text="⏹ 停止")
        self._stop_login_btn.pack(side="right", padx=(0, 10))
        
        if email:
            self.status_callback(f"正在打开浏览器，请手动登录 {email}...")
        else:
            self.status_callback("正在打开浏览器，请手动完成登录...")

        def run():
            self._active_changer = GooglePasswordChanger(headless=False)
            result = self._active_changer.manual_login_for_cookie(
                email=email,
                password=password,
                callback=lambda msg: self._parent.after(
                    0, lambda m=msg: (
                        self.status_callback(m),
                        self.log_callback(m),
                    )
                ),
            )

            def on_done():
                self._active_changer = None
                self._stop_login_btn.pack_forget()
                self._login_btn.configure(state="normal", text="🌐 浏览器登录")
                
                # Use the email returned by the login process, as it might have extracted it
                final_email = result.get("email", email)
                
                if result["success"] and result.get("cookies"):
                    if final_email:
                        # Check if it exists in DB, if not, create a skeleton or just save cookies
                        acc = self.account_manager.get_account(final_email)
                        if acc:
                            self.account_manager.save_cookies(final_email, result["cookies"])
                            self.list_panel.refresh_list(self.list_panel.search_var.get())
                            self.on_account_saved_external()
                            self.status_callback(f"✅ {final_email} Cookie 已保存")
                            messagebox.showinfo("成功", f"{final_email}\n\nCookie 已成功提取并保存！")
                        else:
                            # Account not in list yet
                            # Update the form with the cookies but we can't save directly without hitting save
                            # Let's save a skeleton account and then refresh
                            self.account_manager.add_account(
                                email=final_email,
                                password=password,
                                tags=["已存 Cookie"],
                            )
                            self.account_manager.save_cookies(final_email, result["cookies"])
                            self.list_panel.refresh_list(self.list_panel.search_var.get())
                            self.list_panel.select_account_by_id(final_email)
                            self.on_account_saved_external()
                            messagebox.showinfo("成功", f"新账号 {final_email} 已入库并保存 Cookie！")
                    else:
                        messagebox.showwarning("提示", "获取到了 Cookie，但未能自动提取到邮箱，请手动填入邮箱后再试。")
                else:
                    self.status_callback(f"❌ 登录失败或未提取到: {result.get('message', '')}")
                    if "浏览器已被关闭" not in result.get('message', ''):
                        messagebox.showwarning("失败", f"{result.get('message', '登录失败')}")

            self._parent.after(0, on_done)

        threading.Thread(target=run, daemon=True).start()

    # ── Public API ──────────────────────────────────────────────

    def refresh(self):
        self.list_panel.refresh_list(self.list_panel.search_var.get())

    @property
    def totp_display(self):
        return self.detail_panel.totp_display
