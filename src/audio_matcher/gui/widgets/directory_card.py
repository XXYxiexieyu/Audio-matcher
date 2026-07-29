"""目录选择卡片组件 — 现代化的目录浏览和文件选择。"""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, ttk
from typing import Callable, Optional

import ttkbootstrap as tb

from audio_matcher.core.config import Config
from audio_matcher.core.models import AudioFile
from audio_matcher.core.scanner import AudioScanner
from audio_matcher.gui.styles import Colors, Fonts, Icons, Sizes, Spacing


class DirectoryCard(ttk.Frame):
    """目录选择卡片：浏览目录、显示文件列表、启动扫描。

    Callbacks
    --------
    on_scan(path, files, language, dry_run, rename_files)
        用户点击「开始扫描」时调用。
    on_cancel()
        用户点击「取消扫描」时调用。
    """

    def __init__(
        self,
        parent,
        *,
        config: Config,
        on_scan: Optional[Callable] = None,
        on_cancel: Optional[Callable] = None,
        **kwargs,
    ) -> None:
        super().__init__(parent, **kwargs)
        self._config = config  # 使用传入的 Config，修复配置 bug
        self._on_scan = on_scan
        self._on_cancel = on_cancel
        self._selected_path: Optional[Path] = None
        self._audio_files: list[AudioFile] = []
        self._file_vars: dict[str, tk.BooleanVar] = {}
        self._is_scanning = False
        self._build()

    # ── Build ──────────────────────────────────────────────────────────

    def _build(self) -> None:
        # 卡片容器
        card = tb.Frame(self, bootstyle="dark", padding=Spacing.MD)
        card.pack(fill="both", expand=True, padx=Spacing.SM, pady=Spacing.SM)

        # 标题
        header = ttk.Label(
            card,
            text=f"{Icons.FOLDER} 音乐目录",
            font=Fonts.H3,
            foreground=Colors.TEXT_PRIMARY,
        )
        header.pack(anchor="w", pady=(0, Spacing.MD))

        # 路径显示
        self._path_var = tk.StringVar(value="未选择目录")
        path_frame = ttk.Frame(card)
        path_frame.pack(fill="x", pady=(0, Spacing.SM))

        path_label = ttk.Label(
            path_frame,
            textvariable=self._path_var,
            font=Fonts.SMALL,
            foreground=Colors.TEXT_SECONDARY,
            wraplength=220,
        )
        path_label.pack(side="left", fill="x", expand=True)

        # 浏览按钮
        browse_btn = tb.Button(
            card,
            text="选择文件夹",
            command=self._on_browse,
            bootstyle="primary-outline",
            width=15,
        )
        browse_btn.pack(fill="x", pady=(0, Spacing.MD))

        # 文件列表标题 + 统计
        list_header = ttk.Frame(card)
        list_header.pack(fill="x", pady=(Spacing.SM, Spacing.XS))

        ttk.Label(
            list_header,
            text="文件列表",
            font=Fonts.SMALL_BOLD,
            foreground=Colors.TEXT_PRIMARY,
        ).pack(side="left")

        self._count_var = tk.StringVar(value="")
        ttk.Label(
            list_header,
            textvariable=self._count_var,
            font=Fonts.SMALL,
            foreground=Colors.TEXT_SECONDARY,
        ).pack(side="right")

        # 文件列表（Treeview）
        list_container = ttk.Frame(card)
        list_container.pack(fill="both", expand=True, pady=(0, Spacing.SM))

        # 创建 Treeview
        self._tree = ttk.Treeview(
            list_container,
            columns=("selected", "name"),
            show="headings",
            height=8,
            selectmode="none",
        )
        self._tree.heading("selected", text="")
        self._tree.heading("name", text="文件名")
        self._tree.column("selected", width=30, anchor="center", stretch=False)
        self._tree.column("name", width=180, anchor="w")

        # 滚动条
        scrollbar = ttk.Scrollbar(
            list_container, orient="vertical", command=self._tree.yview
        )
        self._tree.configure(yscrollcommand=scrollbar.set)

        self._tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # 绑定点击事件（切换复选框）
        self._tree.bind("<Button-1>", self._on_tree_click)

        # 全选/全不选按钮
        btn_row = ttk.Frame(card)
        btn_row.pack(fill="x", pady=(0, Spacing.SM))

        tb.Button(
            btn_row,
            text="全选",
            command=self._select_all,
            bootstyle="link",
        ).pack(side="left", padx=(0, Spacing.SM))

        tb.Button(
            btn_row,
            text="全不选",
            command=self._deselect_all,
            bootstyle="link",
        ).pack(side="left")

        # 扫描/取消按钮
        self._action_btn = tb.Button(
            card,
            text=f"{Icons.PLAY} 开始扫描",
            command=self._on_action,
            bootstyle="primary",
            state="disabled",
            width=15,
        )
        self._action_btn.pack(fill="x", pady=(Spacing.SM, 0))

    # ── File list helpers ──────────────────────────────────────────────

    def _refresh_file_list(self) -> None:
        """扫描目录并更新文件列表。"""
        # 清空
        for item in self._tree.get_children():
            self._tree.delete(item)
        self._file_vars.clear()
        self._audio_files.clear()

        if self._selected_path is None:
            self._count_var.set("")
            self._action_btn.config(state="disabled")
            return

        # 使用传入的 Config 扫描
        scanner = AudioScanner(self._config)
        try:
            self._audio_files = scanner.scan(
                self._selected_path,
                recursive=True,
            )
        except Exception:
            self._audio_files = []

        if not self._audio_files:
            self._count_var.set("未找到音频文件")
            self._action_btn.config(state="disabled")
            return

        # 填充 Treeview
        for af in sorted(self._audio_files, key=lambda f: f.path.name.lower()):
            var = tk.BooleanVar(value=True)
            self._file_vars[af.id] = var

            self._tree.insert(
                "",
                "end",
                iid=af.id,
                values=(Icons.CHECKED, af.path.name),
            )

        count = len(self._audio_files)
        self._count_var.set(f"{count} 个文件")
        self._action_btn.config(state="normal")

    def _on_tree_click(self, event) -> None:
        """处理 Treeview 点击，切换复选框状态。"""
        region = self._tree.identify_region(event.x, event.y)
        if region != "cell":
            return

        column = self._tree.identify_column(event.x)
        item = self._tree.identify_row(event.y)

        if column == "#1" and item:  # 点击了选中列
            var = self._file_vars.get(item)
            if var:
                new_val = not var.get()
                var.set(new_val)
                icon = Icons.CHECKED if new_val else Icons.UNCHECKED
                self._tree.set(item, "selected", icon)
                self._update_scan_button()

    def _select_all(self) -> None:
        for af_id, var in self._file_vars.items():
            var.set(True)
            self._tree.set(af_id, "selected", Icons.CHECKED)
        self._update_scan_button()

    def _deselect_all(self) -> None:
        for af_id, var in self._file_vars.items():
            var.set(False)
            self._tree.set(af_id, "selected", Icons.UNCHECKED)
        self._update_scan_button()

    def _update_scan_button(self) -> None:
        """根据选中状态更新扫描按钮。"""
        if self._is_scanning:
            return
        any_selected = any(var.get() for var in self._file_vars.values())
        state = "normal" if any_selected else "disabled"
        self._action_btn.config(state=state)

    def get_selected_files(self) -> list[AudioFile]:
        """返回当前选中的文件列表。"""
        return [
            af for af in self._audio_files
            if self._file_vars.get(af.id, tk.BooleanVar(value=False)).get()
        ]

    # ── Events ─────────────────────────────────────────────────────────

    def _on_browse(self) -> None:
        path_str = filedialog.askdirectory(title="选择音乐目录")
        if path_str:
            self._selected_path = Path(path_str)
            # 缩短路径显示
            display = str(self._selected_path)
            if len(display) > 35:
                display = "..." + display[-32:]
            self._path_var.set(display)
            self._action_btn.config(state="disabled")
            self._refresh_file_list()

    def _on_action(self) -> None:
        if self._is_scanning:
            # 取消扫描
            if self._on_cancel:
                self._on_cancel()
            self.set_scanning(False)
        else:
            # 开始扫描
            selected = self.get_selected_files()
            if not selected:
                return

            self.set_scanning(True)
            if self._on_scan:
                self._on_scan(
                    self._selected_path,
                    selected,
                )

    def set_scanning(self, scanning: bool) -> None:
        """设置扫描状态。"""
        self._is_scanning = scanning
        if scanning:
            self._action_btn.config(
                text=f"{Icons.STOP} 取消扫描",
                bootstyle="danger",
                state="normal",
            )
        else:
            self._action_btn.config(
                text=f"{Icons.PLAY} 开始扫描",
                bootstyle="primary",
            )
            self._update_scan_button()

    @property
    def selected_path(self) -> Optional[Path]:
        return self._selected_path

    @property
    def is_scanning(self) -> bool:
        return self._is_scanning
