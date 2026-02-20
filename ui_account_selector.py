import customtkinter as ctk

from account_manager import AccountManager, TAG_OPTIONS


class AccountSelectionPanel(ctk.CTkFrame):
    """Reusable account selection panel with search filter, checkboxes,
    sort toggle, select all / none / refresh buttons, and selected count."""

    def __init__(self, parent, account_manager: AccountManager, width: int = 260):
        super().__init__(parent, width=width, corner_radius=8)
        self.pack_propagate(False)
        self.account_manager = account_manager

        self._sort_by = "created"
        self._check_vars: list[tuple[str, ctk.BooleanVar]] = []
        self._check_widgets: list[ctk.CTkCheckBox] = []

        # Header
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=10, pady=(15, 8))
        
        # Title with Icon
        title_row = ctk.CTkFrame(header, fg_color="transparent")
        title_row.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(title_row, text="📋 选择账号",
                     font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold")).pack(side="left")
        
        # Sort Button
        self._sort_btn = ctk.CTkButton(
            title_row, text="导入序", width=54, height=28,
            font=ctk.CTkFont(size=12, weight="bold"), corner_radius=6,
            fg_color=("gray85", "gray30"), hover_color=("gray75", "gray40"),
            text_color=("black", "white"),
            command=self._toggle_sort,
        )
        self._sort_btn.pack(side="right")


        # Select Action Buttons (Grouped)
        sel_btn = ctk.CTkFrame(self, fg_color="transparent")
        sel_btn.pack(fill="x", padx=10, pady=(0, 12))
        
        btn_conf = {
            "width": 60, "height": 28, "font": ctk.CTkFont(size=12),
            "corner_radius": 6, 
            "fg_color": ("gray85", "gray30"), 
            "hover_color": ("gray75", "gray40"),
            "text_color": ("black", "white")
        }
        
        ctk.CTkButton(sel_btn, text="全选", command=self.select_all, **btn_conf).pack(side="left", padx=(0, 6))
        ctk.CTkButton(sel_btn, text="全不选", command=self.select_none, **btn_conf).pack(side="left", padx=(0, 6))
        ctk.CTkButton(sel_btn, text="刷新", command=self.refresh, **btn_conf).pack(side="left")

        # Tag filter
        filter_frame = ctk.CTkFrame(self, fg_color="transparent")
        filter_frame.pack(fill="x", padx=10, pady=(0, 8))
        ctk.CTkLabel(filter_frame, text="标签筛选:", font=ctk.CTkFont(size=11)).pack(side="left")
        self._tag_filter_var = ctk.StringVar(value="全部")
        self._tag_filter = ctk.CTkOptionMenu(
            filter_frame, values=["全部"] + TAG_OPTIONS, variable=self._tag_filter_var,
            width=100, height=26, font=ctk.CTkFont(size=11),
            dropdown_font=ctk.CTkFont(size=11),
            command=lambda *_: self.refresh(),
        )
        self._tag_filter.pack(side="left", padx=(5, 0))

        # Search filter
        self._search_var = ctk.StringVar()
        self._search_var.trace_add("write", lambda *_: self.refresh())
        
        search_frame = ctk.CTkFrame(self, fg_color="transparent")
        search_frame.pack(fill="x", padx=10, pady=(0, 8))
        
        ctk.CTkEntry(
            search_frame, textvariable=self._search_var, height=36,
            placeholder_text="🔍 搜索邮箱...",
            font=ctk.CTkFont(family="Segoe UI", size=13),
            border_width=1, corner_radius=8
        ).pack(fill="x")

        # Scrollable checkbox list
        self._scroll = ctk.CTkScrollableFrame(
            self, corner_radius=6, 
            fg_color=("gray95", "gray20"),
            border_width=1, border_color=("gray80", "gray30")
        )
        self._scroll.pack(fill="both", expand=True, padx=10, pady=(0, 5))

        # Selected count
        self._selected_var = ctk.StringVar(value="已选: 0")
        stat_frame = ctk.CTkFrame(self, height=24, fg_color=("gray90", "#2b2b2b"), corner_radius=4)
        stat_frame.pack(fill="x", padx=10, pady=(5, 10))
        
        ctk.CTkLabel(stat_frame, textvariable=self._selected_var,
                     font=ctk.CTkFont(size=11, weight="bold"),
                     text_color=("gray50", "gray70")).pack(pady=2)

        self.refresh()

    # ── Public API ──────────────────────────────────────

    def refresh(self):
        """Rebuild the checkbox list from current accounts."""
        for w in self._check_widgets:
            w.destroy()
        self._check_widgets.clear()
        self._check_vars.clear()

        accounts = self.account_manager.get_all_accounts(sort_by=self._sort_by)
        filter_text = self._search_var.get().strip().lower()
        tag_filter = self._tag_filter_var.get()
        tag_map = {"家庭组": "🏠", "成品号": "✅", "资格号": "⭐"}

        for acc in accounts:
            email = acc["email"]
            acc_tags = acc.get("tags", [])
            
            if filter_text and filter_text not in email.lower():
                continue
            if tag_filter != "全部" and tag_filter not in acc_tags:
                continue
            
            # Tag badges
            tag_badges = ""
            if acc_tags:
                tag_badges = " " + "".join(tag_map.get(t, "") for t in acc_tags)
            var = ctk.BooleanVar(value=True)
            var.trace_add("write", lambda *_: self._update_selected_count())
            display = email if len(email) <= 25 else email[:22] + "..."
            display += tag_badges
            
            cb = ctk.CTkCheckBox(
                self._scroll, text=display, variable=var,
                font=ctk.CTkFont(size=11), height=28, corner_radius=4,
            )
            cb.pack(fill="x", pady=1)
            self._check_vars.append((acc["id"], var))
            self._check_widgets.append(cb)

        self._update_selected_count()

    def select_all(self):
        for _, var in self._check_vars:
            var.set(True)

    def select_none(self):
        for _, var in self._check_vars:
            var.set(False)

    def get_selected_accounts(self) -> list[dict]:
        """Return account dicts for checked items, preserving panel order."""
        selected_ids = [aid for aid, var in self._check_vars if var.get()]
        if not selected_ids:
            return []
        all_accounts = self.account_manager.get_all_accounts()
        id_to_acc = {acc["id"]: acc for acc in all_accounts}
        return [id_to_acc[aid] for aid in selected_ids if aid in id_to_acc]

    # ── Internal ────────────────────────────────────────

    def _toggle_sort(self):
        if self._sort_by == "created":
            self._sort_by = "email"
            self._sort_btn.configure(text="A→Z")
        else:
            self._sort_by = "created"
            self._sort_btn.configure(text="导入序")
        self.refresh()

    def _update_selected_count(self):
        count = sum(1 for _, var in self._check_vars if var.get())
        total = len(self._check_vars)
        self._selected_var.set(f"已选: {count}/{total}")
