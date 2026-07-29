"""Audio Matcher GUI — 现代化主窗口。

布局：
- 顶部：步骤指示条 + 设置按钮
- 左侧：目录选择卡片 + 选项卡片
- 右侧：结果表格 + 标签编辑器 + 歌词预览 + 状态栏
"""

from __future__ import annotations

import asyncio
import logging
import threading
from pathlib import Path
from typing import Optional

import ttkbootstrap as tb

from audio_matcher.core.config import Config
from audio_matcher.core.models import ProcessingStatus, TrackMatch, TrackResult
from audio_matcher.core.tagger import AudioTagger

from audio_matcher.gui.dialogs.candidate_selector import CandidateSelectorDialog
from audio_matcher.gui.dialogs.settings_dialog import SettingsDialog
from audio_matcher.gui.styles import Colors, Fonts, Sizes, Spacing
from audio_matcher.gui.widgets.directory_card import DirectoryCard
from audio_matcher.gui.widgets.lyrics_viewer import LyricsPanel
from audio_matcher.gui.widgets.options_card import OptionsCard
from audio_matcher.gui.widgets.result_table import ResultTable
from audio_matcher.gui.widgets.status_bar import StatusBar
from audio_matcher.gui.widgets.step_indicator import StepIndicator
from audio_matcher.gui.widgets.tag_editor import TagEditorPanel

logger = logging.getLogger("audio_matcher.gui")


class MainWindow(tb.Window):
    """主程序窗口。"""

    def __init__(self, themename: str = "darkly") -> None:
        super().__init__(
            themename=themename,
            title="音频匹配器 v0.0.6",
            size=(Sizes.WINDOW_WIDTH, Sizes.WINDOW_HEIGHT),
            minsize=(Sizes.WINDOW_MIN_WIDTH, Sizes.WINDOW_MIN_HEIGHT),
        )
        self.config = Config.load()

        # 状态
        self._scan_cancelled = False
        self._current_results: list[TrackResult] = []

        # Asyncio 后台线程桥接
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._start_async_loop()

        self._build()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── 异步桥接 ─────────────────────────────────────────────────────────

    def _start_async_loop(self) -> None:
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def _run_loop(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def _run_async(self, coro, callback=None) -> None:
        """在后台事件循环中调度协程。"""
        async def _wrapper():
            try:
                result = await coro
                if callback:
                    self.after(0, callback, result)
            except asyncio.CancelledError:
                self.after(0, lambda: self._status.log("扫描已取消", "warning"))
                self.after(0, lambda: self._directory_card.set_scanning(False))
            except Exception as exc:
                self.after(0, lambda: self._status.log_error(f"错误：{exc}"))
                self.after(0, lambda: self._directory_card.set_scanning(False))

        if self._loop:
            asyncio.run_coroutine_threadsafe(_wrapper(), self._loop)

    def _on_close(self) -> None:
        if self._loop:
            self._loop.call_soon_threadsafe(self._loop.stop)
        self.destroy()

    # ── 布局 ──────────────────────────────────────────────────────────────

    def _build(self) -> None:
        # 配置窗口背景
        self.configure(bg=Colors.BG_DARK)

        # 顶部：步骤指示条
        self._step_indicator = StepIndicator(
            self,
            on_step_click=self._on_step_click,
            on_settings=self._on_settings,
        )
        self._step_indicator.pack(fill="x", pady=(0, 1))

        # 分隔线
        separator = tb.Frame(self, height=1, bootstyle="secondary")
        separator.pack(fill="x")

        # 主内容区
        content = tb.Frame(self)
        content.pack(fill="both", expand=True)

        # 左侧面板
        sidebar = tb.Frame(content, width=Sizes.SIDEBAR_WIDTH)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        # 目录选择卡片
        self._directory_card = DirectoryCard(
            sidebar,
            config=self.config,  # 传入主配置，修复 bug
            on_scan=self._on_scan,
            on_cancel=self._on_cancel_scan,
        )
        self._directory_card.pack(fill="both", expand=True, pady=(0, Spacing.SM))

        # 选项卡片
        self._options_card = OptionsCard(
            sidebar,
            on_restore=self._on_restore,
        )
        self._options_card.pack(fill="x")

        # 右侧主内容区
        main_area = tb.Frame(content)
        main_area.pack(side="left", fill="both", expand=True, padx=(Spacing.SM, 0))

        # 结果表格（主要区域）
        self._result_table = ResultTable(
            main_area,
            on_select=self._on_track_select,
            on_write=self._on_write_tags,
            on_retry=self._on_retry_track,
            on_skip=self._on_skip_track,
        )
        self._result_table.pack(fill="both", expand=True, pady=(0, Spacing.SM))

        # 下方：编辑器 + 歌词
        bottom_panel = tb.Frame(main_area)
        bottom_panel.pack(fill="x", pady=(0, Spacing.SM))

        self._tag_editor = TagEditorPanel(
            bottom_panel,
            on_write=self._on_write_tags,
        )
        self._tag_editor.pack(side="left", fill="both", expand=True, padx=(0, Spacing.SM))

        self._lyrics_viewer = LyricsPanel(bottom_panel)
        self._lyrics_viewer.pack(side="right", fill="both", expand=True)

        # 底部状态栏
        self._status = StatusBar(main_area)
        self._status.pack(fill="x")

        # 初始化步骤
        self._step_indicator.set_step("select")

    # ── 步骤管理 ─────────────────────────────────────────────────────────

    def _on_step_click(self, step_id: str) -> None:
        """步骤点击（回退）。"""
        # 目前不支持回退，保留接口
        pass

    def _on_settings(self) -> None:
        """打开设置对话框。"""
        dialog = SettingsDialog(self, self.config)
        if dialog.saved:
            self._status.log_success("设置已保存")
            # 重新加载配置
            self.config = Config.load()
            # 更新目录卡片的配置
            self._directory_card._config = self.config

    # ── 扫描流程 ─────────────────────────────────────────────────────────

    def _on_scan(self, path: Path, files: list) -> None:
        """开始扫描。"""
        self._scan_cancelled = False
        self._current_results = []

        # 更新步骤
        self._step_indicator.set_step("select", completed=True)
        self._step_indicator.set_step("scan")

        # 禁用选项
        self._options_card.set_enabled(False)

        # 更新状态
        self._status.set_status("正在扫描文件...")
        self._status.set_progress(0, len(files))
        self._status.log(f"扫描目录：{path}（{len(files)} 个文件）")

        # 清空表格
        self._result_table.set_results([])
        self._tag_editor.clear()
        self._lyrics_viewer.clear()

        # 进度回调
        def _on_progress(current: int, total: int, filename: str) -> None:
            if self._scan_cancelled:
                return
            self.after(0, lambda: self._status.set_progress(current, total))
            self.after(0, lambda: self._status.set_status(f"处理中 ({current}/{total}): {filename}"))

        async def _scan_pipeline():
            from audio_matcher.core.pipeline import Pipeline
            pipeline = Pipeline(self.config)
            return await pipeline.run(
                path,
                dry_run=self._options_card.dry_run,
                rename_files=self._options_card.rename_files,
                files=files,
                lyrics_language=self._options_card.language,
                progress_callback=_on_progress,
            )

        def _on_done(results):
            if self._scan_cancelled:
                self._status.set_status("扫描已取消")
                self._directory_card.set_scanning(False)
                self._options_card.set_enabled(True)
                return

            self._current_results = results
            self._result_table.set_results(results)

            # 统计
            tagged = sum(1 for r in results if r.status == ProcessingStatus.TAGGED)
            lyrics_found = sum(1 for r in results if r.lyrics and r.lyrics.lines)
            errors = sum(1 for r in results if r.status == ProcessingStatus.ERROR)
            awaiting = sum(
                1 for r in results
                if r.status == ProcessingStatus.AWAITING_SELECTION
            )

            # 更新状态栏
            self._status.set_stats(tagged, lyrics_found, errors, awaiting)
            self._status.set_progress(len(results), len(results))

            # 完成消息
            parts = [f"{tagged} 首已标记", f"{lyrics_found} 首有歌词", f"{errors} 失败"]
            if awaiting:
                parts.append(f"{awaiting} 首等待选择")
            status_msg = f"完成：{'，'.join(parts)}"
            self._status.set_status(status_msg)
            self._status.log_success(f"扫描完成：{status_msg}")

            # 更新步骤
            self._step_indicator.set_step("scan", completed=True)
            self._step_indicator.set_step("review")

            # 恢复 UI
            self._directory_card.set_scanning(False)
            self._options_card.set_enabled(True)

        self._run_async(_scan_pipeline(), _on_done)

    def _on_cancel_scan(self) -> None:
        """取消扫描。"""
        self._scan_cancelled = True
        self._status.log_warning("正在取消扫描...")

    # ── 结果处理 ─────────────────────────────────────────────────────────

    def _on_track_select(self, result: TrackResult) -> None:
        """选中曲目。"""
        self._tag_editor.load(result)
        if result.lyrics:
            self._lyrics_viewer.set_lyrics(result.lyrics)
        else:
            self._lyrics_viewer.clear()

        # 如果待选择，弹出候选对话框
        if (
            result.status == ProcessingStatus.AWAITING_SELECTION
            and result.match_alternatives
        ):
            self._show_candidate_selection(result)

    def _show_candidate_selection(self, result: TrackResult) -> None:
        """显示候选选择对话框。"""
        dialog = CandidateSelectorDialog(
            self,
            candidates=result.match_alternatives,
            filename=result.audio_file.path.name,
        )

        selected = dialog.selected_match
        if selected is None:
            self._status.log(f"已跳过：{result.audio_file.path.name}")
            return

        self._status.log(
            f"已选择：{selected.artist} - {selected.title}"
            f"（{selected.confidence:.0%}）"
        )

        async def _resume():
            from audio_matcher.core.pipeline import Pipeline
            pipeline = Pipeline(self.config)
            await pipeline.resume_after_selection(result, selected)
            return result

        def _on_resumed(updated: TrackResult):
            # 写入标签
            self._write_tag_for_result(updated)

            # 刷新显示
            self._result_table.set_results(self._current_results)
            self._tag_editor.load(updated)
            if updated.lyrics:
                self._lyrics_viewer.set_lyrics(updated.lyrics)

        self._run_async(_resume(), _on_resumed)

    def _write_tag_for_result(self, result: TrackResult) -> None:
        """为单个结果写入标签。"""
        tagger = AudioTagger(self.config)
        try:
            tagger.write(result.audio_file, result.match, result.lyrics)
            result.status = ProcessingStatus.TAGGED
            self._status.log_success(f"标签已写入：{result.audio_file.path.name}")
        except Exception as exc:
            self._status.log_error(f"写入标签失败：{exc}")

    def _on_write_tags(self, result: TrackResult) -> None:
        """写入标签（编辑器按钮）。"""
        self._write_tag_for_result(result)
        # 刷新表格
        self._result_table.set_results(self._current_results)
        # 更新编辑器状态
        self._tag_editor.load(result)

    def _on_retry_track(self, result: TrackResult) -> None:
        """重试识别。"""
        self._status.log(f"重新识别：{result.audio_file.path.name}")
        # TODO: 实现单个文件重试
        self._status.log_warning("重试功能待实现")

    def _on_skip_track(self, result: TrackResult) -> None:
        """跳过文件。"""
        result.status = ProcessingStatus.SKIPPED
        self._result_table.set_results(self._current_results)
        self._status.log(f"已跳过：{result.audio_file.path.name}")

    # ── 工具功能 ─────────────────────────────────────────────────────────

    def _on_restore(self) -> None:
        """恢复原始文件名。"""
        path = self._directory_card.selected_path
        if not path:
            self._status.log_error("请先选择目录")
            return

        mapping_file = path / "_track_mapping.txt"
        if not mapping_file.exists():
            self._status.log_error(f"未找到映射文件：{mapping_file}")
            return

        restored = 0
        for line in mapping_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or "=" not in line:
                continue
            left, right = line.split("=", 1)
            original = left.strip()
            target = right.strip()
            original_path = path / original
            target_path = path / target
            if target_path.exists() and not original_path.exists():
                try:
                    target_path.rename(original_path)
                    self._status.log(f"恢复：{target} → {original}")
                    restored += 1
                except OSError as exc:
                    self._status.log_error(f"恢复失败 {target}: {exc}")

        self._status.log_success(f"文件名恢复完成：{restored} 个文件")
        # 刷新文件列表
        self._directory_card._refresh_file_list()


def main() -> None:
    """启动 GUI。"""
    app = MainWindow()
    app.mainloop()


if __name__ == "__main__":
    main()
