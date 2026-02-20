import customtkinter as ctk

from account_manager import AccountManager
from ui_account_list import AccountListPanel
from ui_account_detail import AccountDetailPanel


class ManageTab:
    """账号管理 Tab：左侧列表 + 右侧详情，支持拖拽分隔条调整宽度。"""

    def __init__(self, parent, account_manager: AccountManager,
                 status_callback, on_account_saved):
        self.account_manager = account_manager
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

        # Right: Account detail
        self.detail_panel = AccountDetailPanel(
            parent, account_manager,
            status_callback=status_callback,
        )
        self.detail_panel.grid(row=0, column=2, sticky="nsew")
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

    def _on_account_selected(self, account_id: str):
        self.detail_panel.load_account(account_id)

    def _on_new_account(self):
        self.detail_panel.clear_form()

    def _on_account_saved(self, event=None):
        account_id = self.detail_panel.current_account_id
        self.list_panel.refresh_list(self.list_panel.search_var.get())
        if account_id:
            self.list_panel.select_account_by_id(account_id)
        self.on_account_saved_external()

    # ── Public API ──────────────────────────────────────────────

    def refresh(self):
        self.list_panel.refresh_list(self.list_panel.search_var.get())

    @property
    def totp_display(self):
        return self.detail_panel.totp_display
