"""进度面板控件 — 进度条 + 日志输出。"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk


class ProgressPanel(ttk.Frame):
    """底部面板：进度条 + 可滚动日志。"""

    def __init__(self, parent, **kwargs) -> None:
        super().__init__(parent, **kwargs)
        self._build()

    def _build(self) -> None:
        # 进度条
        self._progress = ttk.Progressbar(self, mode="determinate")
        self._progress.pack(fill="x", padx=5, pady=(5, 0))

        # 状态标签
        self._status_var = tk.StringVar(value="就绪")
        status_label = ttk.Label(self, textvariable=self._status_var, anchor="w")
        status_label.pack(fill="x", padx=5)

        # 日志输出
        self._log = tk.Text(self, wrap="word", height=6, state="disabled")
        self._log.pack(fill="both", expand=True, padx=5, pady=5)

    def set_status(self, text: str) -> None:
        self._status_var.set(text)

    def set_progress(self, current: int, total: int) -> None:
        self._progress["maximum"] = total
        self._progress["value"] = current

    def log(self, message: str) -> None:
        self._log.config(state="normal")
        self._log.insert("end", message + "\n")
        self._log.see("end")
        self._log.config(state="disabled")
