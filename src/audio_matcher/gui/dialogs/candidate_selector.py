"""候选选择对话框 — 模糊匹配时展示多个候选让用户选择。"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Optional

import ttkbootstrap as tb
from ttkbootstrap.constants import *

from audio_matcher.core.models import MatchSource, TrackMatch


class CandidateSelectorDialog(tb.Toplevel):
    """模态对话框，显示模糊匹配候选列表供用户选择。

    使用方法::

        dialog = CandidateSelectorDialog(parent, candidates, filename)
        selected = dialog.selected_match  # TrackMatch or None
    """

    SOURCE_LABELS = {
        "acoustid": "AcoustID",
        "shazam": "Shazam",
        "musicbrainz": "MusicBrainz",
    }

    def __init__(
        self,
        parent,
        candidates: list[TrackMatch],
        filename: str,
    ) -> None:
        super().__init__(parent)
        self.title("选择匹配结果")
        self._result: Optional[TrackMatch] = None
        self._candidates = candidates

        self.transient(parent)
        self.grab_set()

        self._build(filename)

        # 居中
        self.update_idletasks()
        pw = parent.winfo_rootx() + parent.winfo_width() // 2
        py = parent.winfo_rooty() + parent.winfo_height() // 2
        x = max(0, pw - self.winfo_width() // 2)
        y = max(0, py - self.winfo_height() // 2)
        self.geometry(f"+{x}+{y}")

        self.wait_window()

    @property
    def selected_match(self) -> Optional[TrackMatch]:
        return self._result

    def _build(self, filename: str) -> None:
        # 标题说明
        header = ttk.Label(
            self,
            text=f"主识别失败，以下是备选匹配结果：\n{filename}",
            font=("", 11),
            wraplength=520,
        )
        header.pack(pady=(15, 10), padx=20)

        # Treeview
        columns = ("confidence", "title", "artist", "album", "source")
        self._tree = ttk.Treeview(
            self,
            columns=columns,
            show="headings",
            selectmode="browse",
            height=min(len(self._candidates), 10),
        )
        self._tree.heading("confidence", text="置信度")
        self._tree.heading("title", text="标题")
        self._tree.heading("artist", text="艺人")
        self._tree.heading("album", text="专辑")
        self._tree.heading("source", text="来源")
        self._tree.column("confidence", width=70, anchor="center")
        self._tree.column("title", width=180)
        self._tree.column("artist", width=130)
        self._tree.column("album", width=130)
        self._tree.column("source", width=90, anchor="center")
        self._tree.pack(fill="both", expand=True, padx=20, pady=5)

        # 填充数据
        for i, c in enumerate(self._candidates):
            self._tree.insert(
                "",
                "end",
                iid=str(i),
                values=(
                    f"{c.confidence:.0%}",
                    c.title,
                    c.artist,
                    c.album,
                    self.SOURCE_LABELS.get(c.source.value, c.source.value),
                ),
            )

        # 按钮
        btn_frame = ttk.Frame(self)
        btn_frame.pack(pady=(5, 15))

        ttk.Button(
            btn_frame, text="确认选择",
            command=self._on_confirm, bootstyle="success",
        ).pack(side="left", padx=5)

        ttk.Button(
            btn_frame, text="手动输入",
            command=self._on_manual, bootstyle="secondary",
        ).pack(side="left", padx=5)

        ttk.Button(
            btn_frame, text="跳过",
            command=self._on_skip, bootstyle="secondary",
        ).pack(side="left", padx=5)

        # 双击选择
        self._tree.bind("<Double-1>", lambda e: self._on_confirm())

        # 按 Enter 确认
        self.bind("<Return>", lambda e: self._on_confirm())
        self.bind("<Escape>", lambda e: self._on_skip())

    def _on_confirm(self) -> None:
        selection = self._tree.selection()
        if selection:
            idx = int(selection[0])
            self._result = self._candidates[idx]
        self.destroy()

    def _on_manual(self) -> None:
        dialog = _ManualEntryDialog(self)
        if dialog.result:
            self._result = dialog.result
        self.destroy()

    def _on_skip(self) -> None:
        self._result = None
        self.destroy()


class _ManualEntryDialog(tb.Toplevel):
    """手动输入标题/艺人的小对话框。"""

    def __init__(self, parent) -> None:
        super().__init__(parent)
        self.title("手动输入")
        self.result: Optional[TrackMatch] = None
        self.transient(parent)
        self.grab_set()

        self._build()
        self.wait_window()

    def _build(self) -> None:
        ttk.Label(self, text="标题：").grid(
            row=0, column=0, padx=10, pady=5, sticky="e"
        )
        self._title_var = tk.StringVar()
        ttk.Entry(self, textvariable=self._title_var, width=40).grid(
            row=0, column=1, padx=10, pady=5
        )

        ttk.Label(self, text="艺人：").grid(
            row=1, column=0, padx=10, pady=5, sticky="e"
        )
        self._artist_var = tk.StringVar()
        ttk.Entry(self, textvariable=self._artist_var, width=40).grid(
            row=1, column=1, padx=10, pady=5
        )

        btn_frame = ttk.Frame(self)
        btn_frame.grid(row=2, column=0, columnspan=2, pady=10)

        ttk.Button(
            btn_frame, text="确定", command=self._on_ok, bootstyle="success",
        ).pack(side="left", padx=5)
        ttk.Button(
            btn_frame, text="取消", command=self.destroy,
        ).pack(side="left", padx=5)

        self.bind("<Return>", lambda e: self._on_ok())

    def _on_ok(self) -> None:
        title = self._title_var.get().strip()
        artist = self._artist_var.get().strip()
        if title or artist:
            self.result = TrackMatch(
                title=title,
                artist=artist,
                source=MatchSource.SHAZAM,
                confidence=1.0,
            )
        self.destroy()
