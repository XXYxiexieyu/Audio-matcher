"""CLI output formatters using Rich."""

from __future__ import annotations

from audio_matcher.core.models import ProcessingStatus, TrackResult


def print_results_table(results: list[TrackResult]) -> None:
    """Print a Rich table summarising pipeline results."""
    try:
        from rich.console import Console
        from rich.table import Table
    except ImportError:
        _print_results_plain(results)
        return

    console = Console()
    table = Table(title="Audio Matcher — Results", show_lines=False)
    table.add_column("Status", width=8)
    table.add_column("File", style="cyan")
    table.add_column("Title", style="green")
    table.add_column("Artist", style="yellow")
    table.add_column("Album")
    table.add_column("Confidence", justify="right")

    status_icons = {
        ProcessingStatus.TAGGED: "[green]✓[/]",
        ProcessingStatus.RECOGNIZED: "[yellow]~[/]",
        ProcessingStatus.LYRICS_FETCHED: "[yellow]~[/]",
        ProcessingStatus.AWAITING_SELECTION: "[yellow]?[/]",
        ProcessingStatus.ERROR: "[red]✗[/]",
        ProcessingStatus.PENDING: "[dim]?[/]",
    }

    for r in results:
        icon = status_icons.get(r.status, "?")
        if r.match:
            title = r.match.title
            artist = r.match.artist
            album = r.match.album or "—"
            conf = f"{r.match.confidence:.0%}"
        elif r.match_alternatives:
            best = r.match_alternatives[0]
            title = f"? {best.title}"
            artist = f"? {best.artist}"
            album = best.album or "—"
            conf = f"({len(r.match_alternatives)})"
        else:
            title = artist = album = "—"
            conf = "—"
        table.add_row(
            icon,
            r.audio_file.path.name,
            title,
            artist,
            album,
            conf,
        )

    console.print(table)


def _print_results_plain(results: list[TrackResult]) -> None:
    """Fallback plain-text output."""
    print(f"\n{'='*60}")
    print(f"{'Status':8} {'File':20} {'Title':15} {'Artist':15}")
    print(f"{'-'*60}")
    for r in results:
        status = r.status.value[:8]
        fname = r.audio_file.path.name[:20]
        title = (r.match.title or "—")[:15] if r.match else "—"
        artist = (r.match.artist or "—")[:15] if r.match else "—"
        print(f"{status:8} {fname:20} {title:15} {artist:15}")
    print(f"{'='*60}")
