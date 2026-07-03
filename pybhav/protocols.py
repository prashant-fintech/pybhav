"""Abstract base classes for pybhav's extensibility points."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date

import pandas as pd


class BhavcopCache(ABC):
    """Interface for a bhavcopy data cache keyed by (segment, date)."""

    @abstractmethod
    def has(self, segment: str, dt: date) -> bool: ...

    @abstractmethod
    def get(self, segment: str, dt: date) -> bytes: ...

    @abstractmethod
    def put(self, segment: str, dt: date, data: bytes) -> None: ...


class BhavcopFetcher(ABC):
    """Interface for fetching raw bhavcopy CSV bytes."""

    @abstractmethod
    def fetch(self, segment: str, dt: date) -> bytes: ...


class BhavcopParser(ABC):
    """Interface for parsing raw bhavcopy bytes into a DataFrame."""

    @abstractmethod
    def parse(self, data: bytes) -> pd.DataFrame: ...
