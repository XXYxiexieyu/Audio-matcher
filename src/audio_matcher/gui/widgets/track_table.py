"""Track table widget — displays scan results in a Treeview."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from audio_matcher.core.models import ProcessingStatus, TrackResult


class TrackTable(ttk.Frame):
    """Scrollable table of scanned tracks with match results."""

    COLUMNS = ("status", "filename", "title", "artist", "album", "confidence")
    COLUMN_LABELS = {
        "status": "Status",
        "filename": "File",
        "title": "Title",
        "artist": "Artist",
        "album": "Album",
        "confidence": "Conf",
    }
    COLUMN_WIDTHS = {
        "status": 50,
        "filename": 180,
        "title": 150,
        "artist": 120,
        "album": 120,
        "confidence": 60,
    }

    def __init__(self, parent, *, on_select: callable = None, **kwargs) -> None:
        super().__init__(parent, **kwargs)
        self._on_select_cb = on_select
        self._results: list[TrackResult] = []
        self._result_map: dict[str, TrackResult] = {}
        self._build()

    def _build(self) -> None:
        # Treeview.
        self._tree = ttk.Treeview(
            self, columns=self.COLUMNS, show="headings", selectmode="browse",
        )
        for col in self.COLUMNS:
            self._tree.heading(col, text=self.COLUMN_LABELS[col])
            self._tree.column(col, width=self.COLUMN_WIDTHS[col], anchor="w")

        # Scrollbar.
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=scrollbar.set)

        self._tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Bind selection.
        self._tree.bind("<<TreeviewSelect>>", self._on_select)

    def set_results(self, results: list[TrackResult]) -> None:
        """Replace all rows with *results*."""
        self._tree.delete(*self._tree.get_children())
        self._results = results
        self._result_map.clear()

        status_icons = {
            ProcessingStatus.TAGGED: "OK",
            ProcessingStatus.RECOGNIZED: "~",
            ProcessingStatus.LYRICS_FETCHED: "~",
            ProcessingStatus.ERROR: "ERR",
            ProcessingStatus.PENDING: "...",
            ProcessingStatus.FINGERPRINTED: "...",
        }

        for r in results:
            item_id = self._tree.insert("", "end", values=(
                status_icons.get(r.status, "?"),
                r.audio_file.path.name,
                r.match.title if r.match else "",
                r.match.artist if r.match else "",
                r.match.album if r.match else "",
                f"{r.match.confidence:.0%}" if r.match and r.match.confidence else "",
            ))
            self._result_map[item_id] = r

    def _on_select(self, event) -> None:
        selection = self._tree.selection()
        if selection and self._on_select_cb:
            item_id = selection[0]
            result = self._result_map.get(item_id)
            if result:
                self._on_select_cb(result)

    @property
    def selected_result(self) -> TrackResult | None:
        selection = self._tree.selection()
        if selection:
            return self._result_map.get(selection[0])
        return None
