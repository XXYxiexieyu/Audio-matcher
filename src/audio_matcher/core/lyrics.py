"""Synced lyrics fetcher — LRCLIB → NetEase → QQ Music fallback chain."""

from __future__ import annotations

import logging
from typing import Optional

from audio_matcher.core.cache import LyricsCache
from audio_matcher.core.config import Config
from audio_matcher.core.models import (
    LyricLine,
    LyricsSource,
    SyncedLyrics,
    TrackMatch,
)

logger = logging.getLogger("audio_matcher.lyrics")


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
                    if self.cache is not None:
                        self.cache.set(match.artist, match.title, result)
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
        params = {
            "track_name": match.title,
            "artist_name": match.artist,
        }
        if match.album:
            params["album_name"] = match.album

        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://lrclib.net/api/search",
                params=params,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                if resp.status != 200:
                    logger.debug("LRCLIB returned %d", resp.status)
                    return None
                data = await resp.json()

        if not isinstance(data, list) or len(data) == 0:
            return None

        # Pick the first result with synced lyrics.
        for entry in data:
            synced = entry.get("syncedLyrics")
            if synced:
                return SyncedLyrics(
                    lines=self._parse_lrc(synced),
                    source=LyricsSource.LRCLIB,
                    raw_lrc=synced,
                )

        return None

    # ── NetEase ──────────────────────────────────────────────────────────

    async def _fetch_netease(self, match: TrackMatch) -> Optional[SyncedLyrics]:
        """Fetch from NetEase Cloud Music (unofficial API)."""
        try:
            import aiohttp
            # Search for the song.
            search_url = "https://music.163.com/api/search/get"
            params = {"s": f"{match.title} {match.artist}", "type": 1, "limit": 5}
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Referer": "https://music.163.com/",
            }
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    search_url, params=params, headers=headers,
                    timeout=aiohttp.ClientTimeout(total=15),
                ) as resp:
                    if resp.status != 200:
                        return None
                    search_data = await resp.json()

            songs = search_data.get("result", {}).get("songs", [])
            if not songs:
                return None

            song_id = songs[0]["id"]

            # Fetch lyrics by song ID.
            lyric_url = "https://music.163.com/api/song/lyric"
            params = {"id": song_id, "lv": 1, "kv": 1, "tv": -1}
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    lyric_url, params=params, headers=headers,
                    timeout=aiohttp.ClientTimeout(total=15),
                ) as resp:
                    if resp.status != 200:
                        return None
                    lyric_data = await resp.json()

            lrc_obj = lyric_data.get("lrc", {})
            raw_lrc = lrc_obj.get("lyric", "")
            if not raw_lrc:
                return None

            return SyncedLyrics(
                lines=self._parse_lrc(raw_lrc),
                source=LyricsSource.NETEASE,
                raw_lrc=raw_lrc,
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
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Referer": "https://y.qq.com/",
            }
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    search_url, params=params, headers=headers,
                    timeout=aiohttp.ClientTimeout(total=15),
                ) as resp:
                    if resp.status != 200:
                        return None
                    search_data = await resp.json()

            songs = search_data.get("data", {}).get("song", {}).get("list", [])
            if not songs:
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
                    lyric_url, params=params, headers=headers,
                    timeout=aiohttp.ClientTimeout(total=15),
                ) as resp:
                    if resp.status != 200:
                        return None
                    lyric_data = await resp.json()

            raw_lrc = lyric_data.get("lyric", "")
            if not raw_lrc:
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
