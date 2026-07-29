"""统一 UI 样式常量 — 颜色、字体、间距、尺寸。

所有 GUI 组件应使用这些常量，避免硬编码值。
"""

from __future__ import annotations

# ── 颜色 ─────────────────────────────────────────────────────────────

class Colors:
    """语义化颜色定义（darkly 主题适配）。"""

    # 主色
    PRIMARY = "#4a9eff"
    PRIMARY_HOVER = "#6bb0ff"
    PRIMARY_PRESSED = "#3a8eef"

    # 状态色
    SUCCESS = "#2ecc71"
    SUCCESS_BG = "#1e3a2a"
    WARNING = "#f39c12"
    WARNING_BG = "#3a2e1e"
    ERROR = "#e74c3c"
    ERROR_BG = "#3a1e1e"
    INFO = "#3498db"
    INFO_BG = "#1e2a3a"

    # 背景
    BG_DARK = "#1a1d23"      # 主背景
    BG_CARD = "#242830"      # 卡片背景
    BG_HOVER = "#2d3139"     # 悬停背景
    BG_SELECTED = "#2d4a6a"  # 选中背景
    BG_INPUT = "#2a2e35"     # 输入框背景

    # 文字
    TEXT_PRIMARY = "#e8eaed"
    TEXT_SECONDARY = "#9aa0a6"
    TEXT_DISABLED = "#5f6368"
    TEXT_LINK = "#4a9eff"

    # 边框
    BORDER = "#3c4043"
    BORDER_FOCUS = "#4a9eff"

    # 表格
    TABLE_ROW_EVEN = "#242830"
    TABLE_ROW_ODD = "#2a2e35"
    TABLE_HEADER = "#2d3139"


# ── 字体 ─────────────────────────────────────────────────────────────

class Fonts:
    """字体定义（family, size, weight）。"""

    DEFAULT_FAMILY = "Segoe UI"  # Windows 现代字体，回退到系统默认

    H1 = (DEFAULT_FAMILY, 16, "bold")
    H2 = (DEFAULT_FAMILY, 14, "bold")
    H3 = (DEFAULT_FAMILY, 12, "bold")
    BODY = (DEFAULT_FAMILY, 11, "normal")
    BODY_BOLD = (DEFAULT_FAMILY, 11, "bold")
    SMALL = (DEFAULT_FAMILY, 10, "normal")
    SMALL_BOLD = (DEFAULT_FAMILY, 10, "bold")
    MONO = ("Cascadia Code", 10, "normal")  # 等宽字体，用于 LRC 时间戳


# ── 间距 ─────────────────────────────────────────────────────────────

class Spacing:
    """标准间距值（px）。"""

    XS = 4
    SM = 8
    MD = 12
    LG = 16
    XL = 24
    XXL = 32


# ── 尺寸 ─────────────────────────────────────────────────────────────

class Sizes:
    """标准尺寸值（px）。"""

    # 窗口
    WINDOW_WIDTH = 1280
    WINDOW_HEIGHT = 800
    WINDOW_MIN_WIDTH = 960
    WINDOW_MIN_HEIGHT = 600

    # 布局
    SIDEBAR_WIDTH = 280
    STEP_INDICATOR_HEIGHT = 48
    STATUS_BAR_HEIGHT = 32

    # 卡片
    CARD_RADIUS = 8
    CARD_PADDING = 16

    # 按钮
    BUTTON_HEIGHT = 32
    BUTTON_PADDING_X = 16

    # 输入框
    INPUT_HEIGHT = 32
    INPUT_RADIUS = 4

    # 表格
    TABLE_ROW_HEIGHT = 28
    TABLE_HEADER_HEIGHT = 32


# ── 图标 ─────────────────────────────────────────────────────────────

class Icons:
    """Unicode 图标（避免外部图标文件）。"""

    FOLDER = "📁"
    MUSIC = "🎵"
    SEARCH = "🔍"
    SETTINGS = "⚙️"
    SUCCESS = "✓"
    WARNING = "?"
    ERROR = "✗"
    PENDING = "…"
    PLAY = "▶"
    PAUSE = "⏸"
    STOP = "⏹"
    REFRESH = "🔄"
    WRITE = "💾"
    EDIT = "✏️"
    DELETE = "🗑"
    EXPAND = "▼"
    COLLAPSE = "▶"
    CHECKED = "☑"
    UNCHECKED = "☐"
    LOADING = "⏳"


# ── 样式辅助函数 ─────────────────────────────────────────────────────

def card_style() -> dict:
    """返回卡片样式参数字典。"""
    return {
        "padding": Sizes.CARD_PADDING,
    }


def button_primary_style() -> dict:
    """返回主要按钮样式。"""
    return {
        "bootstyle": "primary",
        "padding": (Sizes.BUTTON_PADDING_X, Sizes.BUTTON_HEIGHT // 2),
    }


def button_secondary_style() -> dict:
    """返回次要按钮样式。"""
    return {
        "bootstyle": "secondary-outline",
        "padding": (Sizes.BUTTON_PADDING_X, Sizes.BUTTON_HEIGHT // 2),
    }


def button_danger_style() -> dict:
    """返回危险按钮样式。"""
    return {
        "bootstyle": "danger-outline",
        "padding": (Sizes.BUTTON_PADDING_X, Sizes.BUTTON_HEIGHT // 2),
    }
