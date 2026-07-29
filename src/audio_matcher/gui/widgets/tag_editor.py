"""标签编辑器控件 — 手动编辑识别到的元数据。"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from audio_matcher.core.models import MatchSource, TrackMatch, TrackResult


class TagEditor(ttk.Frame):
    """元数据编辑表单（标题、艺人、专辑、年份、轨号、歌词）。"""

    FIELDS = [
        ("title", "标题"),
        ("artist", "艺人"),
        ("album", "专辑"),
        ("year", "年份"),
        ("track_number", "轨号"),
    ]

    def __init__(self, parent, *, on_write: callable = None, **kwargs) -> None:
        super().__init__(parent, **kwargs)
        self._on_write = on_write
        self._current_result: TrackResult | None = None
        self._entries: dict[str, tk.StringVar] = {}
        self._lyrics_text: tk.Text | None = None
        self._build()

    def _build(self) -> None:
        # 标题
        header = ttk.Label(self, text="标签编辑器", font=("", 11, "bold"))
        header.grid(row=0, column=0, columnspan=2, sticky="w", pady=(5, 10))

        # 可编辑字段
        for i, (key, label) in enumerate(self.FIELDS):
            ttk.Label(self, text=f"{label}：").grid(
                row=i + 1, column=0, sticky="e", padx=(5, 5), pady=2,
            )
            var = tk.StringVar()
            entry = ttk.Entry(self, textvariable=var, width=30)
            entry.grid(row=i + 1, column=1, sticky="ew", padx=(0, 10), pady=2)
            self._entries[key] = var

        # 歌词
        ttk.Label(self, text="歌词：").grid(
            row=len(self.FIELDS) + 1, column=0, sticky="ne", padx=(5, 5), pady=(10, 2),
        )
        self._lyrics_text = tk.Text(self, width=35, height=8, wrap="word")
        self._lyrics_text.grid(
            row=len(self.FIELDS) + 1, column=1, sticky="ew", padx=(0, 10), pady=(10, 2),
        )

        # 按钮
        btn_frame = ttk.Frame(self)
        btn_frame.grid(row=len(self.FIELDS) + 2, column=0, columnspan=2, pady=10)

        ttk.Button(btn_frame, text="写入标签", command=self._on_write_clicked).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="还原", command=self._revert).pack(side="left", padx=5)

        self.grid_columnconfigure(1, weight=1)

    def load(self, result: TrackResult) -> None:
        """用 TrackResult 填充编辑器。"""
        self._current_result = result
        # Prefer confirmed match; fall back to best alternative for preview.
        effective = result.match
        if not effective and result.match_alternatives:
            effective = result.match_alternatives[0]
        if effective:
            self._entries["title"].set(effective.title or "")
            self._entries["artist"].set(effective.artist or "")
            self._entries["album"].set(effective.album or "")
            self._entries["year"].set(str(effective.year) if effective.year else "")
            self._entries["track_number"].set(
                str(effective.track_number) if effective.track_number else ""
            )
        if self._lyrics_text:
            self._lyrics_text.delete("1.0", "end")
            if result.lyrics:
                self._lyrics_text.insert("1.0", result.lyrics.raw_lrc)

    def _revert(self) -> None:
        if self._current_result:
            self.load(self._current_result)

    def _on_write_clicked(self) -> None:
        if not self._current_result:
            return
        # If no match yet (e.g. AWAITING_SELECTION with manual edits),
        # create one from the editor fields.
        if not self._current_result.match:
            self._current_result.match = TrackMatch(source=MatchSource.SHAZAM)
        self._current_result.match.title = self._entries["title"].get()
        self._current_result.match.artist = self._entries["artist"].get()
        self._current_result.match.album = self._entries["album"].get()
        try:
            self._current_result.match.year = int(self._entries["year"].get())
        except (ValueError, TypeError):
            self._current_result.match.year = None
        try:
            self._current_result.match.track_number = int(self._entries["track_number"].get())
        except (ValueError, TypeError):
            self._current_result.match.track_number = None
        self._current_result.edited = True
        if self._on_write:
            self._on_write(self._current_result)
