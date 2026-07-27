"""Folder selector sidebar widget."""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, ttk


class FolderSelector(ttk.Frame):
    """Sidebar widget for browsing and selecting a music directory."""

    def __init__(self, parent, *, on_scan: callable = None, **kwargs) -> None:
        super().__init__(parent, **kwargs)
        self._on_scan = on_scan
        self._selected_path: Path | None = None
        self._build()

    def _build(self) -> None:
        # Header.
        header = ttk.Label(self, text="Music Folder", font=("", 11, "bold"))
        header.pack(pady=(5, 10))

        # Path display.
        self._path_var = tk.StringVar(value="No folder selected")
        path_label = ttk.Label(self, textvariable=self._path_var, wraplength=200)
        path_label.pack(pady=(0, 10))

        # Browse button.
        btn_browse = ttk.Button(self, text="Browse...", command=self._on_browse)
        btn_browse.pack(pady=(0, 5))

        # Scan button.
        self._btn_scan = ttk.Button(
            self, text="Scan & Identify",
            command=self._on_scan_clicked,
            state="disabled",
        )
        self._btn_scan.pack(pady=(5, 10))

        # Separator.
        ttk.Separator(self, orient="horizontal").pack(fill="x", pady=10)

        # Options.
        self._recursive_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            self, text="Recursive", variable=self._recursive_var,
        ).pack(anchor="w", padx=10)

        self._dry_run_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            self, text="Dry Run (preview only)", variable=self._dry_run_var,
        ).pack(anchor="w", padx=10)

    def _on_browse(self) -> None:
        path_str = filedialog.askdirectory(title="Select Music Folder")
        if path_str:
            self._selected_path = Path(path_str)
            self._path_var.set(str(self._selected_path))
            self._btn_scan.config(state="normal")

    def _on_scan_clicked(self) -> None:
        if self._on_scan and self._selected_path:
            self._on_scan(
                self._selected_path,
                recursive=self._recursive_var.get(),
                dry_run=self._dry_run_var.get(),
            )

    @property
    def selected_path(self) -> Path | None:
        return self._selected_path
