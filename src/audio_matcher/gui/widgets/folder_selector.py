"""文件夹选择器侧边栏控件。"""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, ttk


class FolderSelector(ttk.Frame):
    """侧边栏控件：浏览并选择音乐目录。"""

    def __init__(self, parent, *, on_scan: callable = None, on_restore: callable = None, **kwargs) -> None:
        super().__init__(parent, **kwargs)
        self._on_scan = on_scan
        self._on_restore_cb = on_restore
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

        # 选项 — ttkbootstrap Checkbutton with round-toggle for clear √ feedback.
        opt_frame = ttk.Frame(self)
        opt_frame.pack(fill="x", padx=5)

        import ttkbootstrap as tb

        self._recursive_var = tk.BooleanVar(value=True)
        cb1 = tb.Checkbutton(
            opt_frame, text="递归子目录",
            variable=self._recursive_var,
            bootstyle="round-toggle",
        )
        cb1.pack(anchor="w", pady=2)

        self._rename_var = tk.BooleanVar(value=True)
        cb2 = tb.Checkbutton(
            opt_frame, text="重命名为 艺人 - 歌名",
            variable=self._rename_var,
            bootstyle="round-toggle",
        )
        cb2.pack(anchor="w", pady=2)

        self._dry_run_var = tk.BooleanVar(value=False)
        cb3 = tb.Checkbutton(
            opt_frame, text="仅预览（不写入）",
            variable=self._dry_run_var,
            bootstyle="round-toggle",
        )
        cb3.pack(anchor="w", pady=2)

        # 恢复文件名按钮
        btn_restore = tb.Button(
            opt_frame, text="恢复原始文件名",
            command=self._on_restore,
            bootstyle="warning-outline",
        )
        btn_restore.pack(anchor="w", pady=(10, 0))

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
                rename_files=self._rename_var.get(),
            )

    def _on_restore(self) -> None:
        if self._on_restore_cb and self._selected_path:
            self._on_restore_cb(self._selected_path)

    @property
    def selected_path(self) -> Path | None:
        return self._selected_path
