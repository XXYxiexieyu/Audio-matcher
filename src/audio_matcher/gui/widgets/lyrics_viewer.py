"""歌词预览组件 — 选项卡式多语言歌词显示。"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Optional

import ttkbootstrap as tb

from audio_matcher.core.models import SyncedLyrics
from audio_matcher.gui.styles import Colors, Fonts, Icons, Spacing


class LyricsPanel(ttk.Frame):
    """歌词预览面板。

    功能：
    - 选项卡切换：原词 / 翻译 / 罗马音
    - 只读但可选择复制
    - 显示歌词来源
    - 等宽字体显示时间戳
    """

    def __init__(self, parent, **kwargs) -> None:
        super().__init__(parent, **kwargs)
        self._current_lyrics: Optional[SyncedLyrics] = None
        self._build()

    # ── Build ──────────────────────────────────────────────────────────

    def _build(self) -> None:
        # 卡片容器
        card = tb.Frame(self, bootstyle="dark", padding=Spacing.MD)
        card.pack(fill="both", expand=True, padx=Spacing.SM, pady=Spacing.SM)

        # 标题 + 来源
        header_frame = ttk.Frame(card)
        header_frame.pack(fill="x", pady=(0, Spacing.MD))

        ttk.Label(
            header_frame,
            text=f"{Icons.MUSIC} 歌词预览",
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

        # 选项卡
        self._notebook = ttk.Notebook(card)
        self._notebook.pack(fill="both", expand=True)

        # 原词选项卡
        self._raw_frame = ttk.Frame(self._notebook)
        self._notebook.add(self._raw_frame, text=" 原词 ")
        self._raw_text = self._create_text_widget(self._raw_frame)

        # 翻译选项卡
        self._trans_frame = ttk.Frame(self._notebook)
        self._notebook.add(self._trans_frame, text=" 翻译 ")
        self._trans_text = self._create_text_widget(self._trans_frame)

        # 罗马音选项卡
        self._romaji_frame = ttk.Frame(self._notebook)
        self._notebook.add(self._romaji_frame, text=" 罗马音 ")
        self._romaji_text = self._create_text_widget(self._romaji_frame)

        # 默认禁用无内容选项卡
        self._update_tabs()

    def _create_text_widget(self, parent) -> tk.Text:
        """创建只读文本控件。"""
        text = tk.Text(
            parent,
            wrap="word",
            font=Fonts.MONO,
            bg=Colors.BG_INPUT,
            fg=Colors.TEXT_PRIMARY,
            insertbackground=Colors.TEXT_PRIMARY,
            selectbackground=Colors.BG_SELECTED,
            relief="flat",
            padx=Spacing.SM,
            pady=Spacing.SM,
        )
        text.pack(fill="both", expand=True)

        # 滚动条
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=text.yview)
        text.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")

        return text

    # ── Data ───────────────────────────────────────────────────────────

    def set_lyrics(self, lyrics: SyncedLyrics) -> None:
        """设置歌词内容。"""
        self._current_lyrics = lyrics

        # 更新来源
        source_text = lyrics.source.value if lyrics.source else ""
        self._source_var.set(source_text)

        # 填充各选项卡
        self._raw_text.config(state="normal")
        self._raw_text.delete("1.0", "end")
        if lyrics.raw_lrc:
            self._raw_text.insert("1.0", lyrics.raw_lrc)
        else:
            self._raw_text.insert("1.0", "暂无原词")
        self._raw_text.config(state="disabled")

        self._trans_text.config(state="normal")
        self._trans_text.delete("1.0", "end")
        if lyrics.translated_lrc:
            self._trans_text.insert("1.0", lyrics.translated_lrc)
        else:
            self._trans_text.insert("1.0", "暂无翻译")
        self._trans_text.config(state="disabled")

        self._romaji_text.config(state="normal")
        self._romaji_text.delete("1.0", "end")
        if lyrics.romanized_lrc:
            self._romaji_text.insert("1.0", lyrics.romanized_lrc)
        else:
            self._romaji_text.insert("1.0", "暂无罗马音")
        self._romaji_text.config(state="disabled")

        # 更新选项卡可用状态
        self._update_tabs()

    def _update_tabs(self) -> None:
        """根据内容更新选项卡可用状态。"""
        if not self._current_lyrics:
            self._notebook.tab(0, state="normal")
            self._notebook.tab(1, state="disabled")
            self._notebook.tab(2, state="disabled")
            return

        # 原词始终可用
        self._notebook.tab(0, state="normal")

        # 翻译
        trans_state = "normal" if self._current_lyrics.translated_lrc else "disabled"
        self._notebook.tab(1, state=trans_state)

        # 罗马音
        romaji_state = "normal" if self._current_lyrics.romanized_lrc else "disabled"
        self._notebook.tab(2, state=romaji_state)

        # 如果当前选项卡被禁用，切换到第一个可用
        try:
            current = self._notebook.index("current")
            if self._notebook.tab(current, "state") == "disabled":
                self._notebook.select(0)
        except tk.TclError:
            pass

    def clear(self) -> None:
        """清空歌词显示。"""
        self._current_lyrics = None
        self._source_var.set("")

        for text in (self._raw_text, self._trans_text, self._romaji_text):
            text.config(state="normal")
            text.delete("1.0", "end")
            text.insert("1.0", "暂无歌词")
            text.config(state="disabled")

        self._update_tabs()
