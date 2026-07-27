"""Lyrics viewer widget — displays synced lyrics with timestamps."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk


class LyricsViewer(ttk.Frame):
    """Scrollable synced lyrics display."""

    def __init__(self, parent, **kwargs) -> None:
        super().__init__(parent, **kwargs)
        self._build()

    def _build(self) -> None:
        header = ttk.Label(self, text="Lyrics Preview", font=("", 11, "bold"))
        header.pack(pady=(5, 5))

        self._text = tk.Text(self, wrap="word", state="disabled", height=12)
        self._text.pack(fill="both", expand=True, padx=5, pady=5)

    def set_lyrics(self, raw_lrc: str) -> None:
        """Display raw LRC text."""
        self._text.config(state="normal")
        self._text.delete("1.0", "end")
        if raw_lrc:
            self._text.insert("1.0", raw_lrc)
        else:
            self._text.insert("1.0", "No lyrics available")
        self._text.config(state="disabled")

    def clear(self) -> None:
        self.set_lyrics("")
