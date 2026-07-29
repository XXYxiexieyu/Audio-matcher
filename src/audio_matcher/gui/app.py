"""Audio Matcher GUI — 主程序窗口。

用法：
    python -m audio_matcher.gui.app
"""

from __future__ import annotations

import asyncio
import logging
import threading
from pathlib import Path
from typing import Optional

import ttkbootstrap as tb
from ttkbootstrap.constants import *

from audio_matcher.core.config import Config
from audio_matcher.core.models import ProcessingStatus, TrackMatch, TrackResult
from audio_matcher.core.tagger import AudioTagger

from audio_matcher.gui.widgets.folder_selector import FolderSelector
from audio_matcher.gui.widgets.track_table import TrackTable
from audio_matcher.gui.widgets.tag_editor import TagEditor
from audio_matcher.gui.widgets.lyrics_viewer import LyricsViewer
from audio_matcher.gui.widgets.progress_panel import ProgressPanel
from audio_matcher.gui.dialogs.candidate_selector import CandidateSelectorDialog

logger = logging.getLogger("audio_matcher.gui")


class MainWindow(tb.Window):
    """主程序窗口。"""

    def __init__(self, themename: str = "darkly") -> None:
        super().__init__(themename=themename, title="音频匹配器 v0.0.6", size=(1200, 850))
        self.config = Config()

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
            except Exception as exc:
                self.after(0, lambda: self._log.log(f"错误：{exc}"))

        if self._loop:
            asyncio.run_coroutine_threadsafe(_wrapper(), self._loop)

    def _on_close(self) -> None:
        if self._loop:
            self._loop.call_soon_threadsafe(self._loop.stop)
        self.destroy()

    # ── 布局 ──────────────────────────────────────────────────────────────

    def _build(self) -> None:
        # 左侧栏
        sidebar = tb.Frame(self, width=220, padding=10)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        self._folder_selector = FolderSelector(sidebar, on_scan=self._on_scan, on_restore=self._on_restore)
        self._folder_selector.pack(fill="both", expand=True)

        # 主内容区
        content = tb.Frame(self, padding=5)
        content.pack(side="left", fill="both", expand=True)

        # 上方：曲目表
        self._track_table = TrackTable(content, on_select=self._on_track_select)
        self._track_table.pack(fill="both", expand=True, pady=(0, 5))

        # 下方：编辑器 + 歌词
        bottom = tb.Frame(content)
        bottom.pack(fill="x", pady=(0, 5))

        self._tag_editor = TagEditor(bottom, on_write=self._on_write_tags)
        self._tag_editor.pack(side="left", fill="both", expand=True, padx=(0, 5))

        self._lyrics_viewer = LyricsViewer(bottom)
        self._lyrics_viewer.pack(side="right", fill="both", expand=True, padx=(5, 0))

        # 底部状态栏：进度 + 日志
        self._log = ProgressPanel(content)
        self._log.pack(fill="x")

    # ── 事件处理 ──────────────────────────────────────────────────────────

    def _on_scan(self, path: Path, files: list, language: str, dry_run: bool, rename_files: bool = True) -> None:
        self._log.set_status("正在扫描文件...")
        self._log.set_progress(0, 1 if not files else len(files))
        self._log.log(f"扫描目录：{path}（{len(files)} 个文件，语言：{language}）")
        self._track_table.set_results([])

        # Progress callback — runs on background thread, schedules UI update.
        def _on_progress(current: int, total: int, filename: str) -> None:
            self.after(0, lambda: self._log.set_progress(current, total))
            self.after(0, lambda: self._log.set_status(f"处理中 ({current}/{total}): {filename}"))

        async def _scan_pipeline():
            from audio_matcher.core.pipeline import Pipeline
            pipeline = Pipeline(self.config)
            return await pipeline.run(
                path,
                dry_run=dry_run,
                rename_files=rename_files,
                files=files,
                lyrics_language=language,
                progress_callback=_on_progress,
            )

        def _on_done(results):
            self._track_table.set_results(results)
            tagged = sum(1 for r in results if r.status == ProcessingStatus.TAGGED)
            lyrics_found = sum(1 for r in results if r.lyrics and r.lyrics.lines)
            errors = sum(1 for r in results if r.status == ProcessingStatus.ERROR)
            awaiting = sum(
                1 for r in results
                if r.status == ProcessingStatus.AWAITING_SELECTION
            )
            parts = [f"{tagged} 首已标记", f"{lyrics_found} 首有歌词", f"{errors} 失败"]
            if awaiting:
                parts.append(f"{awaiting} 首等待选择")
            self._log.set_status(f"完成：{'，'.join(parts)}")
            self._log.set_progress(len(results), len(results))
            self._log.log(f"扫描完成：共 {len(results)} 个文件，{'，'.join(parts)}")
            # Refresh table to show updated filenames.
            self._track_table.set_results(results)

        self._run_async(_scan_pipeline(), _on_done)

    def _on_track_select(self, result: TrackResult) -> None:
        self._tag_editor.load(result)
        if result.lyrics:
            self._lyrics_viewer.set_lyrics(result.lyrics)
        else:
            self._lyrics_viewer.clear()

        # If this file has fuzzy candidates awaiting selection, show the dialog.
        if (
            result.status == ProcessingStatus.AWAITING_SELECTION
            and result.match_alternatives
        ):
            self._show_candidate_selection(result)

    def _show_candidate_selection(self, result: TrackResult) -> None:
        """弹出候选选择对话框，用户确认后继续管线处理。"""
        dialog = CandidateSelectorDialog(
            self,
            candidates=result.match_alternatives,
            filename=result.audio_file.path.name,
        )

        selected = dialog.selected_match
        if selected is None:
            self._log.log(f"已跳过：{result.audio_file.path.name}")
            return

        self._log.log(
            f"已选择：{selected.artist} - {selected.title}"
            f"（{selected.confidence:.0%}）"
        )

        async def _resume():
            from audio_matcher.core.pipeline import Pipeline
            pipeline = Pipeline(self.config)
            await pipeline.resume_after_selection(result, selected)
            return result

        def _on_resumed(updated: TrackResult):
            # Write tags.
            tagger = AudioTagger(self.config)
            try:
                tagger.write(
                    updated.audio_file, updated.match, updated.lyrics
                )
                updated.status = ProcessingStatus.TAGGED
                self._log.log(f"标签已写入：{updated.audio_file.path.name}")
                self._log.set_status(f"已标记：{updated.audio_file.path.name}")
            except Exception as exc:
                self._log.log(f"写入标签失败：{exc}")
            # Refresh table and editor.
            self._track_table.set_results(self._track_table.results)
            self._tag_editor.load(updated)
            if updated.lyrics:
                self._lyrics_viewer.set_lyrics(updated.lyrics)

        self._run_async(_resume(), _on_resumed)

    def _on_restore(self, path: Path) -> None:
        """Restore original filenames from _track_mapping.txt."""
        mapping_file = path / "_track_mapping.txt"
        if not mapping_file.exists():
            self._log.log(f"未找到映射文件：{mapping_file}")
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
                    self._log.log(f"恢复：{target} → {original}")
                    restored += 1
                except OSError as exc:
                    self._log.log(f"恢复失败 {target}: {exc}")

        self._log.set_status(f"已恢复 {restored} 个文件名")
        self._log.log(f"文件名恢复完成：{restored} 个文件")

    def _on_write_tags(self, result: TrackResult) -> None:
        tagger = AudioTagger(self.config)
        try:
            tagger.write(result.audio_file, result.match, result.lyrics)
            result.status = ProcessingStatus.TAGGED
            self._log.log(f"标签已写入：{result.audio_file.path.name}")
            self._log.set_status(f"已标记：{result.audio_file.path.name}")
        except Exception as exc:
            self._log.log(f"写入标签失败：{exc}")


def main() -> None:
    """启动 GUI。"""
    app = MainWindow()
    app.mainloop()


if __name__ == "__main__":
    main()
