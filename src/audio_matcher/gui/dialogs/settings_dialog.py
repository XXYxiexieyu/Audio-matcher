"""设置对话框 — 配置管理界面。"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Optional

import ttkbootstrap as tb

from audio_matcher.core.config import Config
from audio_matcher.gui.styles import Colors, Fonts, Icons, Spacing


class SettingsDialog(tb.Toplevel):
    """设置对话框。

    功能：
    - 选项卡布局：常规/识别/歌词/性能/扫描
    - 配置编辑和保存
    """

    def __init__(self, parent, config: Config) -> None:
        super().__init__(parent)
        self.title("设置")
        self._config = config
        self._original_config = Config.load()  # 用于取消时恢复
        self._result = False  # 是否保存了更改

        self.transient(parent)
        self.grab_set()

        self._build()

        # 居中
        self.update_idletasks()
        pw = parent.winfo_rootx() + parent.winfo_width() // 2
        py = parent.winfo_rooty() + parent.winfo_height() // 2
        x = max(0, pw - self.winfo_width() // 2)
        y = max(0, py - self.winfo_height() // 2)
        self.geometry(f"600x500+{x}+{y}")

        self.wait_window()

    @property
    def saved(self) -> bool:
        return self._result

    # ── Build ──────────────────────────────────────────────────────────

    def _build(self) -> None:
        # 主容器
        main = tb.Frame(self, padding=Spacing.LG)
        main.pack(fill="both", expand=True)

        # 标题
        ttk.Label(
            main,
            text=f"{Icons.SETTINGS} 设置",
            font=Fonts.H2,
            foreground=Colors.TEXT_PRIMARY,
        ).pack(anchor="w", pady=(0, Spacing.MD))

        # 选项卡
        notebook = ttk.Notebook(main)
        notebook.pack(fill="both", expand=True, pady=(0, Spacing.MD))

        # 常规选项卡
        general_frame = ttk.Frame(notebook, padding=Spacing.MD)
        notebook.add(general_frame, text=" 常规 ")
        self._build_general_tab(general_frame)

        # 识别选项卡
        recognition_frame = ttk.Frame(notebook, padding=Spacing.MD)
        notebook.add(recognition_frame, text=" 识别 ")
        self._build_recognition_tab(recognition_frame)

        # 歌词选项卡
        lyrics_frame = ttk.Frame(notebook, padding=Spacing.MD)
        notebook.add(lyrics_frame, text=" 歌词 ")
        self._build_lyrics_tab(lyrics_frame)

        # 性能选项卡
        performance_frame = ttk.Frame(notebook, padding=Spacing.MD)
        notebook.add(performance_frame, text=" 性能 ")
        self._build_performance_tab(performance_frame)

        # 扫描选项卡
        scan_frame = ttk.Frame(notebook, padding=Spacing.MD)
        notebook.add(scan_frame, text=" 扫描 ")
        self._build_scan_tab(scan_frame)

        # 按钮
        btn_frame = ttk.Frame(main)
        btn_frame.pack(fill="x")

        tb.Button(
            btn_frame,
            text="保存",
            command=self._on_save,
            bootstyle="success",
            width=12,
        ).pack(side="left", padx=(0, Spacing.SM))

        tb.Button(
            btn_frame,
            text="取消",
            command=self._on_cancel,
            bootstyle="secondary-outline",
            width=12,
        ).pack(side="left", padx=Spacing.SM)

        tb.Button(
            btn_frame,
            text="恢复默认",
            command=self._on_reset,
            bootstyle="warning-outline",
            width=12,
        ).pack(side="right")

    def _build_general_tab(self, parent) -> None:
        """常规选项卡。"""
        # 覆盖标签
        self._overwrite_var = tk.BooleanVar(value=self._config.overwrite_tags)
        tb.Checkbutton(
            parent,
            text="覆盖现有标签",
            variable=self._overwrite_var,
            bootstyle="round-toggle",
        ).pack(anchor="w", pady=Spacing.XS)

        # 备份原始文件
        self._backup_var = tk.BooleanVar(value=self._config.backup_original)
        tb.Checkbutton(
            parent,
            text="写入前备份原始文件",
            variable=self._backup_var,
            bootstyle="round-toggle",
        ).pack(anchor="w", pady=Spacing.XS)

        # LRC sidecar
        self._lrc_sidecar_var = tk.BooleanVar(value=self._config.write_lrc_sidecar)
        tb.Checkbutton(
            parent,
            text="生成 .lrc 歌词文件",
            variable=self._lrc_sidecar_var,
            bootstyle="round-toggle",
        ).pack(anchor="w", pady=Spacing.XS)

    def _build_recognition_tab(self, parent) -> None:
        """识别选项卡。"""
        # AcoustID API Key
        ttk.Label(
            parent,
            text="AcoustID API Key：",
            font=Fonts.BODY,
            foreground=Colors.TEXT_SECONDARY,
        ).pack(anchor="w", pady=(Spacing.XS, 0))

        self._acoustid_var = tk.StringVar(value=self._config.acoustid_api_key)
        ttk.Entry(parent, textvariable=self._acoustid_var, width=50).pack(
            fill="x", pady=(Spacing.XS, Spacing.SM)
        )

        ttk.Label(
            parent,
            text="在 https://acoustid.org/ 注册获取 API Key",
            font=Fonts.SMALL,
            foreground=Colors.TEXT_SECONDARY,
        ).pack(anchor="w", pady=(0, Spacing.MD))

        # Shazam 超时
        ttk.Label(
            parent,
            text="Shazam 超时（秒）：",
            font=Fonts.BODY,
            foreground=Colors.TEXT_SECONDARY,
        ).pack(anchor="w", pady=(Spacing.SM, 0))

        self._timeout_var = tk.StringVar(value=str(self._config.shazamio_timeout))
        ttk.Entry(parent, textvariable=self._timeout_var, width=10).pack(
            anchor="w", pady=(Spacing.XS, Spacing.SM)
        )

        # 最小置信度
        ttk.Label(
            parent,
            text="最小置信度（0.0-1.0）：",
            font=Fonts.BODY,
            foreground=Colors.TEXT_SECONDARY,
        ).pack(anchor="w", pady=(Spacing.SM, 0))

        self._confidence_var = tk.StringVar(value=str(self._config.min_confidence))
        ttk.Entry(parent, textvariable=self._confidence_var, width=10).pack(
            anchor="w", pady=(Spacing.XS, Spacing.SM)
        )

        # 模糊匹配置信度
        ttk.Label(
            parent,
            text="模糊匹配置信度：",
            font=Fonts.BODY,
            foreground=Colors.TEXT_SECONDARY,
        ).pack(anchor="w", pady=(Spacing.SM, 0))

        self._fuzzy_confidence_var = tk.StringVar(
            value=str(self._config.fuzzy_min_confidence)
        )
        ttk.Entry(parent, textvariable=self._fuzzy_confidence_var, width=10).pack(
            anchor="w", pady=(Spacing.XS, Spacing.SM)
        )

        # 最大候选数
        ttk.Label(
            parent,
            text="最大候选数：",
            font=Fonts.BODY,
            foreground=Colors.TEXT_SECONDARY,
        ).pack(anchor="w", pady=(Spacing.SM, 0))

        self._max_candidates_var = tk.StringVar(
            value=str(self._config.fuzzy_max_candidates)
        )
        ttk.Entry(parent, textvariable=self._max_candidates_var, width=10).pack(
            anchor="w", pady=(Spacing.XS, Spacing.SM)
        )

    def _build_lyrics_tab(self, parent) -> None:
        """歌词选项卡。"""
        # 歌词提供商
        ttk.Label(
            parent,
            text="歌词提供商（按优先级排序）：",
            font=Fonts.BODY,
            foreground=Colors.TEXT_SECONDARY,
        ).pack(anchor="w", pady=(Spacing.XS, Spacing.SM))

        providers_frame = ttk.Frame(parent)
        providers_frame.pack(fill="x", pady=(0, Spacing.MD))

        self._provider_vars: dict[str, tk.BooleanVar] = {}
        for provider in ["lrclib", "netease", "qqmusic"]:
            var = tk.BooleanVar(value=provider in self._config.lyrics_providers)
            self._provider_vars[provider] = var
            tb.Checkbutton(
                providers_frame,
                text=provider.upper(),
                variable=var,
                bootstyle="round-toggle",
            ).pack(anchor="w", pady=Spacing.XS)

        # 默认歌词语言
        ttk.Label(
            parent,
            text="默认歌词语言：",
            font=Fonts.BODY,
            foreground=Colors.TEXT_SECONDARY,
        ).pack(anchor="w", pady=(Spacing.MD, Spacing.XS))

        self._default_lang_var = tk.StringVar(value=self._config.lyrics_language)
        lang_combo = ttk.Combobox(
            parent,
            textvariable=self._default_lang_var,
            values=["original_only", "bilingual", "japanese_romaji", "bilingual_romaji"],
            state="readonly",
        )
        lang_combo.pack(anchor="w", pady=(0, Spacing.SM))

    def _build_performance_tab(self, parent) -> None:
        """性能选项卡。"""
        # 并行工作数
        ttk.Label(
            parent,
            text="并行工作数：",
            font=Fonts.BODY,
            foreground=Colors.TEXT_SECONDARY,
        ).pack(anchor="w", pady=(Spacing.XS, 0))

        self._workers_var = tk.StringVar(value=str(self._config.max_workers))
        ttk.Entry(parent, textvariable=self._workers_var, width=10).pack(
            anchor="w", pady=(Spacing.XS, Spacing.SM)
        )

        # 速率限制
        ttk.Label(
            parent,
            text="API 速率限制（请求/秒）：",
            font=Fonts.BODY,
            foreground=Colors.TEXT_SECONDARY,
        ).pack(anchor="w", pady=(Spacing.MD, 0))

        self._rate_limit_var = tk.StringVar(value=str(self._config.rate_limit_rps))
        ttk.Entry(parent, textvariable=self._rate_limit_var, width=10).pack(
            anchor="w", pady=(Spacing.XS, Spacing.SM)
        )

    def _build_scan_tab(self, parent) -> None:
        """扫描选项卡。"""
        # 音频扩展名
        ttk.Label(
            parent,
            text="支持的音频扩展名：",
            font=Fonts.BODY,
            foreground=Colors.TEXT_SECONDARY,
        ).pack(anchor="w", pady=(Spacing.XS, Spacing.SM))

        ext_text = " ".join(sorted(self._config.audio_extensions))
        self._extensions_var = tk.StringVar(value=ext_text)
        ext_entry = ttk.Entry(parent, textvariable=self._extensions_var, width=50)
        ext_entry.pack(fill="x", pady=(0, Spacing.SM))

        ttk.Label(
            parent,
            text="用空格分隔多个扩展名",
            font=Fonts.SMALL,
            foreground=Colors.TEXT_SECONDARY,
        ).pack(anchor="w", pady=(0, Spacing.MD))

        # 时长限制
        duration_frame = ttk.Frame(parent)
        duration_frame.pack(fill="x", pady=(Spacing.MD, 0))

        ttk.Label(
            duration_frame,
            text="最短时长（秒）：",
            font=Fonts.BODY,
            foreground=Colors.TEXT_SECONDARY,
        ).pack(side="left")

        self._min_duration_var = tk.StringVar(value=str(self._config.min_duration_sec))
        ttk.Entry(duration_frame, textvariable=self._min_duration_var, width=8).pack(
            side="left", padx=(Spacing.XS, Spacing.MD)
        )

        ttk.Label(
            duration_frame,
            text="最长时长（秒）：",
            font=Fonts.BODY,
            foreground=Colors.TEXT_SECONDARY,
        ).pack(side="left")

        self._max_duration_var = tk.StringVar(value=str(self._config.max_duration_sec))
        ttk.Entry(duration_frame, textvariable=self._max_duration_var, width=8).pack(
            side="left", padx=Spacing.XS
        )

    # ── Actions ────────────────────────────────────────────────────────

    def _on_save(self) -> None:
        """保存配置。"""
        try:
            # 常规
            self._config.overwrite_tags = self._overwrite_var.get()
            self._config.backup_original = self._backup_var.get()
            self._config.write_lrc_sidecar = self._lrc_sidecar_var.get()

            # 识别
            self._config.acoustid_api_key = self._acoustid_var.get().strip()
            self._config.shazamio_timeout = int(self._timeout_var.get())
            self._config.min_confidence = float(self._confidence_var.get())
            self._config.fuzzy_min_confidence = float(self._fuzzy_confidence_var.get())
            self._config.fuzzy_max_candidates = int(self._max_candidates_var.get())

            # 歌词
            self._config.lyrics_providers = [
                p for p, var in self._provider_vars.items() if var.get()
            ]
            self._config.lyrics_language = self._default_lang_var.get()

            # 性能
            self._config.max_workers = int(self._workers_var.get())
            self._config.rate_limit_rps = float(self._rate_limit_var.get())

            # 扫描
            extensions = self._extensions_var.get().split()
            self._config.audio_extensions = set(extensions)
            self._config.min_duration_sec = float(self._min_duration_var.get())
            self._config.max_duration_sec = float(self._max_duration_var.get())

            # 保存到文件
            self._config.save()
            self._result = True
            self.destroy()

        except ValueError as e:
            from tkinter import messagebox
            messagebox.showerror("输入错误", f"请检查输入值：{e}")

    def _on_cancel(self) -> None:
        """取消，恢复原始配置。"""
        self._result = False
        self.destroy()

    def _on_reset(self) -> None:
        """恢复默认设置。"""
        from tkinter import messagebox
        if messagebox.askyesno("确认", "确定要恢复所有设置为默认值吗？"):
            default = Config()
            self._config.__dict__.update(default.__dict__)
            self.destroy()
            # 重新打开对话框
            SettingsDialog(self.master, self._config)
