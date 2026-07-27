"""Tag editor widget — manual editing of matched metadata."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from audio_matcher.core.models import TrackResult


class TagEditor(ttk.Frame):
    """Editable form for track metadata (TITLE, ARTIST, ALBUM, YEAR, TRACK, LYRICS)."""

    FIELDS = [
        ("title", "Title"),
        ("artist", "Artist"),
        ("album", "Album"),
        ("year", "Year"),
        ("track_number", "Track #"),
    ]

    def __init__(self, parent, *, on_write: callable = None, **kwargs) -> None:
        super().__init__(parent, **kwargs)
        self._on_write = on_write
        self._current_result: TrackResult | None = None
        self._entries: dict[str, tk.StringVar] = {}
        self._lyrics_text: tk.Text | None = None
        self._build()

    def _build(self) -> None:
        # Header.
        header = ttk.Label(self, text="Tag Editor", font=("", 11, "bold"))
        header.grid(row=0, column=0, columnspan=2, sticky="w", pady=(5, 10))

        # Editable fields.
        for i, (key, label) in enumerate(self.FIELDS):
            ttk.Label(self, text=f"{label}:").grid(
                row=i + 1, column=0, sticky="e", padx=(5, 5), pady=2,
            )
            var = tk.StringVar()
            entry = ttk.Entry(self, textvariable=var, width=30)
            entry.grid(row=i + 1, column=1, sticky="ew", padx=(0, 10), pady=2)
            self._entries[key] = var

        # Lyrics.
        ttk.Label(self, text="Lyrics:").grid(
            row=len(self.FIELDS) + 1, column=0, sticky="ne", padx=(5, 5), pady=(10, 2),
        )
        self._lyrics_text = tk.Text(self, width=35, height=8, wrap="word")
        self._lyrics_text.grid(
            row=len(self.FIELDS) + 1, column=1, sticky="ew", padx=(0, 10), pady=(10, 2),
        )

        # Buttons.
        btn_frame = ttk.Frame(self)
        btn_frame.grid(row=len(self.FIELDS) + 2, column=0, columnspan=2, pady=10)

        ttk.Button(btn_frame, text="Write Tags", command=self._on_write_clicked).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Revert", command=self._revert).pack(side="left", padx=5)

        self.grid_columnconfigure(1, weight=1)

    def load(self, result: TrackResult) -> None:
        """Populate the editor with a TrackResult."""
        self._current_result = result
        if result.match:
            self._entries["title"].set(result.match.title or "")
            self._entries["artist"].set(result.match.artist or "")
            self._entries["album"].set(result.match.album or "")
            self._entries["year"].set(str(result.match.year) if result.match.year else "")
            self._entries["track_number"].set(str(result.match.track_number) if result.match.track_number else "")
        if self._lyrics_text:
            self._lyrics_text.delete("1.0", "end")
            if result.lyrics:
                self._lyrics_text.insert("1.0", result.lyrics.raw_lrc)

    def _revert(self) -> None:
        if self._current_result:
            self.load(self._current_result)

    def _on_write_clicked(self) -> None:
        if self._current_result and self._current_result.match:
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
