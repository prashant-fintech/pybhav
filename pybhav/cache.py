"""Local file cache keyed by (segment, date)."""

from datetime import date
from pathlib import Path


class Cache:
    def __init__(self, cache_dir: str | Path):
        self.root = Path(cache_dir).expanduser()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, segment: str, dt: date) -> Path:
        return self.root / f"{segment.lower()}_{dt.isoformat()}_bhav.csv"

    def has(self, segment: str, dt: date) -> bool:
        return self._path(segment, dt).exists()

    def get(self, segment: str, dt: date) -> bytes:
        return self._path(segment, dt).read_bytes()

    def put(self, segment: str, dt: date, csv_bytes: bytes) -> None:
        self._path(segment, dt).write_bytes(csv_bytes)
