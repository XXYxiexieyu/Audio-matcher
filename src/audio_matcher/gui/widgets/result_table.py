"""结果表格组件 — 现代化的扫描结果展示，支持排序、筛选、右键菜单。"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable, Optional

import ttkbootstrap as tb

from audio_matcher.core.models import ProcessingStatus, TrackResult
from audio_matcher.gui.styles import Colors, Fonts, Icons, Sizes, Spacing


class ResultTable(ttk.Frame):
    """扫描结果表格。

    功能：
    - 斑马纹行背景
    - 彩色状态指示
    - 列排序
    - 状态筛选 + 文本搜索
    - 右键菜单
    - 批量选择
    """

    COLUMNS = ("status", "filename", "title", "artist", "album", "confidence", "error")
    COLUMN_LABELS = {
        "status": "状态",
        "filename": "文件",
        "title": "标题",
        "artist": "艺人",
        "album": "专辑",
        "confidence": "置信度",
        "error": "错误",
    }
    COLUMN_WIDTHS = {
        "status": 60,
        "filename": 160,
        "title": 140,
        "artist": 120,
        "album": 120,
        "confidence": 70,
        "error": 100,
    }

    STATUS_DISPLAY = {
        ProcessingStatus.TAGGED: ("✓", Colors.SUCCESS, "已标记"),
        ProcessingStatus.RECOGNIZED: ("~", Colors.INFO, "已识别"),
        ProcessingStatus.LYRICS_FETCHED: ("~", Colors.INFO, "有歌词"),
        ProcessingStatus.AWAITING_SELECTION: ("?", Colors.WARNING, "待选择"),
        ProcessingStatus.ERROR: ("✗", Colors.ERROR, "失败"),
        ProcessingStatus.PENDING: ("…", Colors.TEXT_DISABLED, "等待"),
        ProcessingStatus.FINGERPRINTED: ("…", Colors.TEXT_DISABLED, "指纹"),
        ProcessingStatus.SCANNED: ("…", Colors.TEXT_DISABLED, "已扫描"),
    }

    def __init__(
        self,
        parent,
        *,
        on_select: Optional[Callable[[TrackResult], None]] = None,
        on_write: Optional[Callable[[TrackResult], None]] = None,
        on_retry: Optional[Callable[[TrackResult], None]] = None,
        on_skip: Optional[Callable[[TrackResult], None]] = None,
        **kwargs,
    ) -> None:
        super().__init__(parent, **kwargs)
        self._on_select_cb = on_select
        self._on_write_cb = on_write
        self._on_retry_cb = on_retry
        self._on_skip_cb = on_skip

        self._results: list[TrackResult] = []
        self._result_map: dict[str, TrackResult] = {}
        self._sort_column: Optional[str] = None
        self._sort_reverse = False
        self._filter_status: Optional[str] = None
        self._filter_text = ""

        self._build()

    # ── Build ──────────────────────────────────────────────────────────

    def _build(self) -> None:
        # 筛选栏
        filter_frame = ttk.Frame(self)
        filter_frame.pack(fill="x", padx=Spacing.SM, pady=(Spacing.SM, 0))

        # 状态筛选
        ttk.Label(
            filter_frame,
            text="筛选：",
            font=Fonts.SMALL,
            foreground=Colors.TEXT_SECONDARY,
        ).pack(side="left")

        self._filter_var = tk.StringVar(value="全部")
        filter_combo = ttk.Combobox(
            filter_frame,
            textvariable=self._filter_var,
            values=["全部", "已标记", "已识别", "有歌词", "待选择", "失败"],
            state="readonly",
            width=8,
        )
        filter_combo.pack(side="left", padx=(Spacing.XS, Spacing.MD))
        filter_combo.bind("<<ComboboxSelected>>", lambda e: self._apply_filter())

        # 搜索框
        ttk.Label(
            filter_frame,
            text="搜索：",
            font=Fonts.SMALL,
            foreground=Colors.TEXT_SECONDARY,
        ).pack(side="left")

        self._search_var = tk.StringVar()
        self._search_var.trace_add("write", lambda *a: self._apply_filter())
        search_entry = ttk.Entry(
            filter_frame,
            textvariable=self._search_var,
            width=20,
        )
        search_entry.pack(side="left", padx=Spacing.XS)

        # 批量操作按钮
        tb.Button(
            filter_frame,
            text="写入选中",
            command=self._write_selected,
            bootstyle="primary-outline",
        ).pack(side="right", padx=Spacing.XS)

        # 表格容器
        table_container = ttk.Frame(self)
        table_container.pack(fill="both", expand=True, padx=Spacing.SM, pady=Spacing.SM)

        # Treeview
        self._tree = ttk.Treeview(
            table_container,
            columns=self.COLUMNS,
            show="headings",
            selectmode="extended",  # 支持多选
        )

        for col in self.COLUMNS:
            self._tree.heading(
                col,
                text=self.COLUMN_LABELS[col],
                command=lambda c=col: self._sort_by(c),
            )
            self._tree.column(
                col,
                width=self.COLUMN_WIDTHS[col],
                anchor="w" if col != "status" else "center",
            )

        # 滚动条
        scrollbar = ttk.Scrollbar(
            table_container, orient="vertical", command=self._tree.yview
        )
        self._tree.configure(yscrollcommand=scrollbar.set)

        self._tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # 绑定事件
        self._tree.bind("<<TreeviewSelect>>", self._on_select)
        self._tree.bind("<Button-3>", self._on_right_click)  # 右键

        # 空状态标签
        self._empty_label = ttk.Label(
            table_container,
            text="暂无结果，请先扫描目录",
            font=Fonts.BODY,
            foreground=Colors.TEXT_DISABLED,
        )

        # 右键菜单
        self._context_menu = tk.Menu(self, tearoff=0)
        self._context_menu.add_command(label="写入标签", command=self._context_write)
        self._context_menu.add_command(label="强制重新识别", command=self._context_retry)
        self._context_menu.add_command(label="跳过此文件", command=self._context_skip)
        self._context_menu.add_separator()
        self._context_menu.add_command(label="查看错误详情", command=self._context_error)

        # 快捷键
        self._tree.bind("<Control-a>", lambda e: self._select_all())
        self._tree.bind("<Control-w>", lambda e: self._write_selected())

    # ── Data ───────────────────────────────────────────────────────────

    def set_results(self, results: list[TrackResult]) -> None:
        """设置结果列表。"""
        self._results = results
        self._refresh_table()

    def _refresh_table(self) -> None:
        """刷新表格显示。"""
        # 清空
        for item in self._tree.get_children():
            self._tree.delete(item)
        self._result_map.clear()

        if not self._results:
            self._empty_label.place(relx=0.5, rely=0.5, anchor="center")
            return

        self._empty_label.place_forget()

        # 筛选
        filtered = self._get_filtered_results()

        # 排序
        if self._sort_column:
            filtered = self._sort_results(filtered)

        # 填充
        for r in filtered:
            status_icon, status_color, status_text = self.STATUS_DISPLAY.get(
                r.status, ("?", Colors.TEXT_SECONDARY, "未知")
            )

            # 确定显示内容
            if r.match:
                title = r.match.title
                artist = r.match.artist
                album = r.match.album
                confidence = f"{r.match.confidence:.0%}" if r.match.confidence else ""
            elif r.match_alternatives:
                best = r.match_alternatives[0]
                title = f"? {best.title}"
                artist = f"? {best.artist}"
                album = best.album
                confidence = f"({len(r.match_alternatives)} 候选)"
            else:
                title = artist = album = confidence = ""

            error = (r.error or "")[:30] if r.error else ""

            # 斑马纹
            row_index = len(self._tree.get_children())
            tags = ("evenrow",) if row_index % 2 == 0 else ("oddrow",)

            # 状态颜色标签
            if r.status == ProcessingStatus.ERROR:
                tags += ("error",)
            elif r.status == ProcessingStatus.AWAITING_SELECTION:
                tags += ("warning",)
            elif r.status == ProcessingStatus.TAGGED:
                tags += ("success",)

            item_id = self._tree.insert(
                "",
                "end",
                values=(
                    status_icon,
                    r.audio_file.path.name,
                    title,
                    artist,
                    album,
                    confidence,
                    error,
                ),
                tags=tags,
            )
            self._result_map[item_id] = r

        # 配置标签样式
        self._tree.tag_configure("evenrow", background=Colors.TABLE_ROW_EVEN)
        self._tree.tag_configure("oddrow", background=Colors.TABLE_ROW_ODD)
        self._tree.tag_configure("error", foreground=Colors.ERROR)
        self._tree.tag_configure("warning", foreground=Colors.WARNING)
        self._tree.tag_configure("success", foreground=Colors.SUCCESS)

    def _get_filtered_results(self) -> list[TrackResult]:
        """获取筛选后的结果。"""
        filtered = self._results

        # 状态筛选
        status_filter = self._filter_var.get()
        if status_filter != "全部":
            status_map = {
                "已标记": ProcessingStatus.TAGGED,
                "已识别": ProcessingStatus.RECOGNIZED,
                "有歌词": ProcessingStatus.LYRICS_FETCHED,
                "待选择": ProcessingStatus.AWAITING_SELECTION,
                "失败": ProcessingStatus.ERROR,
            }
            target_status = status_map.get(status_filter)
            if target_status:
                filtered = [r for r in filtered if r.status == target_status]

        # 文本搜索
        search_text = self._search_var.get().lower()
        if search_text:
            filtered = [
                r for r in filtered
                if search_text in r.audio_file.path.name.lower()
                or (r.match and search_text in r.match.title.lower())
                or (r.match and search_text in r.match.artist.lower())
            ]

        return filtered

    def _sort_results(self, results: list[TrackResult]) -> list[TrackResult]:
        """排序结果。"""
        key_funcs = {
            "filename": lambda r: r.audio_file.path.name.lower(),
            "title": lambda r: (r.match.title if r.match else "").lower(),
            "artist": lambda r: (r.match.artist if r.match else "").lower(),
            "album": lambda r: (r.match.album if r.match else "").lower(),
            "confidence": lambda r: r.match.confidence if r.match else 0,
        }
        key_func = key_funcs.get(self._sort_column, key_funcs["filename"])
        return sorted(results, key=key_func, reverse=self._sort_reverse)

    def _sort_by(self, column: str) -> None:
        """按列排序。"""
        if self._sort_column == column:
            self._sort_reverse = not self._sort_reverse
        else:
            self._sort_column = column
            self._sort_reverse = False
        self._refresh_table()

    def _apply_filter(self) -> None:
        """应用筛选。"""
        self._refresh_table()

    # ── Selection ──────────────────────────────────────────────────────

    def _on_select(self, event) -> None:
        selection = self._tree.selection()
        if selection and self._on_select_cb:
            # 单选时触发回调
            if len(selection) == 1:
                item_id = selection[0]
                result = self._result_map.get(item_id)
                if result:
                    self._on_select_cb(result)

    def _select_all(self) -> None:
        """全选。"""
        for item in self._tree.get_children():
            self._tree.selection_add(item)

    def get_selected_results(self) -> list[TrackResult]:
        """获取选中的结果。"""
        selection = self._tree.selection()
        return [self._result_map[item] for item in selection if item in self._result_map]

    @property
    def selected_result(self) -> Optional[TrackResult]:
        selection = self._tree.selection()
        if len(selection) == 1:
            return self._result_map.get(selection[0])
        return None

    @property
    def results(self) -> list[TrackResult]:
        return self._results

    # ── Context Menu ───────────────────────────────────────────────────

    def _on_right_click(self, event) -> None:
        """右键点击。"""
        item = self._tree.identify_row(event.y)
        if item:
            if item not in self._tree.selection():
                self._tree.selection_set(item)
            self._context_menu.post(event.x_root, event.y_root)

    def _context_write(self) -> None:
        selected = self.get_selected_results()
        for result in selected:
            if self._on_write_cb:
                self._on_write_cb(result)

    def _context_retry(self) -> None:
        selected = self.get_selected_results()
        for result in selected:
            if self._on_retry_cb:
                self._on_retry_cb(result)

    def _context_skip(self) -> None:
        selected = self.get_selected_results()
        for result in selected:
            if self._on_skip_cb:
                self._on_skip_cb(result)

    def _context_error(self) -> None:
        result = self.selected_result
        if result and result.error:
            from tkinter import messagebox
            messagebox.showinfo("错误详情", f"文件：{result.audio_file.path.name}\n\n错误：{result.error}")

    def _write_selected(self) -> None:
        """写入选中项标签。"""
        selected = self.get_selected_results()
        for result in selected:
            if result.match and self._on_write_cb:
                self._on_write_cb(result)
