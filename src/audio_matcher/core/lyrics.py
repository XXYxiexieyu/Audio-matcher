"""Synced lyrics fetcher — LRCLIB → NetEase → QQ Music fallback chain."""

from __future__ import annotations

import logging
from typing import Optional

from audio_matcher.core.cache import LyricsCache
from audio_matcher.core.config import Config
from audio_matcher.core.models import (
    LyricLine,
    LyricsLanguage,
    LyricsSource,
    SyncedLyrics,
    TrackMatch,
)
from audio_matcher.core.romaji import lrc_to_romaji

logger = logging.getLogger("audio_matcher.lyrics")

# Common browser-emulation headers for APIs that check User-Agent / Referer.
_API_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
}


class LyricsFetcher:
    """Fetch synced LRC lyrics from online sources.

    Providers are tried in the order specified in config.lyrics_providers.
    """

    def __init__(
        self,
        config: Optional[Config] = None,
        cache: Optional[LyricsCache] = None,
    ) -> None:
        self.config = config or Config()
        self.cache = cache

    async def fetch(self, match: TrackMatch) -> Optional[SyncedLyrics]:
        """Fetch lyrics for *match*, trying providers in order.

        Returns the first successful result, or None.
        """
        if not match.artist or not match.title:
            logger.debug("No artist/title for lyrics lookup")
            return None

        # Cache check.
        if self.cache is not None:
            cached = self.cache.get(match.artist, match.title)
            if cached is not None:
                return cached

        for provider in self.config.lyrics_providers:
            fetcher = getattr(self, f"_fetch_{provider}", None)
            if fetcher is None:
                logger.debug("Unknown lyrics provider: %s", provider)
                continue
            try:
                result = await fetcher(match)
                if result is not None and result.lines:
                    # Romaji post-processing (computed fresh, not cached).
                    language = LyricsLanguage(self.config.lyrics_language)
                    if language in (LyricsLanguage.JAPANESE_ROMAJI, LyricsLanguage.BILINGUAL_ROMAJI):
                        result.romanized_lrc = lrc_to_romaji(result.raw_lrc)
                        if result.romanized_lrc:
                            result.romanized_lines = self._parse_lrc(result.romanized_lrc)
                    if self.cache is not None:
                        self.cache.set(match.artist, match.title, result)
                    logger.info(
                        "Lyrics from %s: %s - %s (%d lines, tl=%s, rom=%s)",
                        provider, match.artist, match.title, len(result.lines),
                        result.has_translation, result.has_romanized,
                    )
                    return result
            except Exception as exc:
                logger.debug("Lyrics provider %s failed: %s", provider, exc)
                continue

        logger.info("No lyrics found for %s - %s", match.artist, match.title)
        return None

    # ── LRCLIB ───────────────────────────────────────────────────────────

    async def _fetch_lrclib(self, match: TrackMatch) -> Optional[SyncedLyrics]:
        """Fetch from LRCLIB (public, no API key).

        https://lrclib.net/api/search
        """
        import aiohttp

        # Search without album — including it makes matching too strict
        # (e.g. Shazam album ≠ LRCLIB album name → 0 results).
        params: dict[str, str] = {
            "track_name": match.title,
            "artist_name": match.artist,
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://lrclib.net/api/search",
                params=params,
                headers=_API_HEADERS,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                if resp.status != 200:
                    logger.debug("LRCLIB returned %d", resp.status)
                    return None
                data = await resp.json()

        if not isinstance(data, list) or len(data) == 0:
            logger.debug("LRCLIB: no results for %s - %s", match.artist, match.title)
            return None

        # Prefer the first result with synced lyrics.
        for entry in data:
            synced = entry.get("syncedLyrics")
            if synced:
                return SyncedLyrics(
                    lines=self._parse_lrc(synced),
                    source=LyricsSource.LRCLIB,
                    raw_lrc=synced,
                )

        # Fallback: use plain (unsynced) lyrics when available.
        for entry in data:
            plain = entry.get("plainLyrics")
            if plain:
                logger.debug("LRCLIB: using plain lyrics (no synced available)")
                return SyncedLyrics(
                    lines=self._parse_plain(plain),
                    source=LyricsSource.LRCLIB,
                    raw_lrc=self._plain_to_lrc(plain),
                )

        logger.debug("LRCLIB: results exist but no lyrics text in any entry")
        return None

    # ── NetEase ──────────────────────────────────────────────────────────

    async def _fetch_netease(self, match: TrackMatch) -> Optional[SyncedLyrics]:
        """Fetch from NetEase Cloud Music (unofficial API)."""
        try:
            import aiohttp

            # Search for the song.
            search_url = "https://music.163.com/api/search/get"
            params = {"s": f"{match.title} {match.artist}", "type": 1, "limit": 5}
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    search_url,
                    params=params,
                    headers={**_API_HEADERS, "Referer": "https://music.163.com/"},
                    timeout=aiohttp.ClientTimeout(total=15),
                ) as resp:
                    if resp.status != 200:
                        return None
                    search_data = await resp.json(content_type=None)

            songs = search_data.get("result", {}).get("songs", [])
            if not songs:
                logger.debug("NetEase: no search results")
                return None

            song_id = songs[0]["id"]

            # Fetch lyrics by song ID.
            lyric_url = "https://music.163.com/api/song/lyric"
            params = {"id": song_id, "lv": 1, "kv": 1, "tv": -1}
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    lyric_url,
                    params=params,
                    headers={**_API_HEADERS, "Referer": "https://music.163.com/"},
                    timeout=aiohttp.ClientTimeout(total=15),
                ) as resp:
                    if resp.status != 200:
                        return None
                    lyric_data = await resp.json(content_type=None)

            lrc_obj = lyric_data.get("lrc", {})
            raw_lrc = lrc_obj.get("lyric", "")
            if not raw_lrc:
                logger.debug("NetEase: no lyric text in response")
                return None

            # Also capture translated lyrics (tlyric) when available.
            tlyric_obj = lyric_data.get("tlyric", {})
            raw_tlyric = tlyric_obj.get("lyric", "")

            return SyncedLyrics(
                lines=self._parse_lrc(raw_lrc),
                source=LyricsSource.NETEASE,
                raw_lrc=raw_lrc,
                translated_lrc=raw_tlyric,
                translated_lines=self._parse_lrc(raw_tlyric) if raw_tlyric else [],
            )
        except Exception:
            return None

    # ── QQ Music ─────────────────────────────────────────────────────────

    async def _fetch_qqmusic(self, match: TrackMatch) -> Optional[SyncedLyrics]:
        """Fetch from QQ Music (unofficial API)."""
        try:
            import aiohttp

            search_url = "https://c.y.qq.com/soso/fcgi-bin/client_search_cp"
            params = {
                "w": f"{match.title} {match.artist}",
                "format": "json",
                "n": 5,
                "t": 0,
            }
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    search_url,
                    params=params,
                    headers={**_API_HEADERS, "Referer": "https://y.qq.com/"},
                    timeout=aiohttp.ClientTimeout(total=15),
                ) as resp:
                    if resp.status != 200:
                        return None
                    # QQ Music search returns application/x-javascript content-type.
                    search_data = await resp.json(content_type=None)

            songs = search_data.get("data", {}).get("song", {}).get("list", [])
            if not songs:
                logger.debug("QQ Music: no search results")
                return None

            song_mid = songs[0]["songmid"]

            # Fetch lyrics by songmid.
            lyric_url = "https://c.y.qq.com/lyric/fcgi-bin/fcg_query_lyric_new.fcg"
            params = {
                "songmid": song_mid,
                "format": "json",
                "nobase64": 1,
                "g_tk": 5381,
            }
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    lyric_url,
                    params=params,
                    headers={**_API_HEADERS, "Referer": "https://y.qq.com/"},
                    timeout=aiohttp.ClientTimeout(total=15),
                ) as resp:
                    if resp.status != 200:
                        return None
                    # QQ Music lyrics returns text/html content-type.
                    lyric_data = await resp.json(content_type=None)

            raw_lrc = lyric_data.get("lyric", "")
            if not raw_lrc:
                logger.debug("QQ Music: no lyric text in response")
                return None

            return SyncedLyrics(
                lines=self._parse_lrc(raw_lrc),
                source=LyricsSource.QQMUSIC,
                raw_lrc=raw_lrc,
            )
        except Exception:
            return None

    # ── LRC Parser ───────────────────────────────────────────────────────

    @staticmethod
    def _parse_lrc(raw: str) -> list[LyricLine]:
        """Parse LRC formatted text into a list of LyricLine objects.

        Handles [mm:ss.xx] and [mm:ss] formats.
        Lines without a timestamp tag are silently skipped.
        """
        import re

        lines: list[LyricLine] = []
        pattern = re.compile(r"\[(\d{1,3}):(\d{2})(?:\.(\d{1,3}))?\]")
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            match = pattern.search(line)
            if match:
                minutes = int(match.group(1))
                seconds = int(match.group(2))
                centiseconds = match.group(3)
                cs = int(centiseconds) if centiseconds else 0
                # Normalise: if 2-digit centiseconds, multiply by 10 for ms.
                if centiseconds and len(centiseconds) == 2:
                    cs *= 10
                elif centiseconds and len(centiseconds) == 1:
                    cs *= 100
                timestamp_ms = minutes * 60000 + seconds * 1000 + cs
                text = pattern.sub("", line).strip()
                lines.append(LyricLine(timestamp_ms=timestamp_ms, text=text))
        return lines

    @staticmethod
    def _parse_plain(raw: str) -> list[LyricLine]:
        """Parse plain (unsynced) lyrics into untimed LyricLine objects."""
        lines: list[LyricLine] = []
        for line in raw.splitlines():
            line = line.strip()
            if line:
                lines.append(LyricLine(timestamp_ms=0, text=line))
        return lines

    @staticmethod
    def _plain_to_lrc(plain: str) -> str:
        """Convert plain text lyrics into unsynced LRC format.

        Each line is prefixed with [00:00.00] so it remains valid LRC
        that can be embedded and displayed by most players.
        """
        result: list[str] = []
        for line in plain.splitlines():
            line = line.strip()
            if line:
                result.append(f"[00:00.00]{line}")
        return "\n".join(result)
