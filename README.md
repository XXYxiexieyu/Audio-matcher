# Audio Matcher v0.0.5

Batch audio file identification, metadata tagging, and synced lyrics (LRC) downloader.

## Features

- **Audio identification** via Shazam fingerprinting and MusicBrainz/AcoustID
- **Multi-format support**: FLAC, WAV, MP3, DSD (.dsf, .dff), M4A, AAC, OGG, WMA, AIFF
- **Synced LRC lyrics** from LRCLIB, NetEase Cloud Music, and QQ Music
- **Automatic metadata tagging**: writes TITLE, ARTIST, ALBUM, YEAR, TRACKNUMBER, LYRICS tags
- **Batch processing** with async parallel workers and progress bar
- **Resume support**: skips already-processed files
- **Caching**: fingerprints and lyrics cached to avoid redundant API calls
- **Post-processing review**: edit recognized metadata before writing tags

## Quick Start

### 1. Install

```bash
pip install -e .
```

### 2. Identify and Tag Audio Files

```bash
# Full pipeline: identify + fetch lyrics + write tags
audio-matcher scan ./my_music

# Dry-run: preview without writing
audio-matcher scan ./my_music --dry-run

# Interactive review before writing
audio-matcher scan ./my_music --interactive

# With more parallel workers
audio-matcher scan ./my_music --workers 8
```

### 3. Launch GUI

```bash
python -m audio_matcher.gui.app
```

## Supported Formats

| Format | Extension | Tag Type | Lyrics Tag |
|--------|-----------|----------|------------|
| FLAC   | .flac     | Vorbis   | LYRICS     |
| MP3    | .mp3      | ID3v2    | USLT       |
| WAV    | .wav      | ID3v2    | USLT       |
| DSD    | .dsf      | ID3v2    | USLT       |
| DSD    | .dff      | ID3v2    | USLT       |
| M4A    | .m4a      | MP4      | ©lyr       |
| AAC    | .aac      | ID3v2    | USLT       |
| OGG    | .ogg      | Vorbis   | LYRICS     |
| AIFF   | .aiff     | ID3v2    | USLT       |

## Changelog

### v0.0.5 (2026-07-29)
- **文件选择**: 浏览目录后显示文件列表（复选框默认全选）+ 全选/全不选按钮
- **歌词语言选择**: 仅外语 / 双语 / 日语+罗马音 / 双语+罗马音
- **罗马音转换**: pykakasi 日语→罗马音，保持 LRC 时间戳
- **多歌词标签**: ID3 多 USLT 帧 / Vorbis 多标签
- **歌词预览**: 原文/翻译/罗马音分段显示
- 修复 GUI recursive 参数传递 bug
- Pipeline 支持预过滤文件列表

### v0.0.4 (2026-07-29)
- **歌词注入修复**: 修复 LRCLIB 搜索因 album 参数过严导致 0 结果的问题
- **LRCLIB 回退**: 无 syncedLyrics 时自动使用 plainLyrics（转为 unsynced LRC）
- **NetEase API**: 添加 `Accept: application/json` header，使用 `content_type=None` 处理非标准响应
- **QQ Music API**: 使用 `content_type=None` 处理 lyrics 接口返回的 `text/html` content-type
- 统一 `_API_HEADERS` 常量，新增 `_parse_plain` / `_plain_to_lrc` 辅助方法

### v0.0.3 (2026-07-27)
- MP3 等 9 种格式支持
- 歌词嵌入（ID3v2 USLT / Vorbis LYRICS）+ LRC sidecar
- 文件重命名为「歌名 - 艺人」格式
- GUI: Checkbutton 改为 ttkbootstrap round-toggle
- 专辑字段解析修复（metadata/metapages 双格式）
- 写入前清除旧标签

### v0.0.2
- GUI 全面中文化

### v0.0.1
- 全新 CLI + GUI 双模，英文界面

## License

MIT
