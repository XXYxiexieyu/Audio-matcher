"""步骤指示条组件 — 显示当前工作流程阶段。"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable, Optional

import ttkbootstrap as tb

from audio_matcher.gui.styles import Colors, Fonts, Icons, Sizes, Spacing


class StepIndicator(ttk.Frame):
    """顶部步骤指示条，显示工作流程进度。

    步骤：
    1. 选择目录
    2. 扫描识别
    3. 审查确认

    右侧有设置按钮。
    """

    STEPS = [
        ("select", "选择目录"),
        ("scan", "扫描识别"),
        ("review", "审查确认"),
    ]

    def __init__(
        self,
        parent,
        *,
        on_step_click: Optional[Callable[[str], None]] = None,
        on_settings: Optional[Callable[[], None]] = None,
        **kwargs,
    ) -> None:
        super().__init__(parent, **kwargs)
        self._on_step_click = on_step_click
        self._on_settings = on_settings
        self._current_step = "select"
        self._completed_steps: set[str] = set()
        self._step_labels: dict[str, ttk.Label] = {}
        self._step_icons: dict[str, ttk.Label] = {}
        self._build()

    def _build(self) -> None:
        self.configure(height=Sizes.STEP_INDICATOR_HEIGHT)
        self.pack_propagate(False)

        # 左侧：步骤
        steps_frame = ttk.Frame(self)
        steps_frame.pack(side="left", fill="y", padx=Spacing.LG)

        for i, (step_id, label) in enumerate(self.STEPS):
            if i > 0:
                # 箭头分隔
                arrow = ttk.Label(
                    steps_frame,
                    text="→",
                    font=Fonts.BODY,
                    foreground=Colors.TEXT_DISABLED,
                )
                arrow.pack(side="left", padx=Spacing.SM)

            # 步骤图标
            icon = ttk.Label(
                steps_frame,
                text=f"{i + 1}",
                font=Fonts.BODY_BOLD,
                foreground=Colors.TEXT_SECONDARY,
                width=3,
                anchor="center",
            )
            icon.pack(side="left", padx=(Spacing.SM, Spacing.XS))
            self._step_icons[step_id] = icon

            # 步骤文字
            text = ttk.Label(
                steps_frame,
                text=label,
                font=Fonts.BODY,
                foreground=Colors.TEXT_SECONDARY,
                cursor="hand2",
            )
            text.pack(side="left")
            text.bind("<Button-1>", lambda e, s=step_id: self._on_step_clicked(s))
            self._step_labels[step_id] = text

        # 右侧：设置按钮
        settings_btn = tb.Button(
            self,
            text=f"{Icons.SETTINGS} 设置",
            command=self._on_settings_clicked,
            bootstyle="secondary-outline",
            width=10,
        )
        settings_btn.pack(side="right", padx=Spacing.LG, pady=Spacing.SM)

        # 初始状态
        self._update_display()

    def set_step(self, step_id: str, completed: bool = False) -> None:
        """设置当前步骤。

        Args:
            step_id: 步骤 ID ("select", "scan", "review")
            completed: 是否标记为已完成
        """
        if step_id not in [s[0] for s in self.STEPS]:
            return

        if completed:
            self._completed_steps.add(step_id)
            # 当前步骤变为下一个
            idx = [s[0] for s in self.STEPS].index(step_id)
            if idx + 1 < len(self.STEPS):
                self._current_step = self.STEPS[idx + 1][0]
        else:
            self._current_step = step_id

        self._update_display()

    def reset(self) -> None:
        """重置到第一步。"""
        self._current_step = "select"
        self._completed_steps.clear()
        self._update_display()

    def _update_display(self) -> None:
        """更新步骤显示样式。"""
        for step_id, _ in self.STEPS:
            icon = self._step_icons[step_id]
            label = self._step_labels[step_id]

            if step_id in self._completed_steps:
                # 已完成
                icon.configure(text=Icons.SUCCESS, foreground=Colors.SUCCESS)
                label.configure(foreground=Colors.SUCCESS, font=Fonts.BODY)
            elif step_id == self._current_step:
                # 当前步骤
                step_num = [s[0] for s in self.STEPS].index(step_id) + 1
                icon.configure(text=str(step_num), foreground=Colors.PRIMARY)
                label.configure(foreground=Colors.PRIMARY, font=Fonts.BODY_BOLD)
            else:
                # 未来步骤
                step_num = [s[0] for s in self.STEPS].index(step_id) + 1
                icon.configure(text=str(step_num), foreground=Colors.TEXT_DISABLED)
                label.configure(foreground=Colors.TEXT_DISABLED, font=Fonts.BODY)

    def _on_step_clicked(self, step_id: str) -> None:
        """步骤被点击（仅已完成步骤可回退）。"""
        if step_id in self._completed_steps and self._on_step_click:
            self._on_step_click(step_id)

    def _on_settings_clicked(self) -> None:
        """设置按钮被点击。"""
        if self._on_settings:
            self._on_settings()
