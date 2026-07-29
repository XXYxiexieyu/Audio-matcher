"""候选选择对话框 — 现代化的模糊匹配候选选择。"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Optional

import ttkbootstrap as tb

from audio_matcher.core.models import MatchSource, TrackMatch
from audio_matcher.gui.styles import Colors, Fonts, Icons, Sizes, Spacing


class CandidateSelectorDialog(tb.Toplevel):
    """候选选择对话框。

    功能：
    - 显示候选列表（置信度条形图）
    - 来源徽章
    - 预览选中候选详情
    - 确认/手动输入/跳过
    """

    SOURCE_LABELS = {
        "acoustid": ("AcoustID", Colors.INFO),
        "shazam": ("Shazam", Colors.PRIMARY),
        "musicbrainz": ("MusicBrainz", Colors.SUCCESS),
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
        self._selected_index: Optional[int] = None

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

    # ── Build ──────────────────────────────────────────────────────────

    def _build(self, filename: str) -> None:
        # 主容器
        main = tb.Frame(self, padding=Spacing.LG)
        main.pack(fill="both", expand=True)

        # 标题
        header = ttk.Label(
            main,
            text="主识别失败，请选择正确的匹配结果",
            font=Fonts.H2,
            foreground=Colors.TEXT_PRIMARY,
        )
        header.pack(anchor="w", pady=(0, Spacing.XS))

        # 文件名
        ttk.Label(
            main,
            text=f"文件：{filename}",
            font=Fonts.SMALL,
            foreground=Colors.TEXT_SECONDARY,
        ).pack(anchor="w", pady=(0, Spacing.MD))

        # 候选列表
        list_frame = ttk.Frame(main)
        list_frame.pack(fill="both", expand=True, pady=(0, Spacing.MD))

        # 创建候选卡片
        self._candidate_frames: list[tk.Frame] = []
        for i, candidate in enumerate(self._candidates):
            frame = self._create_candidate_card(list_frame, candidate, i)
            frame.pack(fill="x", pady=Spacing.XS)
            self._candidate_frames.append(frame)

        # 默认选中第一个
        if self._candidates:
            self._select_candidate(0)

        # 按钮
        btn_frame = ttk.Frame(main)
        btn_frame.pack(fill="x", pady=(Spacing.MD, 0))

        tb.Button(
            btn_frame,
            text=f"{Icons.SUCCESS} 确认选择",
            command=self._on_confirm,
            bootstyle="success",
            width=15,
        ).pack(side="left", padx=(0, Spacing.SM))

        tb.Button(
            btn_frame,
            text=f"{Icons.EDIT} 手动输入",
            command=self._on_manual,
            bootstyle="secondary-outline",
            width=15,
        ).pack(side="left", padx=Spacing.SM)

        tb.Button(
            btn_frame,
            text="跳过",
            command=self._on_skip,
            bootstyle="secondary-outline",
            width=15,
        ).pack(side="left", padx=Spacing.SM)

        # 提示
        ttk.Label(
            main,
            text="选择后将自动获取歌词并写入标签",
            font=Fonts.SMALL,
            foreground=Colors.TEXT_SECONDARY,
        ).pack(anchor="w", pady=(Spacing.MD, 0))

        # 快捷键
        self.bind("<Return>", lambda e: self._on_confirm())
        self.bind("<Escape>", lambda e: self._on_skip())
        self.bind("<Up>", lambda e: self._navigate(-1))
        self.bind("<Down>", lambda e: self._navigate(1))

    def _create_candidate_card(
        self, parent, candidate: TrackMatch, index: int
    ) -> tk.Frame:
        """创建候选卡片。"""
        # 卡片框架
        card = tk.Frame(
            parent,
            bg=Colors.BG_CARD,
            padx=Spacing.MD,
            pady=Spacing.SM,
            cursor="hand2",
        )

        # 绑定点击
        card.bind("<Button-1>", lambda e, i=index: self._select_candidate(i))

        # 左侧：置信度条形图
        conf_frame = tk.Frame(card, bg=Colors.BG_CARD, width=60)
        conf_frame.pack(side="left", fill="y", padx=(0, Spacing.MD))
        conf_frame.pack_propagate(False)

        # 置信度百分比
        conf_pct = candidate.confidence
        conf_label = tk.Label(
            conf_frame,
            text=f"{conf_pct:.0%}",
            font=Fonts.H3,
            fg=Colors.PRIMARY,
            bg=Colors.BG_CARD,
        )
        conf_label.pack(pady=(Spacing.SM, 0))

        # 置信度条
        conf_bar_bg = tk.Frame(conf_frame, bg=Colors.BORDER, height=4, width=50)
        conf_bar_bg.pack(pady=Spacing.XS)
        conf_bar_bg.pack_propagate(False)

        conf_bar_fill = tk.Frame(
            conf_bar_bg,
            bg=Colors.PRIMARY,
            height=4,
            width=int(50 * conf_pct),
        )
        conf_bar_fill.place(x=0, y=0)

        # 中间：信息
        info_frame = tk.Frame(card, bg=Colors.BG_CARD)
        info_frame.pack(side="left", fill="both", expand=True)

        # 标题
        title_label = tk.Label(
            info_frame,
            text=candidate.title or "未知标题",
            font=Fonts.BODY_BOLD,
            fg=Colors.TEXT_PRIMARY,
            bg=Colors.BG_CARD,
            anchor="w",
        )
        title_label.pack(fill="x")

        # 艺人 + 专辑
        artist_text = candidate.artist or "未知艺人"
        if candidate.album:
            artist_text += f" · {candidate.album}"
        if candidate.year:
            artist_text += f" ({candidate.year})"

        artist_label = tk.Label(
            info_frame,
            text=artist_text,
            font=Fonts.BODY,
            fg=Colors.TEXT_SECONDARY,
            bg=Colors.BG_CARD,
            anchor="w",
        )
        artist_label.pack(fill="x")

        # 右侧：来源徽章
        source_label, source_color = self.SOURCE_LABELS.get(
            candidate.source.value, (candidate.source.value, Colors.TEXT_SECONDARY)
        )
        source_badge = tk.Label(
            card,
            text=source_label,
            font=Fonts.SMALL,
            fg=source_color,
            bg=Colors.BG_CARD,
            padx=Spacing.SM,
            pady=Spacing.XS,
        )
        source_badge.pack(side="right")

        # 存储索引
        card._candidate_index = index

        return card

    def _select_candidate(self, index: int) -> None:
        """选中候选。"""
        self._selected_index = index

        # 更新所有卡片样式
        for i, frame in enumerate(self._candidate_frames):
            if i == index:
                frame.configure(bg=Colors.BG_SELECTED)
                for child in frame.winfo_children():
                    if isinstance(child, tk.Frame):
                        child.configure(bg=Colors.BG_SELECTED)
                        for grandchild in child.winfo_children():
                            if isinstance(grandchild, tk.Label):
                                grandchild.configure(bg=Colors.BG_SELECTED)
                    elif isinstance(child, tk.Label):
                        child.configure(bg=Colors.BG_SELECTED)
            else:
                frame.configure(bg=Colors.BG_CARD)
                for child in frame.winfo_children():
                    if isinstance(child, tk.Frame):
                        child.configure(bg=Colors.BG_CARD)
                        for grandchild in child.winfo_children():
                            if isinstance(grandchild, tk.Label):
                                grandchild.configure(bg=Colors.BG_CARD)
                    elif isinstance(child, tk.Label):
                        child.configure(bg=Colors.BG_CARD)

    def _navigate(self, delta: int) -> None:
        """键盘导航。"""
        if not self._candidates:
            return
        new_index = (self._selected_index or 0) + delta
        new_index = max(0, min(new_index, len(self._candidates) - 1))
        self._select_candidate(new_index)

    # ── Actions ────────────────────────────────────────────────────────

    def _on_confirm(self) -> None:
        """确认选择。"""
        if self._selected_index is not None:
            self._result = self._candidates[self._selected_index]
        self.destroy()

    def _on_manual(self) -> None:
        """手动输入。"""
        dialog = ManualEntryDialog(self)
        if dialog.result:
            self._result = dialog.result
        self.destroy()

    def _on_skip(self) -> None:
        """跳过。"""
        self._result = None
        self.destroy()


class ManualEntryDialog(tb.Toplevel):
    """手动输入对话框。"""

    def __init__(self, parent) -> None:
        super().__init__(parent)
        self.title("手动输入")
        self.result: Optional[TrackMatch] = None
        self.transient(parent)
        self.grab_set()

        self._build()
        self.wait_window()

    def _build(self) -> None:
        main = tb.Frame(self, padding=Spacing.LG)
        main.pack(fill="both", expand=True)

        # 标题
        ttk.Label(
            main,
            text="手动输入歌曲信息",
            font=Fonts.H3,
            foreground=Colors.TEXT_PRIMARY,
        ).pack(anchor="w", pady=(0, Spacing.MD))

        # 标题输入
        ttk.Label(
            main,
            text="标题：",
            font=Fonts.BODY,
            foreground=Colors.TEXT_SECONDARY,
        ).pack(anchor="w", pady=(Spacing.XS, 0))

        self._title_var = tk.StringVar()
        title_entry = ttk.Entry(main, textvariable=self._title_var, width=40)
        title_entry.pack(fill="x", pady=(Spacing.XS, Spacing.SM))
        title_entry.focus()

        # 艺人输入
        ttk.Label(
            main,
            text="艺人：",
            font=Fonts.BODY,
            foreground=Colors.TEXT_SECONDARY,
        ).pack(anchor="w", pady=(Spacing.SM, 0))

        self._artist_var = tk.StringVar()
        ttk.Entry(main, textvariable=self._artist_var, width=40).pack(
            fill="x", pady=(Spacing.XS, Spacing.MD)
        )

        # 按钮
        btn_frame = ttk.Frame(main)
        btn_frame.pack(fill="x")

        tb.Button(
            btn_frame,
            text="确定",
            command=self._on_ok,
            bootstyle="success",
            width=12,
        ).pack(side="left", padx=(0, Spacing.SM))

        tb.Button(
            btn_frame,
            text="取消",
            command=self.destroy,
            bootstyle="secondary-outline",
            width=12,
        ).pack(side="left")

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
