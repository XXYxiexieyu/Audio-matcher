"""歌词预览控件 — 多语言歌词分段显示（v0.0.5）。"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from audio_matcher.core.models import SyncedLyrics


class LyricsViewer(ttk.Frame):
    """可滚动的同步歌词显示区域，支持原文 / 翻译 / 罗马音分段。"""

    def __init__(self, parent, **kwargs) -> None:
        super().__init__(parent, **kwargs)
        self._build()

    def _build(self) -> None:
        header = ttk.Label(self, text="歌词预览", font=("", 11, "bold"))
        header.pack(pady=(5, 5))

        self._text = tk.Text(self, wrap="word", state="disabled", height=12)
        self._text.pack(fill="both", expand=True, padx=5, pady=5)

    def set_lyrics(self, lyrics: SyncedLyrics) -> None:
        """Display all available lyrics variants with section headers."""
        self._text.config(state="normal")
        self._text.delete("1.0", "end")

        parts: list[tuple[str, str]] = []

        if lyrics.raw_lrc:
            parts.append(("── 原词 / Original ──", lyrics.raw_lrc))
        if lyrics.translated_lrc:
            parts.append(("── 翻译 / Translation ──", lyrics.translated_lrc))
        if lyrics.romanized_lrc:
            parts.append(("── 罗马音 / Romaji ──", lyrics.romanized_lrc))

        if parts:
            for i, (header_text, body) in enumerate(parts):
                if i > 0:
                    self._text.insert("end", "\n\n")
                self._text.insert("end", header_text + "\n")
                self._text.insert("end", body)
        else:
            self._text.insert("1.0", "暂无歌词")

        self._text.config(state="disabled")

    def clear(self) -> None:
        self._text.config(state="normal")
        self._text.delete("1.0", "end")
        self._text.insert("1.0", "暂无歌词")
        self._text.config(state="disabled")
