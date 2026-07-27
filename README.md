# Audio Matcher v0.0.3

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

## License

MIT
