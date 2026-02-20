import customtkinter as ctk
import tkinter
from tkinter import messagebox

from account_manager import AccountManager, TAG_OPTIONS


class AccountListPanel(ctk.CTkFrame):
    def __init__(self, parent, account_manager, on_select_callback, on_new_callback):
        super().__init__(parent, corner_radius=0)
        self.account_manager = account_manager
        self.on_select_callback = on_select_callback
        self.on_new_callback = on_new_callback
        self._account_ids: list[str] = []
        self._sort_by = "created"  # "email" or "created"

        # Header + sort toggle
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.pack(fill="x", padx=15, pady=(15, 8))
        ctk.CTkLabel(header_frame, text="账号列表", font=ctk.CTkFont(size=15, weight="bold")
                     ).pack(side="left")
        self._sort_btn = ctk.CTkButton(
            header_frame, text="导入序", width=60, height=26,
            font=ctk.CTkFont(size=11), corner_radius=6,
            fg_color=("gray75", "gray30"), hover_color=("gray65", "gray40"),
            command=self._toggle_sort,
        )
        self._sort_btn.pack(side="right")

        # Search
        self.search_var = ctk.StringVar()
        self.search_var.trace_add("write", self._on_search_changed)
        search_entry = ctk.CTkEntry(self, textvariable=self.search_var,
                                     placeholder_text="搜索账号...", height=32)
        search_entry.pack(fill="x", padx=10, pady=(0, 5))

        # Tag filter
        filter_frame = ctk.CTkFrame(self, fg_color="transparent")
        filter_frame.pack(fill="x", padx=10, pady=(0, 8))
        ctk.CTkLabel(filter_frame, text="筛选:", font=ctk.CTkFont(size=11)).pack(side="left")
        self._tag_filter_var = ctk.StringVar(value="全部")
        self._tag_filter = ctk.CTkOptionMenu(
            filter_frame, values=["全部"] + TAG_OPTIONS, variable=self._tag_filter_var,
            width=100, height=26, font=ctk.CTkFont(size=11),
            dropdown_font=ctk.CTkFont(size=11),
            command=lambda *_: self.refresh_list(self.search_var.get()),
        )
        self._tag_filter.pack(side="left", padx=(5, 0))

        # Scrollable list
        self.scroll_frame = ctk.CTkScrollableFrame(self, corner_radius=8)
        self.scroll_frame.pack(fill="both", expand=True, padx=10, pady=(0, 8))

        self._item_buttons: list[ctk.CTkFrame] = []
        self._selected_indices: set[int] = set()
        self._last_clicked_idx: int = -1

        # Buttons
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=10, pady=(0, 10))
        ctk.CTkButton(btn_frame, text="+ 添加", width=80, height=30,
                      fg_color="#2ecc71", hover_color="#27ae60",
                      command=self._on_add).pack(side="left", padx=(0, 5))
        ctk.CTkButton(btn_frame, text="- 删除", width=80, height=30,
                      fg_color="#e74c3c", hover_color="#c0392b",
                      command=self._on_delete).pack(side="left", padx=(0, 5))
        ctk.CTkButton(btn_frame, text="批量删除", width=80, height=30,
                      fg_color="#e67e22", hover_color="#d35400",
                      command=self._on_batch_delete).pack(side="left")

        self.refresh_list()

    def _toggle_sort(self):
        if self._sort_by == "created":
            self._sort_by = "email"
            self._sort_btn.configure(text="A→Z")
        else:
            self._sort_by = "created"
            self._sort_btn.configure(text="导入序")
        self.refresh_list(self.search_var.get())

    def refresh_list(self, filter_text: str = ""):
        prev_selected_ids = self.get_selected_account_ids() if hasattr(self, '_selected_indices') else []
        for btn in self._item_buttons:
            btn.destroy()
        self._item_buttons.clear()
        self._account_ids.clear()
        self._selected_indices = set()
        self._last_clicked_idx = -1

        if filter_text:
            accounts = self.account_manager.search_accounts(filter_text, sort_by=self._sort_by)
        else:
            accounts = self.account_manager.get_all_accounts(sort_by=self._sort_by)

        tag_map = {"家庭组": "🏠", "成品号": "✅", "资格号": "⭐"}
        tag_colors = {"家庭组": "#2980b9", "成品号": "#27ae60", "资格号": "#8e44ad"}

        for i, acc in enumerate(accounts):
            # Apply tag filter
            tag_filter = self._tag_filter_var.get()
            if tag_filter != "全部":
                if tag_filter not in acc.get("tags", []):
                    continue

            email = acc["email"]
            acc_tags = acc.get("tags", [])
            acc_id = acc["id"]

            # Row frame
            row = ctk.CTkFrame(self.scroll_frame, fg_color="transparent", height=36)
            row.pack(fill="x", pady=1)
            row.pack_propagate(False)

            list_idx = len(self._item_buttons)

            # Email button (takes remaining space)
            display = email if len(email) <= 24 else email[:21] + "..."
            email_btn = ctk.CTkButton(
                row, text=display, anchor="w",
                font=ctk.CTkFont(size=12), height=34, corner_radius=6,
                fg_color="transparent", text_color=("gray10", "gray90"),
                hover_color=("gray85", "gray30"),
            )
            email_btn.bind("<Button-1>", lambda e, idx=list_idx: self._on_click(e, idx))
            email_btn.pack(side="left", fill="x", expand=True)

            # Context Menu on email button
            def show_menu(event, _acc=acc):
                menu = tkinter.Menu(self, tearoff=0)
                menu.add_command(label="复制邮箱", command=lambda: self._copy_to_clip(_acc["email"]))
                menu.add_command(label="复制密码", command=lambda: self._copy_to_clip(_acc["password"]))
                menu.add_command(label="复制TOTP密钥", command=lambda: self._copy_to_clip(_acc.get("totp_secret", "")))
                full_line = AccountManager.format_line(_acc)
                menu.add_command(label="复制完整行", command=lambda: self._copy_to_clip(full_line))
                menu.post(event.x_root, event.y_root)

            email_btn.bind("<Button-3>", show_menu)

            # Tag toggle buttons
            for tag_name in TAG_OPTIONS:
                emoji = tag_map[tag_name]
                is_active = tag_name in acc_tags
                tag_btn = ctk.CTkButton(
                    row, text=emoji, width=28, height=28,
                    font=ctk.CTkFont(size=12), corner_radius=4,
                    fg_color=tag_colors[tag_name] if is_active else ("gray80", "gray25"),
                    hover_color=tag_colors[tag_name],
                    command=lambda _id=acc_id, _tag=tag_name: self._toggle_tag(_id, _tag),
                )
                tag_btn.pack(side="left", padx=1)

            self._item_buttons.append(row)  # store row frame for cleanup
            self._account_ids.append(acc_id)

        # Restore multi-selection logic
        for idx, aid in enumerate(self._account_ids):
            if aid in prev_selected_ids:
                self._selected_indices.add(idx)
                self._last_clicked_idx = idx

        self._update_highlighting()

    def _toggle_tag(self, account_id: str, tag_name: str):
        """Toggle a tag on an account and refresh the list."""
        acc = self.account_manager.get_account(account_id)
        if not acc:
            return
        tags = acc.get("tags", [])
        if tag_name in tags:
            tags.remove(tag_name)
        else:
            tags.append(tag_name)
        self.account_manager.update_account(account_id, tags=tags)
        # Refresh but keep current filter/search, which natively preserves multi-select state
        self.refresh_list(self.search_var.get())

    def _copy_to_clip(self, text):
        if text:
            self.clipboard_clear()
            self.clipboard_append(text)
            messagebox.showinfo("提示", "已复制到剪贴板")


    def get_selected_account_ids(self) -> list[str]:
        if not hasattr(self, '_selected_indices'):
            return []
        return [self._account_ids[i] for i in sorted(self._selected_indices) if 0 <= i < len(self._account_ids)]

    def select_account_by_id(self, account_id: str):
        if account_id in self._account_ids:
            idx = self._account_ids.index(account_id)
            self._selected_indices = {idx}
            self._last_clicked_idx = idx
            self._update_highlighting()

    def _update_highlighting(self):
        for i, row in enumerate(self._item_buttons):
            children = row.winfo_children()
            if not children:
                continue
            btn = children[0]
            if i in self._selected_indices:
                btn.configure(fg_color=("#1a73e8", "#1a73e8"), text_color="white")
            else:
                btn.configure(fg_color="transparent", text_color=("gray10", "gray90"))

    def _on_search_changed(self, *args):
        self.refresh_list(self.search_var.get())

    def _on_click(self, event, idx: int):
        ctrl_pressed = (event.state & 0x0004) != 0
        shift_pressed = (event.state & 0x0001) != 0

        if shift_pressed and self._last_clicked_idx != -1:
            start = min(self._last_clicked_idx, idx)
            end = max(self._last_clicked_idx, idx)
            if not ctrl_pressed:
                self._selected_indices.clear()
            for i in range(start, end + 1):
                self._selected_indices.add(i)
        elif ctrl_pressed:
            if idx in self._selected_indices:
                self._selected_indices.remove(idx)
            else:
                self._selected_indices.add(idx)
            self._last_clicked_idx = idx
        else:
            self._selected_indices = {idx}
            self._last_clicked_idx = idx

        self._update_highlighting()
        
        # Load the newly clicked account to detail panel if it's selected
        if idx in self._selected_indices:
            self.on_select_callback(self._account_ids[idx])
        else:
            if not self._selected_indices:
                self.on_new_callback()
            else:
                last_idx = list(self._selected_indices)[-1]
                self.on_select_callback(self._account_ids[last_idx])

    def _on_add(self):
        self._selected_indices.clear()
        self._update_highlighting()
        self.on_new_callback()

    def _on_delete(self):
        account_ids = self.get_selected_account_ids()
        if not account_ids:
            messagebox.showwarning("提示", "请先选择要删除的账号")
            return
            
        if len(account_ids) == 1:
            acc = self.account_manager.get_account(account_ids[0])
            name = acc["email"] if acc else "未知"
            msg = f"确定要删除账号 \"{name}\" 吗？"
        else:
            msg = f"确定要删除选中的 {len(account_ids)} 个账号吗？\n此操作不可撤销！"
            
        if messagebox.askyesno("确认删除", msg):
            for aid in account_ids:
                self.account_manager.delete_account(aid)
            self.refresh_list(self.search_var.get())
            self.on_new_callback()

    def _on_batch_delete(self):
        accounts = self.account_manager.get_all_accounts(sort_by=self._sort_by)
        if not accounts:
            messagebox.showwarning("提示", "没有可删除的账号")
            return

        dialog = ctk.CTkToplevel(self.winfo_toplevel())
        dialog.title("批量删除账号")
        dialog.geometry("420x500")
        dialog.resizable(False, True)
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()

        ctk.CTkLabel(dialog, text="选择要删除的账号:",
                     font=ctk.CTkFont(size=14, weight="bold")).pack(
            anchor="w", padx=15, pady=(15, 5))

        # Select all / none buttons
        sel_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        sel_frame.pack(fill="x", padx=15, pady=(0, 5))

        check_vars: list[tuple[str, str, ctk.BooleanVar]] = []

        def select_all():
            for _, _, var in check_vars:
                var.set(True)

        def select_none():
            for _, _, var in check_vars:
                var.set(False)

        ctk.CTkButton(sel_frame, text="全选", width=55, height=26,
                      font=ctk.CTkFont(size=11),
                      fg_color=("gray75", "gray30"), hover_color=("gray65", "gray40"),
                      command=select_all).pack(side="left", padx=(0, 5))
        ctk.CTkButton(sel_frame, text="全不选", width=55, height=26,
                      font=ctk.CTkFont(size=11),
                      fg_color=("gray75", "gray30"), hover_color=("gray65", "gray40"),
                      command=select_none).pack(side="left")

        count_var = ctk.StringVar(value=f"已选: 0/{len(accounts)}")
        ctk.CTkLabel(sel_frame, textvariable=count_var,
                     font=ctk.CTkFont(size=11)).pack(side="right")

        def update_count(*_):
            n = sum(1 for _, _, v in check_vars if v.get())
            count_var.set(f"已选: {n}/{len(accounts)}")

        # Scrollable checkbox list
        scroll = ctk.CTkScrollableFrame(dialog, corner_radius=6)
        scroll.pack(fill="both", expand=True, padx=15, pady=(0, 10))

        for acc in accounts:
            var = ctk.BooleanVar(value=False)
            var.trace_add("write", update_count)
            email = acc["email"]
            display = email if len(email) <= 40 else email[:37] + "..."
            ctk.CTkCheckBox(scroll, text=display, variable=var,
                            font=ctk.CTkFont(size=12), height=30,
                            corner_radius=4).pack(fill="x", pady=1)
            check_vars.append((acc["id"], acc["email"], var))

        # Confirm / Cancel buttons
        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack(fill="x", padx=15, pady=(0, 15))

        def do_delete():
            selected = [(aid, email) for aid, email, var in check_vars if var.get()]
            if not selected:
                messagebox.showwarning("提示", "请先勾选要删除的账号", parent=dialog)
                return
            if not messagebox.askyesno("确认批量删除",
                    f"确定要删除选中的 {len(selected)} 个账号吗？\n此操作不可撤销！",
                    parent=dialog):
                return
            for aid, _ in selected:
                self.account_manager.delete_account(aid)
            dialog.destroy()
            self.refresh_list(self.search_var.get())
            self.on_new_callback()

        ctk.CTkButton(btn_frame, text="删除选中", width=120, height=34,
                      font=ctk.CTkFont(size=13, weight="bold"),
                      fg_color="#e74c3c", hover_color="#c0392b",
                      command=do_delete).pack(side="left")
        ctk.CTkButton(btn_frame, text="取消", width=80, height=34,
                      fg_color=("gray70", "gray35"), hover_color=("gray60", "gray45"),
                      command=dialog.destroy).pack(side="left", padx=(10, 0))
