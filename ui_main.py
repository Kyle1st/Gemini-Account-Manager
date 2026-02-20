import customtkinter as ctk
from tkinter import filedialog, messagebox
import shutil
import os
from datetime import datetime

from account_manager import AccountManager
from excel_export import export_to_excel, import_from_excel
from tab_manage import ManageTab
from tab_totp_parallel import TotpParallelTab
from tab_pwchange_parallel import PwChangeParallelTab
from tab_family_parallel import FamilyParallelTab
from tab_close_payment_parallel import ClosePaymentParallelTab
from tab_check_ai_student_parallel import CheckAIStudentParallelTab
from tab_batch_import import BatchImportTab
from tab_log import LogTab


class MainApplication(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Gemini Account Manager")
        self.geometry("1100x720")
        self.minsize(960, 600)

        # Set window icon
        self._set_icon()

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.account_manager = AccountManager()

        # 先创建 tabs，再构建 toolbar（toolbar 引用 tab 方法）
        self._build_tabs()
        self._build_toolbar()
        self._build_status_bar()
        self._start_totp_timer()
        self._update_status_count()

    def _set_icon(self):
        """Set the application window icon (title bar + taskbar)."""
        import tkinter as tk
        base_dir = os.path.dirname(os.path.abspath(__file__))
        ico_path = os.path.join(base_dir, "app.ico")
        png_path = os.path.join(base_dir, "icon.png")
        try:
            if os.path.exists(ico_path):
                self.iconbitmap(ico_path)
            if os.path.exists(png_path):
                icon_image = tk.PhotoImage(file=png_path)
                self.iconphoto(True, icon_image)
                self._icon_ref = icon_image  # prevent garbage collection
        except Exception:
            pass  # graceful fallback — no icon is fine

    def _build_toolbar(self):
        toolbar = ctk.CTkFrame(self, height=68, corner_radius=0, fg_color=("gray98", "#1e1e1e"))
        toolbar.pack(fill="x", side="top", before=self.tabview, padx=0, pady=0)
        toolbar.pack_propagate(False)

        # Logo / Title
        title_frame = ctk.CTkFrame(toolbar, fg_color="transparent")
        title_frame.pack(side="left", padx=25)
        ctk.CTkLabel(title_frame, text="Gemini Account Manager",
                     font=ctk.CTkFont(family="Segoe UI", size=22, weight="bold"),
                     text_color=("gray15", "gray95")).pack(anchor="w")
        ctk.CTkLabel(title_frame, text="v1.0.1",
                     font=ctk.CTkFont(size=11, weight="bold"),
                     text_color=("#3498db", "#5dade2")).pack(anchor="w")

        # Data Actions Group
        grp_data = ctk.CTkFrame(toolbar, fg_color="transparent")
        grp_data.pack(side="left", padx=20)
        
        btn_style = {"font": ctk.CTkFont(family="Segoe UI", size=13, weight="bold"), "corner_radius": 8, "height": 36}
        
        ctk.CTkButton(grp_data, text="📥 备份数据", width=100, **btn_style,
                      fg_color="#8e44ad", hover_color="#9b59b6",
                      command=self._on_backup_data).pack(side="left", padx=6)
        ctk.CTkButton(grp_data, text="📤 恢复数据", width=100, **btn_style,
                      fg_color="#8e44ad", hover_color="#9b59b6",
                      command=self._on_restore_data).pack(side="left", padx=6)

        # Excel Actions Group
        grp_excel = ctk.CTkFrame(toolbar, fg_color="transparent")
        grp_excel.pack(side="left", padx=20)
        
        ctk.CTkButton(grp_excel, text="📊 导出 Excel", width=110, **btn_style,
                      fg_color=("gray75", "gray25"), hover_color=("gray65", "gray35"),
                      text_color=("black", "white"),
                      command=self._on_export_excel).pack(side="left", padx=6)
        ctk.CTkButton(grp_excel, text="📈 导入 Excel", width=110, **btn_style,
                      fg_color=("gray75", "gray25"), hover_color=("gray65", "gray35"),
                      text_color=("black", "white"),
                      command=self._on_import_excel).pack(side="left", padx=6)

        # Theme Toggle
        self.appearance_var = ctk.StringVar(value="深色")
        ctk.CTkOptionMenu(toolbar, values=["深色", "浅色", "跟随系统"],
                          variable=self.appearance_var, width=110, **btn_style,
                          dropdown_font=ctk.CTkFont(size=13),
                          command=self._on_appearance_change
                          ).pack(side="right", padx=15)

        # Tab Order Actions
        grp_tab = ctk.CTkFrame(toolbar, fg_color="transparent")
        grp_tab.pack(side="right", padx=5)

        ctk.CTkButton(grp_tab, text="⬅", width=40, **btn_style,
                      fg_color=("gray75", "gray25"), hover_color=("gray65", "gray35"),
                      text_color=("black", "white"),
                      command=self._move_tab_left).pack(side="left", padx=2)
        ctk.CTkButton(grp_tab, text="➡", width=40, **btn_style,
                      fg_color=("gray75", "gray25"), hover_color=("gray65", "gray35"),
                      text_color=("black", "white"),
                      command=self._move_tab_right).pack(side="left", padx=2)
        
        # Label to indicate function
        # ctk.CTkLabel(grp_tab, text="Tab", font=ctk.CTkFont(size=10)).pack(side="bottom")

    def _move_tab_left(self):
        try:
            current_tab = self.tabview.get()
            # Access internal values list of segmented button
            values = self.tabview._segmented_button.cget("values")
            if not values or current_tab not in values:
                return
            idx = values.index(current_tab)
            if idx > 0:
                values.insert(idx - 1, values.pop(idx))
                self.tabview._segmented_button.configure(values=values)
                self.tabview.set(current_tab)
        except Exception:
            pass

    def _move_tab_right(self):
        try:
            current_tab = self.tabview.get()
            values = self.tabview._segmented_button.cget("values")
            if not values or current_tab not in values:
                return
            idx = values.index(current_tab)
            if idx < len(values) - 1:
                values.insert(idx + 1, values.pop(idx))
                self.tabview._segmented_button.configure(values=values)
                self.tabview.set(current_tab)
        except Exception:
            pass

    def _build_tabs(self):
        self.tabview = ctk.CTkTabview(self, corner_radius=12, 
                                      fg_color=("gray92", "#242424"),
                                      segmented_button_selected_color="#2980b9",
                                      segmented_button_selected_hover_color="#1a5276",
                                      segmented_button_unselected_color=("gray85", "gray30"),
                                      text_color=("gray30", "gray90"))
        
        # Increase tab button font
        self.tabview._segmented_button.configure(font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"))
        
        self.tabview.pack(fill="both", expand=True, padx=15, pady=(15, 15))

        self.manage_tab = ManageTab(
            self.tabview.add("👥 账号管理"), self.account_manager,
            self._update_status, self._update_status_count
        )

        self.import_tab = BatchImportTab(
            self.tabview.add("📥 批量导入"), self.account_manager,
            self._update_status, self._update_status_count
        )

        # Use a bound lambda so all tabs share the same log_append reference
        # even though log_tab is created last (after all other tabs visually)
        def _log_append(msg: str):
            if hasattr(self, 'log_tab'):
                self.log_tab.append(msg)

        common_args = (self.account_manager, _log_append,
                       self._update_status, self._update_status_count)

        self.pwchange_parallel_tab = PwChangeParallelTab(self.tabview.add("🔑 批量改密"), *common_args)
        self.totp_parallel_tab = TotpParallelTab(self.tabview.add("🔒 批量改2FA"), *common_args)
        
        self.family_parallel_tab = FamilyParallelTab(self.tabview.add("👨‍👩‍👧‍👦 批量家庭组"), *common_args)
        self.close_payment_tab = ClosePaymentParallelTab(self.tabview.add("💸 关闭支付"), *common_args)
        self.check_ai_student_tab = CheckAIStudentParallelTab(self.tabview.add("✨ 查询学生资格"), *common_args)

        # Log tab goes last — visually the rightmost tab
        self.log_tab = LogTab(self.tabview.add("📝 运行日志"))

        self.tabview.set("👥 账号管理")


    def _build_status_bar(self):
        bar = ctk.CTkFrame(self, height=36, corner_radius=0, fg_color=("gray90", "#1a1a1a"))
        bar.pack(fill="x", side="bottom")
        bar.pack_propagate(False)

        self.status_left = ctk.StringVar(value="就绪")
        self.status_right = ctk.StringVar(value="")
        
        # Add a small icon or distinct font
        ctk.CTkLabel(bar, text="ℹ️", font=ctk.CTkFont(size=16)).pack(side="left", padx=(15, 5))
        ctk.CTkLabel(bar, textvariable=self.status_left, anchor="w",
                     font=ctk.CTkFont(family="Segoe UI", size=13)).pack(side="left", padx=5)
        
        ctk.CTkLabel(bar, textvariable=self.status_right, anchor="e",
                     font=ctk.CTkFont(family="Consolas", size=12, weight="bold"),
                     text_color=("gray40", "gray60")).pack(side="right", padx=20)

    # ── 状态更新 ──────────────────────────────────────────

    def _update_status(self, message: str):
        self.status_left.set(message)

    def _update_status_count(self):
        accounts = self.account_manager.get_all_accounts()
        total = len(accounts)
        with_totp = sum(1 for acc in accounts if acc.get("totp_secret"))
        no_totp = total - with_totp
        self.status_right.set(f"总计: {total} | 有TOTP: {with_totp} | 无TOTP: {no_totp}")

        # 刷新各子系统的账号列表
        if hasattr(self, 'manage_tab'):
            self.manage_tab.refresh()
        if hasattr(self, 'pwchange_parallel_tab'):
            self.pwchange_parallel_tab.selector.refresh()
        if hasattr(self, 'totp_parallel_tab'):
            self.totp_parallel_tab.selector.refresh()
        if hasattr(self, 'family_parallel_tab'):
            self.family_parallel_tab.selector.refresh()
        if hasattr(self, 'close_payment_tab'):
            self.close_payment_tab.selector.refresh()
        if hasattr(self, 'check_ai_student_tab'):
            self.check_ai_student_tab.selector.refresh()

    # ── TOTP 计时器 ───────────────────────────────────────

    def _start_totp_timer(self):
        self._tick_totp()

    def _tick_totp(self):
        if hasattr(self, 'manage_tab') and self.manage_tab.totp_display:
            self.manage_tab.totp_display.tick()
        self.after(1000, self._tick_totp)

    # ── 外观切换 ──────────────────────────────────────────

    def _on_appearance_change(self, choice: str):
        mode_map = {"深色": "dark", "浅色": "light", "跟随系统": "system"}
        ctk.set_appearance_mode(mode_map.get(choice, "dark"))

    # ── Excel 导入导出 ────────────────────────────────────

    def _on_export_excel(self):
        filepath = filedialog.asksaveasfilename(
            title="导出到 Excel", defaultextension=".xlsx",
            filetypes=[("Excel 文件", "*.xlsx")],
        )
        if not filepath:
            return
        try:
            accounts = self.account_manager.get_all_accounts()
            export_to_excel(accounts, filepath)
            messagebox.showinfo("导出成功", f"已导出 {len(accounts)} 个账号到:\n{filepath}")
            self._update_status(f"已导出 {len(accounts)} 个账号")
        except Exception as e:
            messagebox.showerror("导出失败", str(e))

    def _on_import_excel(self):
        filepath = filedialog.askopenfilename(
            title="从 Excel 导入", filetypes=[("Excel 文件", "*.xlsx")],
        )
        if not filepath:
            return
        try:
            imported = import_from_excel(filepath)
            if not imported:
                messagebox.showinfo("导入", "文件中没有找到有效的账号数据")
                return
            if not messagebox.askyesno("确认导入", f"将导入 {len(imported)} 个账号，是否继续？"):
                return
            for acc in imported:
                self.account_manager.add_account(
                    email=acc.get("email", ""),
                    password=acc.get("password", ""),
                    recovery_email=acc.get("recovery_email", ""),
                    totp_secret=acc.get("totp_secret", ""),
                    notes=acc.get("notes", ""),
                )
            self._update_status_count()
            messagebox.showinfo("导入成功", f"已导入 {len(imported)} 个账号")
        except Exception as e:
            messagebox.showerror("导入失败", str(e))

    # ── 备份/恢复 ─────────────────────────────────────────

    def _on_backup_data(self):
        src = self.account_manager.data_file
        if not os.path.exists(src):
            messagebox.showinfo("提示", "当前没有数据文件可备份")
            return
        dst = filedialog.asksaveasfilename(
            title="备份数据",
            defaultextension=".json",
            initialfile=f"accounts_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            filetypes=[("JSON 文件", "*.json")]
        )
        if dst:
            shutil.copy2(src, dst)
            messagebox.showinfo("成功", f"数据已备份到:\n{dst}")

    def _on_restore_data(self):
        src = filedialog.askopenfilename(
            title="恢复数据（将覆盖当前数据！）",
            filetypes=[("JSON 文件", "*.json")]
        )
        if not src:
            return
        if not messagebox.askyesno("危险操作", "确定要恢复此备份吗？\n当前所有数据将被覆盖且无法找回！"):
            return

        shutil.copy2(src, self.account_manager.data_file)
        self.account_manager.load()  # 重新加载到内存
        self._update_status_count()
        messagebox.showinfo("成功", "数据已恢复，界面已刷新")


if __name__ == "__main__":
    app = MainApplication()
    app.mainloop()
