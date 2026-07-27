"""文件夹选择器侧边栏控件。"""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, ttk


class FolderSelector(ttk.Frame):
    """侧边栏控件：浏览并选择音乐目录。"""

    def __init__(self, parent, *, on_scan: callable = None, **kwargs) -> None:
        super().__init__(parent, **kwargs)
        self._on_scan = on_scan
        self._selected_path: Path | None = None
        self._build()

    def _build(self) -> None:
        # 标题
        header = ttk.Label(self, text="音乐目录", font=("", 11, "bold"))
        header.pack(pady=(5, 10))

        # 路径显示
        self._path_var = tk.StringVar(value="未选择目录")
        path_label = ttk.Label(self, textvariable=self._path_var, wraplength=200)
        path_label.pack(pady=(0, 10))

        # 浏览按钮
        btn_browse = ttk.Button(self, text="浏览...", command=self._on_browse)
        btn_browse.pack(pady=(0, 5))

        # 扫描按钮
        self._btn_scan = ttk.Button(
            self, text="扫描识别",
            command=self._on_scan_clicked,
            state="disabled",
        )
        self._btn_scan.pack(pady=(5, 10))

        # 分隔线
        ttk.Separator(self, orient="horizontal").pack(fill="x", pady=10)

        # 选项
        self._recursive_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            self, text="递归子目录", variable=self._recursive_var,
        ).pack(anchor="w", padx=10)

        self._dry_run_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            self, text="仅预览（不写入）", variable=self._dry_run_var,
        ).pack(anchor="w", padx=10)

    def _on_browse(self) -> None:
        path_str = filedialog.askdirectory(title="选择音乐目录")
        if path_str:
            self._selected_path = Path(path_str)
            self._path_var.set(str(self._selected_path))
            self._btn_scan.config(state="normal")

    def _on_scan_clicked(self) -> None:
        if self._on_scan and self._selected_path:
            self._on_scan(
                self._selected_path,
                recursive=self._recursive_var.get(),
                dry_run=self._dry_run_var.get(),
            )

    @property
    def selected_path(self) -> Path | None:
        return self._selected_path
