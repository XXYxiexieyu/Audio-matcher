"""CLI entry point for Audio Matcher.

Usage:
    audio-matcher scan <directory> [--workers N] [--interactive] [--dry-run] [--resume FILE] [--no-lyrics]
    audio-matcher tag <file> --title X --artist Y [--album Z] [--year Y] [--track N] [--lyrics FILE]
    audio-matcher lyrics <file>
    audio-matcher --version
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

from audio_matcher import __version__
from audio_matcher.core.config import Config, create_default_config
from audio_matcher.core.tagger import AudioTagger
from audio_matcher.core.models import (
    AudioFile,
    AudioFormat,
    MatchSource,
    ProcessingStatus,
    SyncedLyrics,
    TrackMatch,
    TrackResult,
)
from audio_matcher.utils.logging import setup_logging

logger = logging.getLogger("audio_matcher.cli")


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="audio-matcher",
        description="Audio identification, metadata tagging, and lyrics downloader.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  audio-matcher scan ./my_music
  audio-matcher scan ./my_music --dry-run
  audio-matcher scan ./my_music --interactive
  audio-matcher tag song.flac --title "Song" --artist "Artist"
  audio-matcher lyrics song.flac
  audio-matcher --version
        """,
    )
    parser.add_argument(
        "--version", "-V", action="version",
        version=f"audio-matcher {__version__}",
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Detailed logging")

    sub = parser.add_subparsers(dest="command", title="commands")

    # ── scan ────────────────────────────────────────────────────────────
    scan = sub.add_parser("scan", help="Scan and process audio files")
    scan.add_argument("directory", help="Directory to scan for audio files")
    scan.add_argument("--workers", "-w", type=int, default=None, help="Max parallel workers")
    scan.add_argument("--interactive", "-i", action="store_true", help="Review before writing tags")
    scan.add_argument("--dry-run", action="store_true", help="Preview only, no writing")
    scan.add_argument("--resume", help="Resume from state file")
    scan.add_argument("--no-lyrics", action="store_true", help="Skip lyrics step")
    scan.add_argument("--config", "-c", help="Config file path")

    # ── tag ─────────────────────────────────────────────────────────────
    tag = sub.add_parser("tag", help="Tag a single audio file manually")
    tag.add_argument("file", help="Audio file to tag")
    tag.add_argument("--title", help="Track title")
    tag.add_argument("--artist", help="Artist name")
    tag.add_argument("--album", help="Album name")
    tag.add_argument("--year", type=int, help="Release year")
    tag.add_argument("--track", type=int, help="Track number")
    tag.add_argument("--lyrics", help="Lyrics text or .lrc file path")

    # ── lyrics ──────────────────────────────────────────────────────────
    lyrics_cmd = sub.add_parser("lyrics", help="Fetch lyrics for a track (identify first if needed)")
    lyrics_cmd.add_argument("file", help="Audio file to fetch lyrics for")
    lyrics_cmd.add_argument("--title", help="Track title (skip recognition)")
    lyrics_cmd.add_argument("--artist", help="Artist name (skip recognition)")

    # ── init-config ─────────────────────────────────────────────────────
    sub.add_parser("init-config", help="Create a default config file")

    return parser


def main() -> None:
    """Entry point."""
    parser = build_parser()
    args = parser.parse_args()

    setup_logging(verbose=args.verbose)

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    if args.command == "init-config":
        path = create_default_config()
        print(f"Default config written to: {path}")
        return

    if args.command == "scan":
        asyncio.run(_cmd_scan(args))
    elif args.command == "tag":
        _cmd_tag(args)
    elif args.command == "lyrics":
        asyncio.run(_cmd_lyrics(args))


# ── Command implementations ──────────────────────────────────────────────


async def _cmd_scan(args) -> None:
    """Run the full scan pipeline."""
    config = Config.load(args.config) if args.config else Config()
    if args.workers is not None:
        config.max_workers = args.workers

    from audio_matcher.core.pipeline import Pipeline
    pipeline = Pipeline(config)

    print(f"Scanning: {args.directory}")
    results = await pipeline.run(
        args.directory,
        resume_path=args.resume,
        interactive=args.interactive,
        dry_run=args.dry_run,
        no_lyrics=args.no_lyrics,
    )

    from audio_matcher.cli.formatters import print_results_table
    print_results_table(results)

    # Handle files awaiting candidate selection (always, even non-interactive).
    awaiting = [
        r for r in results
        if r.status == ProcessingStatus.AWAITING_SELECTION
    ]
    if awaiting:
        if args.interactive:
            print(f"\n{len(awaiting)} file(s) need match selection.\n")
            tagger = AudioTagger(config)
            for r in awaiting:
                selected = _prompt_candidate_selection(r)
                if selected is not None:
                    r.match = selected
                    r.status = ProcessingStatus.RECOGNIZED
                    if not args.dry_run:
                        try:
                            tagger.write(r.audio_file, r.match, r.lyrics)
                            r.status = ProcessingStatus.TAGGED
                            print(f"  ✓ Tagged: {r.audio_file.path.name}")
                        except Exception as exc:
                            print(f"  ✗ Write error: {exc}")
            # Re-print updated table.
            print_results_table(results)
        else:
            print(
                f"\n{len(awaiting)} file(s) need match selection. "
                f"Re-run with --interactive to choose."
            )

    # Interactive mode: let user edit before writing.
    if args.interactive and results:
        _interactive_review(results, config)


def _cmd_tag(args) -> None:
    """Tag a single file manually."""
    path = Path(args.file)
    if not path.exists():
        print(f"Error: file not found: {args.file}", file=sys.stderr)
        sys.exit(1)

    af = AudioFile(path=path, format=AudioFormat.UNKNOWN)
    match = TrackMatch(
        title=args.title or "",
        artist=args.artist or "",
        album=args.album or "",
        year=args.year,
        track_number=args.track,
        source=MatchSource.SHAZAM,
    )

    lyrics = None
    if args.lyrics:
        lrc_text = _read_lyrics_input(args.lyrics)
        from audio_matcher.core.lyrics import LyricsFetcher
        lines = LyricsFetcher._parse_lrc(lrc_text)
        lyrics = SyncedLyrics(lines=lines, raw_lrc=lrc_text)

    tagger = AudioTagger()
    try:
        tagger.write(af, match, lyrics)
        print(f"Tagged: {path.name}")
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


async def _cmd_lyrics(args) -> None:
    """Fetch lyrics for a single file."""
    path = Path(args.file)
    if not path.exists():
        print(f"Error: file not found: {args.file}", file=sys.stderr)
        sys.exit(1)

    from audio_matcher.core.lyrics import LyricsFetcher
    from audio_matcher.core.recognizer import Recognizer

    if args.title and args.artist:
        match = TrackMatch(title=args.title, artist=args.artist)
    else:
        print(f"Identifying: {path.name} ...")
        recognizer = Recognizer()
        match = await recognizer.recognize_file(str(path))
        if match is None:
            print("Could not identify the track. Use --title and --artist to specify manually.")
            sys.exit(1)
        print(f"  → {match.artist} - {match.title}")

    fetcher = LyricsFetcher()
    lyrics = await fetcher.fetch(match)
    if lyrics:
        print(lyrics.raw_lrc)
    else:
        print("No lyrics found.")
        sys.exit(1)


def _interactive_review(results, config: Config) -> None:
    """Simple interactive prompt to edit results before writing."""
    print("\n── Interactive Review ──")
    for r in results:
        # Handle AWAITING_SELECTION files that weren't already resolved.
        if (
            r.status == ProcessingStatus.AWAITING_SELECTION
            and r.match_alternatives
        ):
            selected = _prompt_candidate_selection(r)
            if selected:
                r.match = selected
                r.status = ProcessingStatus.RECOGNIZED
            else:
                continue

        if not r.match:
            continue
        print(f"\n{r.audio_file.path.name}")
        print(f"  Title : {r.match.title}")
        print(f"  Artist: {r.match.artist}")
        print(f"  Album : {r.match.album}")
        action = input("  [Enter=keep, e=edit, s=skip]: ").strip().lower()
        if action == "e":
            new_title = input(f"    Title [{r.match.title}]: ").strip()
            new_artist = input(f"    Artist [{r.match.artist}]: ").strip()
            if new_title:
                r.match.title = new_title
            if new_artist:
                r.match.artist = new_artist
            r.edited = True
        elif action == "s":
            continue
        # Write.
        tagger = AudioTagger(config)
        try:
            tagger.write(r.audio_file, r.match, r.lyrics)
            r.status = ProcessingStatus.TAGGED
            print(f"  ✓ Written")
        except Exception as exc:
            print(f"  ✗ Error: {exc}")


def _prompt_candidate_selection(result: TrackResult) -> TrackMatch | None:
    """Interactive prompt for selecting among fuzzy match candidates.

    Returns the selected TrackMatch, or None if the user skips.
    """
    candidates = result.match_alternatives
    if not candidates:
        return None

    print(f"\n── {result.audio_file.path.name} ──")
    print("  Primary recognition failed. Fuzzy match candidates:")

    # Try Rich table, fall back to plain text.
    try:
        from rich.console import Console
        from rich.table import Table
        console = Console()
        table = Table(show_header=True, box=None)
        table.add_column("#", width=4)
        table.add_column("Title", style="green")
        table.add_column("Artist", style="yellow")
        table.add_column("Album")
        table.add_column("Confidence", justify="right")
        table.add_column("Source")

        for i, c in enumerate(candidates, 1):
            table.add_row(
                str(i),
                c.title,
                c.artist,
                c.album or "—",
                f"{c.confidence:.0%}",
                c.source.value,
            )
        console.print(table)
    except Exception:
        for i, c in enumerate(candidates, 1):
            print(
                f"  [{i}] {c.artist} - {c.title} "
                f"({c.album}) [{c.confidence:.0%}] via {c.source.value}"
            )

    while True:
        choice = input(
            f"  Select [1-{len(candidates)}], m=manual, s=skip: "
        ).strip().lower()

        if choice == "s":
            return None
        elif choice == "m":
            title = input("    Title: ").strip()
            artist = input("    Artist: ").strip()
            if title or artist:
                return TrackMatch(
                    title=title,
                    artist=artist,
                    source=MatchSource.SHAZAM,
                    confidence=1.0,
                )
            return None
        else:
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(candidates):
                    return candidates[idx]
            except ValueError:
                pass
            print(f"  Invalid choice. Enter 1-{len(candidates)}, m, or s.")


def _read_lyrics_input(source: str) -> str:
    """Read lyrics from a file path or return the raw string."""
    p = Path(source)
    if p.exists() and p.is_file():
        return p.read_text(encoding="utf-8")
    return source


if __name__ == "__main__":
    main()
