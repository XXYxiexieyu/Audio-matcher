"""标签编辑器组件 — 现代化的元数据编辑表单。"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable, Optional

import ttkbootstrap as tb

from audio_matcher.core.models import MatchSource, TrackMatch, TrackResult
from audio_matcher.gui.styles import Colors, Fonts, Icons, Spacing


class TagEditorPanel(ttk.Frame):
    """标签编辑面板。

    功能：
    - 表单字段编辑（标题/艺人/专辑/年份/轨号）
    - 输入验证
    - 显示匹配来源和置信度
    - 已编辑标记
    - 快捷键 Ctrl+S
    """

    FIELDS = [
        ("title", "标题", 30),
        ("artist", "艺人", 30),
        ("album", "专辑", 30),
        ("year", "年份", 10),
        ("track_number", "轨号", 10),
    ]

    def __init__(
        self,
        parent,
        *,
        on_write: Optional[Callable[[TrackResult], None]] = None,
        **kwargs,
    ) -> None:
        super().__init__(parent, **kwargs)
        self._on_write = on_write
        self._current_result: Optional[TrackResult] = None
        self._entries: dict[str, tk.StringVar] = {}
        self._original_values: dict[str, str] = {}
        self._build()

    # ── Build ──────────────────────────────────────────────────────────

    def _build(self) -> None:
        # 卡片容器
        card = tb.Frame(self, bootstyle="dark", padding=Spacing.MD)
        card.pack(fill="both", expand=True, padx=Spacing.SM, pady=Spacing.SM)

        # 标题 + 来源信息
        header_frame = ttk.Frame(card)
        header_frame.pack(fill="x", pady=(0, Spacing.MD))

        ttk.Label(
            header_frame,
            text=f"{Icons.EDIT} 标签编辑",
            font=Fonts.H3,
            foreground=Colors.TEXT_PRIMARY,
        ).pack(side="left")

        self._source_var = tk.StringVar(value="")
        ttk.Label(
            header_frame,
            textvariable=self._source_var,
            font=Fonts.SMALL,
            foreground=Colors.TEXT_SECONDARY,
        ).pack(side="right")

        # 表单字段
        form_frame = ttk.Frame(card)
        form_frame.pack(fill="x")

        for i, (key, label, width) in enumerate(self.FIELDS):
            # 标签
            ttk.Label(
                form_frame,
                text=f"{label}：",
                font=Fonts.BODY,
                foreground=Colors.TEXT_SECONDARY,
            ).grid(row=i, column=0, sticky="e", padx=(0, Spacing.SM), pady=Spacing.XS)

            # 输入框
            var = tk.StringVar()
            var.trace_add("write", lambda *a, k=key: self._on_field_changed(k))
            entry = ttk.Entry(
                form_frame,
                textvariable=var,
                width=width,
                font=Fonts.BODY,
            )
            entry.grid(row=i, column=1, sticky="ew", pady=Spacing.XS)
            self._entries[key] = var

            # 验证提示
            if key in ("year", "track_number"):
                entry.bind("<FocusOut>", lambda e, k=key: self._validate_number(k))

        form_frame.columnconfigure(1, weight=1)

        # 按钮
        btn_frame = ttk.Frame(card)
        btn_frame.pack(fill="x", pady=(Spacing.MD, 0))

        self._write_btn = tb.Button(
            btn_frame,
            text=f"{Icons.WRITE} 写入标签 (Ctrl+S)",
            command=self._on_write_clicked,
            bootstyle="primary",
            state="disabled",
        )
        self._write_btn.pack(side="left", padx=(0, Spacing.SM))

        tb.Button(
            btn_frame,
            text="还原",
            command=self._revert,
            bootstyle="secondary-outline",
        ).pack(side="left")

        # 快捷键
        self.bind_all("<Control-s>", lambda e: self._on_write_clicked())

    # ── Data ───────────────────────────────────────────────────────────

    def load(self, result: TrackResult) -> None:
        """加载 TrackResult 到编辑器。"""
        self._current_result = result

        # 确定有效匹配
        effective = result.match
        if not effective and result.match_alternatives:
            effective = result.match_alternatives[0]

        # 填充字段
        if effective:
            self._entries["title"].set(effective.title or "")
            self._entries["artist"].set(effective.artist or "")
            self._entries["album"].set(effective.album or "")
            self._entries["year"].set(str(effective.year) if effective.year else "")
            self._entries["track_number"].set(
                str(effective.track_number) if effective.track_number else ""
            )

            # 显示来源信息
            source_text = f"{effective.source.value}"
            if effective.confidence:
                source_text += f" | {effective.confidence:.0%}"
            if result.edited:
                source_text += " | 已编辑"
            self._source_var.set(source_text)
        else:
            # 清空
            for var in self._entries.values():
                var.set("")
            self._source_var.set("无匹配")

        # 保存原始值用于比较
        self._original_values = {
            k: v.get() for k, v in self._entries.items()
        }
        self._update_write_button()

    def _on_field_changed(self, key: str) -> None:
        """字段内容变化。"""
        self._update_write_button()

    def _update_write_button(self) -> None:
        """根据是否有修改更新写入按钮状态。"""
        if not self._current_result:
            self._write_btn.config(state="disabled")
            return

        # 检查是否有修改
        has_changes = any(
            self._entries[k].get() != self._original_values.get(k, "")
            for k in self._entries
        )
        state = "normal" if has_changes else "disabled"
        self._write_btn.config(state=state)

    def _validate_number(self, key: str) -> None:
        """验证数字字段。"""
        value = self._entries[key].get().strip()
        if value:
            try:
                int(value)
            except ValueError:
                # 清除无效输入
                self._entries[key].set("")

    def _revert(self) -> None:
        """还原到原始值。"""
        if self._current_result:
            self.load(self._current_result)

    def _on_write_clicked(self) -> None:
        """写入标签。"""
        if not self._current_result:
            return

        # 如果没有匹配，从编辑器创建
        if not self._current_result.match:
            self._current_result.match = TrackMatch(source=MatchSource.SHAZAM)

        # 更新字段
        self._current_result.match.title = self._entries["title"].get().strip()
        self._current_result.match.artist = self._entries["artist"].get().strip()
        self._current_result.match.album = self._entries["album"].get().strip()

        try:
            year = self._entries["year"].get().strip()
            self._current_result.match.year = int(year) if year else None
        except ValueError:
            self._current_result.match.year = None

        try:
            track = self._entries["track_number"].get().strip()
            self._current_result.match.track_number = int(track) if track else None
        except ValueError:
            self._current_result.match.track_number = None

        self._current_result.edited = True

        if self._on_write:
            self._on_write(self._current_result)

        # 更新按钮状态
        self._original_values = {
            k: v.get() for k, v in self._entries.items()
        }
        self._update_write_button()

    def clear(self) -> None:
        """清空编辑器。"""
        self._current_result = None
        for var in self._entries.values():
            var.set("")
        self._source_var.set("")
        self._original_values = {}
        self._update_write_button()
