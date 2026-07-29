"""GUI 组件包。"""

from audio_matcher.gui.widgets.directory_card import DirectoryCard
from audio_matcher.gui.widgets.lyrics_viewer import LyricsPanel
from audio_matcher.gui.widgets.options_card import OptionsCard
from audio_matcher.gui.widgets.result_table import ResultTable
from audio_matcher.gui.widgets.status_bar import StatusBar
from audio_matcher.gui.widgets.step_indicator import StepIndicator
from audio_matcher.gui.widgets.tag_editor import TagEditorPanel

__all__ = [
    "DirectoryCard",
    "LyricsPanel",
    "OptionsCard",
    "ResultTable",
    "StatusBar",
    "StepIndicator",
    "TagEditorPanel",
]
