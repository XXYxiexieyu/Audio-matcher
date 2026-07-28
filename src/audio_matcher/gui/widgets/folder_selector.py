"""文件夹选择器侧边栏控件。

v0.0.5: 新增文件列表（复选框 + 全选/全不选）+ 歌词语言下拉框。
"""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, ttk
from typing import Optional

from audio_matcher.core.models import AudioFile


# Chinese display → enum value mapping for the language dropdown.
_LANG_DISPLAY = {
    "仅外语": "original_only",
    "双语": "bilingual",
    "日语+罗马音": "japanese_romaji",
    "双语+罗马音": "bilingual_romaji",
}
_LANG_LABELS = list(_LANG_DISPLAY.keys())
_DEFAULT_LANG_LABEL = "仅外语"


class FolderSelector(ttk.Frame):
    """侧边栏控件：浏览并选择音乐目录。

    Callbacks
    --------
    on_scan(path, files, language, dry_run, rename_files)
        用户点击「扫描识别」时调用。*files* 是选中的 :class:`AudioFile` 列表。
    on_restore(path)
        用户点击「恢复原始文件名」时调用。
    """

    def __init__(
        self,
        parent,
        *,
        on_scan: callable = None,
        on_restore: callable = None,
        **kwargs,
    ) -> None:
        super().__init__(parent, **kwargs)
        self._on_scan = on_scan
        self._on_restore_cb = on_restore
        self._selected_path: Path | None = None
        self._audio_files: list[AudioFile] = []
        self._file_vars: dict[str, tk.BooleanVar] = {}
        self._build()

    # ── Build ──────────────────────────────────────────────────────────

    def _build(self) -> None:
        # Header.
        header = ttk.Label(self, text="音乐目录", font=("", 11, "bold"))
        header.pack(pady=(5, 10))

        # Path display.
        self._path_var = tk.StringVar(value="未选择目录")
        path_label = ttk.Label(self, textvariable=self._path_var, wraplength=200)
        path_label.pack(pady=(0, 10))

        # Browse button.
        btn_browse = ttk.Button(self, text="浏览...", command=self._on_browse)
        btn_browse.pack(pady=(0, 5))

        # Scan button.
        self._btn_scan = ttk.Button(
            self, text="扫描识别",
            command=self._on_scan_clicked,
            state="disabled",
        )
        self._btn_scan.pack(pady=(5, 10))

        # Separator.
        ttk.Separator(self, orient="horizontal").pack(fill="x", pady=8)

        # ── File list section ──────────────────────────────────────────
        file_section = ttk.Frame(self)
        file_section.pack(fill="both", expand=True, padx=2)

        # Select-all / deselect-all buttons.
        btn_row = ttk.Frame(file_section)
        btn_row.pack(fill="x", pady=(0, 5))

        self._btn_all = ttk.Button(btn_row, text="全选", command=self._select_all)
        self._btn_all.pack(side="left", padx=(0, 5))

        self._btn_none = ttk.Button(btn_row, text="全不选", command=self._deselect_all)
        self._btn_none.pack(side="left")

        # Scrollable file list (Canvas + inner Frame + Checkbuttons).
        self._file_canvas = tk.Canvas(file_section, height=150, highlightthickness=0)
        self._file_canvas.pack(side="left", fill="both", expand=True)

        self._file_scrollbar = ttk.Scrollbar(
            file_section, orient="vertical", command=self._file_canvas.yview,
        )
        self._file_scrollbar.pack(side="right", fill="y")
        self._file_canvas.configure(yscrollcommand=self._file_scrollbar.set)

        self._file_frame = ttk.Frame(self._file_canvas)
        self._file_frame_id = self._file_canvas.create_window(
            (0, 0), window=self._file_frame, anchor="nw", tags="inner",
        )
        self._file_frame.bind("<Configure>", self._on_inner_configure)
        self._file_canvas.bind("<Configure>", self._on_canvas_configure)

        # ── End file list section ──

        # Separator.
        ttk.Separator(self, orient="horizontal").pack(fill="x", pady=8)

        # ── Options ────────────────────────────────────────────────────
        opt_frame = ttk.Frame(self)
        opt_frame.pack(fill="x", padx=5)

        import ttkbootstrap as tb

        # Recursive.
        self._recursive_var = tk.BooleanVar(value=True)
        cb1 = tb.Checkbutton(
            opt_frame, text="递归子目录",
            variable=self._recursive_var,
            bootstyle="round-toggle",
        )
        cb1.pack(anchor="w", pady=2)

        # Rename.
        self._rename_var = tk.BooleanVar(value=True)
        cb2 = tb.Checkbutton(
            opt_frame, text="重命名为 歌名 - 艺人",
            variable=self._rename_var,
            bootstyle="round-toggle",
        )
        cb2.pack(anchor="w", pady=2)

        # Dry run.
        self._dry_run_var = tk.BooleanVar(value=False)
        cb3 = tb.Checkbutton(
            opt_frame, text="仅预览（不写入）",
            variable=self._dry_run_var,
            bootstyle="round-toggle",
        )
        cb3.pack(anchor="w", pady=2)

        # Lyrics language dropdown.
        lang_frame = ttk.Frame(opt_frame)
        lang_frame.pack(fill="x", pady=(8, 2))

        ttk.Label(lang_frame, text="歌词语言：").pack(side="left")

        self._lang_var = tk.StringVar(value=_DEFAULT_LANG_LABEL)
        self._lang_combo = ttk.Combobox(
            lang_frame,
            textvariable=self._lang_var,
            values=_LANG_LABELS,
            state="readonly",
            width=11,
        )
        self._lang_combo.pack(side="left", padx=(5, 0))

        # Restore button.
        btn_restore = tb.Button(
            opt_frame, text="恢复原始文件名",
            command=self._on_restore,
            bootstyle="warning-outline",
        )
        btn_restore.pack(anchor="w", pady=(10, 0))

    # ── File list internal helpers ─────────────────────────────────────

    def _on_inner_configure(self, event) -> None:
        """Update scrollregion when the inner frame resizes."""
        self._file_canvas.configure(scrollregion=self._file_canvas.bbox("all"))

    def _on_canvas_configure(self, event) -> None:
        """Keep inner frame width synced with the canvas."""
        self._file_canvas.itemconfig(self._file_frame_id, width=event.width)

    def _refresh_file_list(self) -> None:
        """Re-scan the selected directory and rebuild the checkbox list."""
        # Clear existing widgets.
        for child in self._file_frame.winfo_children():
            child.destroy()
        self._file_vars.clear()
        self._audio_files.clear()

        if self._selected_path is None:
            return

        # Scan directory.
        from audio_matcher.core.scanner import AudioScanner
        from audio_matcher.core.config import Config

        scanner = AudioScanner(Config())
        try:
            self._audio_files = scanner.scan(
                self._selected_path,
                recursive=self._recursive_var.get(),
            )
        except Exception:
            self._audio_files = []

        if not self._audio_files:
            self._no_files_label = ttk.Label(
                self._file_frame, text="未找到音频文件", foreground="grey",
            )
            self._no_files_label.pack(pady=5)
            self._btn_scan.config(state="disabled")
            return

        self._btn_scan.config(state="normal")

        # Create a Checkbutton per file (default: checked).
        for af in sorted(self._audio_files, key=lambda f: f.path.name.lower()):
            var = tk.BooleanVar(value=True)
            self._file_vars[af.id] = var

            cb = ttk.Checkbutton(
                self._file_frame,
                text=f" {af.path.name}",
                variable=var,
            )
            cb.pack(anchor="w", padx=5, pady=1)

        self._file_canvas.yview_moveto(0)

    def _select_all(self) -> None:
        for var in self._file_vars.values():
            var.set(True)

    def _deselect_all(self) -> None:
        for var in self._file_vars.values():
            var.set(False)

    # ── Events ─────────────────────────────────────────────────────────

    def _on_browse(self) -> None:
        path_str = filedialog.askdirectory(title="选择音乐目录")
        if path_str:
            self._selected_path = Path(path_str)
            self._path_var.set(str(self._selected_path))
            self._btn_scan.config(state="disabled")
            self._refresh_file_list()

    def _on_scan_clicked(self) -> None:
        if self._on_scan is None or self._selected_path is None:
            return

        # Filter to checked files only.
        selected = [
            af for af in self._audio_files
            if self._file_vars.get(af.id, tk.BooleanVar(value=False)).get()
        ]

        if not selected:
            self._btn_scan.config(state="disabled")
            return

        # Map Chinese label → enum value.
        lang_label = self._lang_var.get()
        language = _LANG_DISPLAY.get(lang_label, "original_only")

        self._on_scan(
            self._selected_path,
            selected,
            language,
            self._dry_run_var.get(),
            self._rename_var.get(),
        )

    def _on_restore(self) -> None:
        if self._on_restore_cb and self._selected_path:
            self._on_restore_cb(self._selected_path)

    @property
    def selected_path(self) -> Path | None:
        return self._selected_path
