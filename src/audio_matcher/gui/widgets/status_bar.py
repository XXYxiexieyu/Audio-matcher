"""状态栏组件 — 单行状态显示 + 可折叠日志面板。"""

from __future__ import annotations

import tkinter as tk
from datetime import datetime
from tkinter import ttk
from typing import Optional

import ttkbootstrap as tb

from audio_matcher.gui.styles import Colors, Fonts, Icons, Sizes, Spacing


class StatusBar(ttk.Frame):
    """底部状态栏。

    功能：
    - 单行状态文字 + 进度条 + 百分比
    - 右侧统计信息
    - 可折叠日志抽屉（时间戳 + 级别颜色）
    """

    def __init__(self, parent, **kwargs) -> None:
        super().__init__(parent, **kwargs)
        self._log_expanded = False
        self._log_lines: list[tuple[str, str, str]] = []  # (timestamp, level, message)
        self._build()

    # ── Build ──────────────────────────────────────────────────────────

    def _build(self) -> None:
        # 主状态行
        main_row = ttk.Frame(self, height=Sizes.STATUS_BAR_HEIGHT)
        main_row.pack(fill="x", padx=Spacing.SM, pady=Spacing.XS)
        main_row.pack_propagate(False)

        # 左侧：状态文字
        self._status_var = tk.StringVar(value="就绪")
        status_label = ttk.Label(
            main_row,
            textvariable=self._status_var,
            font=Fonts.BODY,
            foreground=Colors.TEXT_PRIMARY,
        )
        status_label.pack(side="left", padx=(0, Spacing.MD))

        # 中间：进度条 + 百分比
        progress_frame = ttk.Frame(main_row)
        progress_frame.pack(side="left", fill="x", expand=True, padx=Spacing.MD)

        self._progress = ttk.Progressbar(
            progress_frame,
            mode="determinate",
            length=150,
        )
        self._progress.pack(side="left")

        self._progress_var = tk.StringVar(value="")
        progress_label = ttk.Label(
            progress_frame,
            textvariable=self._progress_var,
            font=Fonts.SMALL,
            foreground=Colors.TEXT_SECONDARY,
            width=6,
        )
        progress_label.pack(side="left", padx=(Spacing.XS, 0))

        # 右侧：统计 + 日志切换
        stats_frame = ttk.Frame(main_row)
        stats_frame.pack(side="right", padx=(Spacing.MD, 0))

        self._stats_var = tk.StringVar(value="")
        stats_label = ttk.Label(
            stats_frame,
            textvariable=self._stats_var,
            font=Fonts.SMALL,
            foreground=Colors.TEXT_SECONDARY,
        )
        stats_label.pack(side="left", padx=(0, Spacing.SM))

        # 日志切换按钮
        self._log_toggle = tb.Button(
            stats_frame,
            text=f"{Icons.EXPAND} 日志",
            command=self._toggle_log,
            bootstyle="link",
        )
        self._log_toggle.pack(side="left")

        # 日志面板（默认隐藏）
        self._log_frame = ttk.Frame(self)
        # 不 pack，默认隐藏

        # 日志工具栏
        log_toolbar = ttk.Frame(self._log_frame)
        log_toolbar.pack(fill="x", padx=Spacing.SM, pady=(0, Spacing.XS))

        ttk.Label(
            log_toolbar,
            text="日志",
            font=Fonts.SMALL_BOLD,
            foreground=Colors.TEXT_PRIMARY,
        ).pack(side="left")

        tb.Button(
            log_toolbar,
            text="清除",
            command=self._clear_log,
            bootstyle="link",
        ).pack(side="right")

        # 日志文本
        log_container = ttk.Frame(self._log_frame)
        log_container.pack(fill="both", expand=True, padx=Spacing.SM, pady=(0, Spacing.SM))

        self._log_text = tk.Text(
            log_container,
            wrap="word",
            font=Fonts.SMALL,
            bg=Colors.BG_INPUT,
            fg=Colors.TEXT_PRIMARY,
            state="disabled",
            height=6,
        )
        self._log_text.pack(side="left", fill="both", expand=True)

        log_scrollbar = ttk.Scrollbar(
            log_container, orient="vertical", command=self._log_text.yview
        )
        self._log_text.configure(yscrollcommand=log_scrollbar.set)
        log_scrollbar.pack(side="right", fill="y")

        # 配置日志级别标签
        self._log_text.tag_configure("info", foreground=Colors.TEXT_PRIMARY)
        self._log_text.tag_configure("success", foreground=Colors.SUCCESS)
        self._log_text.tag_configure("warning", foreground=Colors.WARNING)
        self._log_text.tag_configure("error", foreground=Colors.ERROR)

    # ── Public API ─────────────────────────────────────────────────────

    def set_status(self, text: str) -> None:
        """设置状态文字。"""
        self._status_var.set(text)

    def set_progress(self, current: int, total: int) -> None:
        """设置进度。"""
        self._progress["maximum"] = total
        self._progress["value"] = current
        if total > 0:
            pct = int(current / total * 100)
            self._progress_var.set(f"{pct}%")
        else:
            self._progress_var.set("")

    def set_stats(self, tagged: int, lyrics: int, errors: int, awaiting: int = 0) -> None:
        """设置统计信息。"""
        parts = [f"✓{tagged}", f"♪{lyrics}", f"✗{errors}"]
        if awaiting:
            parts.append(f"?{awaiting}")
        self._stats_var.set(" | ".join(parts))

    def log(self, message: str, level: str = "info") -> None:
        """添加日志。

        Args:
            message: 日志内容
            level: 级别 (info/success/warning/error)
        """
        timestamp = datetime.now().strftime("%H:%M:%S")
        self._log_lines.append((timestamp, level, message))

        # 更新显示
        self._log_text.config(state="normal")
        self._log_text.insert("end", f"[{timestamp}] ", "info")
        self._log_text.insert("end", message + "\n", level)
        self._log_text.see("end")
        self._log_text.config(state="disabled")

    def log_success(self, message: str) -> None:
        self.log(message, "success")

    def log_warning(self, message: str) -> None:
        self.log(message, "warning")

    def log_error(self, message: str) -> None:
        self.log(message, "error")

    # ── Log Panel ──────────────────────────────────────────────────────

    def _toggle_log(self) -> None:
        """切换日志面板显示。"""
        self._log_expanded = not self._log_expanded

        if self._log_expanded:
            self._log_frame.pack(fill="both", expand=True)
            self._log_toggle.configure(text=f"{Icons.COLLAPSE} 日志")
        else:
            self._log_frame.pack_forget()
            self._log_toggle.configure(text=f"{Icons.EXPAND} 日志")

    def _clear_log(self) -> None:
        """清除日志。"""
        self._log_lines.clear()
        self._log_text.config(state="normal")
        self._log_text.delete("1.0", "end")
        self._log_text.config(state="disabled")
