"""In-memory per–API-key usage counters (keyed by SHA-256 of the client secret)."""

from __future__ import annotations

import asyncio
import hashlib
from dataclasses import dataclass, field


def api_key_fingerprint(token: str) -> str:
    """Stable identifier for a client API key (same digest as rate-limit key_func)."""
    return hashlib.sha256(token.strip().encode()).hexdigest()


@dataclass
class _KeyStats:
    process_audio_requests: int = 0
    audio_bytes_transcribed: int = 0
    full_epcr_successes: int = 0


@dataclass
class UsageTracker:
    """Thread/async-safe counters; resets on process restart."""

    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    _by_fp: dict[str, _KeyStats] = field(default_factory=dict)

    async def record_process_audio_request(self, client_api_key: str) -> None:
        fp = api_key_fingerprint(client_api_key)
        async with self._lock:
            s = self._by_fp.setdefault(fp, _KeyStats())
            s.process_audio_requests += 1

    async def record_transcription(self, client_api_key: str, audio_byte_len: int) -> None:
        fp = api_key_fingerprint(client_api_key)
        async with self._lock:
            s = self._by_fp.setdefault(fp, _KeyStats())
            s.audio_bytes_transcribed += audio_byte_len

    async def record_full_epcr_success(self, client_api_key: str) -> None:
        fp = api_key_fingerprint(client_api_key)
        async with self._lock:
            s = self._by_fp.setdefault(fp, _KeyStats())
            s.full_epcr_successes += 1

    async def snapshot_rows(self) -> list[dict[str, int | str]]:
        async with self._lock:
            rows: list[dict[str, int | str]] = []
            for fp in sorted(self._by_fp):
                s = self._by_fp[fp]
                rows.append(
                    {
                        "key_fingerprint_sha256": fp,
                        "process_audio_requests": s.process_audio_requests,
                        "audio_bytes_transcribed": s.audio_bytes_transcribed,
                        "full_epcr_successes": s.full_epcr_successes,
                    }
                )
            return rows
