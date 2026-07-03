"""Concrete BhavcopCache implementations."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from .protocols import BhavcopCache


class FileCache(BhavcopCache):
    """Persist bhavcopy data as CSV files under a local directory."""

    def __init__(self, cache_dir: str | Path):
        self.root = Path(cache_dir).expanduser()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, segment: str, dt: date) -> Path:
        return self.root / f"{segment.lower()}_{dt.isoformat()}_bhav.csv"

    def has(self, segment: str, dt: date) -> bool:
        return self._path(segment, dt).exists()

    def get(self, segment: str, dt: date) -> bytes:
        return self._path(segment, dt).read_bytes()

    def put(self, segment: str, dt: date, data: bytes) -> None:
        self._path(segment, dt).write_bytes(data)


class NullCache(BhavcopCache):
    """No-op cache — every lookup misses and puts are discarded."""

    def has(self, segment: str, dt: date) -> bool:
        return False

    def get(self, segment: str, dt: date) -> bytes:
        raise KeyError(f"NullCache has no entry for {segment}/{dt}")

    def put(self, segment: str, dt: date, data: bytes) -> None:
        pass
