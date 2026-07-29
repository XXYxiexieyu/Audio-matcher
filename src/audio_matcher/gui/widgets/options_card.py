"""选项卡片组件 — 扫描选项和歌词语言设置。"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable, Optional

import ttkbootstrap as tb

from audio_matcher.gui.styles import Colors, Fonts, Icons, Spacing


# 歌词语言选项
_LANG_OPTIONS = [
    ("仅外语", "original_only"),
    ("双语", "bilingual"),
    ("日语+罗马音", "japanese_romaji"),
    ("双语+罗马音", "bilingual_romaji"),
]


class OptionsCard(ttk.Frame):
    """选项卡片：递归/重命名/预览模式/歌词语言/恢复文件名。

    Callbacks
    ---------
    on_restore(path)
        用户点击「恢复原始文件名」时调用。
    """

    def __init__(
        self,
        parent,
        *,
        on_restore: Optional[Callable] = None,
        **kwargs,
    ) -> None:
        super().__init__(parent, **kwargs)
        self._on_restore_cb = on_restore
        self._build()

    # ── Build ──────────────────────────────────────────────────────────

    def _build(self) -> None:
        # 卡片容器
        card = tb.Frame(self, bootstyle="dark", padding=Spacing.MD)
        card.pack(fill="both", expand=True, padx=Spacing.SM, pady=Spacing.SM)

        # 标题
        header = ttk.Label(
            card,
            text=f"{Icons.SETTINGS} 扫描选项",
            font=Fonts.H3,
            foreground=Colors.TEXT_PRIMARY,
        )
        header.pack(anchor="w", pady=(0, Spacing.MD))

        # ── 开关选项 ──
        # 递归子目录
        self._recursive_var = tk.BooleanVar(value=True)
        recursive_cb = tb.Checkbutton(
            card,
            text="递归扫描子目录",
            variable=self._recursive_var,
            bootstyle="round-toggle",
        )
        recursive_cb.pack(anchor="w", pady=Spacing.XS)

        # 重命名文件
        self._rename_var = tk.BooleanVar(value=True)
        rename_cb = tb.Checkbutton(
            card,
            text="重命名为「歌名 - 艺人」",
            variable=self._rename_var,
            bootstyle="round-toggle",
        )
        rename_cb.pack(anchor="w", pady=Spacing.XS)

        # 预览模式
        self._dry_run_var = tk.BooleanVar(value=False)
        dry_run_cb = tb.Checkbutton(
            card,
            text="仅预览（不写入文件）",
            variable=self._dry_run_var,
            bootstyle="round-toggle",
        )
        dry_run_cb.pack(anchor="w", pady=Spacing.XS)

        # ── 歌词语言 ──
        lang_frame = ttk.Frame(card)
        lang_frame.pack(fill="x", pady=(Spacing.MD, Spacing.XS))

        ttk.Label(
            lang_frame,
            text="歌词语言：",
            font=Fonts.BODY,
            foreground=Colors.TEXT_PRIMARY,
        ).pack(anchor="w")

        self._lang_var = tk.StringVar(value="original_only")
        self._lang_buttons: list[tb.Button] = []

        # 分段选择器（2x2 网格）
        btn_frame = ttk.Frame(lang_frame)
        btn_frame.pack(fill="x", pady=(Spacing.XS, 0))

        for i, (label, value) in enumerate(_LANG_OPTIONS):
            btn = tb.Button(
                btn_frame,
                text=label,
                command=lambda v=value: self._set_language(v),
                bootstyle="secondary-outline",
                width=12,
            )
            row, col = divmod(i, 2)
            btn.grid(row=row, column=col, padx=2, pady=2, sticky="ew")
            self._lang_buttons.append(btn)

        btn_frame.columnconfigure(0, weight=1)
        btn_frame.columnconfigure(1, weight=1)

        # 初始选中状态
        self._update_lang_buttons()

        # ── 恢复文件名 ──
        restore_btn = tb.Button(
            card,
            text=f"{Icons.REFRESH} 恢复原始文件名",
            command=self._on_restore,
            bootstyle="warning-outline",
            width=20,
        )
        restore_btn.pack(fill="x", pady=(Spacing.LG, 0))

    def _set_language(self, value: str) -> None:
        """设置歌词语言。"""
        self._lang_var.set(value)
        self._update_lang_buttons()

    def _update_lang_buttons(self) -> None:
        """更新语言按钮选中状态。"""
        current = self._lang_var.get()
        for btn, (label, value) in zip(self._lang_buttons, _LANG_OPTIONS):
            if value == current:
                btn.configure(bootstyle="primary")
            else:
                btn.configure(bootstyle="secondary-outline")

    def _on_restore(self) -> None:
        """恢复原始文件名。"""
        if self._on_restore_cb:
            self._on_restore_cb()

    # ── Public API ─────────────────────────────────────────────────────

    @property
    def recursive(self) -> bool:
        return self._recursive_var.get()

    @property
    def rename_files(self) -> bool:
        return self._rename_var.get()

    @property
    def dry_run(self) -> bool:
        return self._dry_run_var.get()

    @property
    def language(self) -> str:
        return self._lang_var.get()

    def set_enabled(self, enabled: bool) -> None:
        """启用/禁用所有选项（扫描时禁用）。"""
        state = "normal" if enabled else "disabled"
        for child in self.winfo_children():
            self._set_child_state(child, state)

    def _set_child_state(self, widget, state: str) -> None:
        """递归设置子控件状态。"""
        try:
            widget.configure(state=state)
        except tk.TclError:
            pass
        for child in widget.winfo_children():
            self._set_child_state(child, state)
