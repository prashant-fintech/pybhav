# pybhav

**pybhav** is a Python library for downloading NSE (National Stock Exchange of India) bhavcopy files — the official end-of-day market data for Indian equities, futures & options, currency derivatives, and SME equities.

[![Python](https://img.shields.io/badge/python-3.9%2B-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![PyPI](https://img.shields.io/pypi/v/pybhav)](https://pypi.org/project/pybhav/)

---

## Features

- **Single-day and date-range downloads** — get one or many trading days as a pandas DataFrame
- **Save to disk** — download the raw CSV file directly to a local directory
- **Automatic caching** — re-uses previously downloaded files; no redundant network calls
- **Retry with backoff** — handles transient HTTP errors gracefully
- **NSE session management** — warms up the required cookies and browser headers automatically
- **Extensible by design** — swap the cache, fetcher, or parser via constructor injection (SOLID)

---

## Installation

```bash
pip install pybhav
```

**Requirements:** Python 3.9+, `requests >= 2.28`, `pandas >= 1.5`

---

## Quick Start

```python
from pybhav import NSEBhavcopy

nse = NSEBhavcopy()

# Single trading day → pandas DataFrame
df = nse.get("2025-06-30")
print(df.head())

# Date range → combined DataFrame (weekends/holidays skipped automatically)
df = nse.get_range("2025-06-01", "2025-06-30")

# Save raw CSV to disk → returns the Path to the written file
path = nse.download("2025-06-30", dest="./data/")
print(path)  # data/cm_2025-06-30_bhav.csv
```

---

## Market Segments

Pass the `segment` keyword to any method. Defaults to `"CM"` (equities).

| Key   | Market                  | Exchange Section          |
|-------|-------------------------|---------------------------|
| `CM`  | Capital Market          | NSE Equities (default)    |
| `FO`  | Futures & Options       | NSE Derivatives           |
| `CD`  | Currency Derivatives    | NSE Currency              |
| `SME` | SME Equities            | NSE Emerge (SME platform) |

```python
# Futures & Options bhavcopy
df = nse.get("2025-06-30", segment="FO")

# Currency derivatives for a range
df = nse.get_range("2025-06-01", "2025-06-30", segment="CD")
```

---

## API Reference

### `NSEBhavcopy(cache_dir, retries, timeout, *, cache, fetcher, parser)`

The main client. All arguments are optional.

| Parameter   | Type                  | Default              | Description                                                    |
|-------------|-----------------------|----------------------|----------------------------------------------------------------|
| `cache_dir` | `str \| Path \| None` | `~/.pybhav_cache`    | Directory for the file cache. Pass `None` to disable caching.  |
| `retries`   | `int`                 | `3`                  | Number of retry attempts on transient HTTP failures.           |
| `timeout`   | `int`                 | `30`                 | HTTP request timeout in seconds.                               |
| `cache`     | `BhavcopCache`        | `FileCache`          | Override the cache with any `BhavcopCache` implementation.     |
| `fetcher`   | `BhavcopFetcher`      | `NSEHttpFetcher`     | Override the HTTP layer with any `BhavcopFetcher`.             |
| `parser`    | `BhavcopParser`       | `NSECsvParser`       | Override the parser with any `BhavcopParser`.                  |

---

### `nse.get(dt, segment="CM") → pd.DataFrame`

Download bhavcopy for a single trading date and return it as a DataFrame.

```python
from datetime import date

df = nse.get("2025-06-30")           # string date
df = nse.get(date(2025, 6, 30))      # date object
df = nse.get("2025-06-30", segment="FO")
```

Raises `BhavcopNotAvailable` if the date is a weekend, public holiday, or future date.

---

### `nse.get_range(start, end, segment="CM", skip_errors=True) → pd.DataFrame`

Download bhavcopy for a date range and concatenate into a single DataFrame.

A `_date` column is added to each row indicating which trading date it came from.

```python
df = nse.get_range("2025-06-01", "2025-06-30")

# Raise on the first unavailable date instead of skipping
df = nse.get_range("2025-06-01", "2025-06-30", skip_errors=False)
```

| Parameter     | Default | Description                                                     |
|---------------|---------|-----------------------------------------------------------------|
| `start`       | —       | Start date, inclusive. `date` object or `"YYYY-MM-DD"` string. |
| `end`         | —       | End date, inclusive.                                            |
| `segment`     | `"CM"`  | Market segment.                                                 |
| `skip_errors` | `True`  | Skip weekends/holidays silently. Set `False` to raise instead.  |

Returns an empty `DataFrame` if no data was found for any date in the range.

---

### `nse.download(dt, segment="CM", dest=".") → Path`

Download the bhavcopy CSV for a single date to a local directory.

```python
path = nse.download("2025-06-30")                        # saves to current dir
path = nse.download("2025-06-30", segment="FO", dest="./data/fo/")
print(path)  # ./data/fo/fo_2025-06-30_bhav.csv
```

The destination directory is created if it does not exist. Returns the `Path` of the written file. If the data is already in the local cache, no network request is made.

---

## Configuration Examples

### Disable caching

```python
nse = NSEBhavcopy(cache_dir=None)
```

### Custom cache directory and longer timeout

```python
nse = NSEBhavcopy(cache_dir="/mnt/data/bhav_cache", timeout=60)
```

### More retries for flaky networks

```python
nse = NSEBhavcopy(retries=5)
```

---

## Extending pybhav

pybhav is built on three abstract base classes exported from the package. Implement any of them and inject it into `NSEBhavcopy` to replace the default behaviour without touching library code.

### Custom cache (e.g. in-memory)

```python
from datetime import date
from pybhav import BhavcopCache, NSEBhavcopy

class MemoryCache(BhavcopCache):
    def __init__(self):
        self._store: dict[tuple, bytes] = {}

    def has(self, segment: str, dt: date) -> bool:
        return (segment, dt) in self._store

    def get(self, segment: str, dt: date) -> bytes:
        return self._store[(segment, dt)]

    def put(self, segment: str, dt: date, data: bytes) -> None:
        self._store[(segment, dt)] = data

nse = NSEBhavcopy(cache=MemoryCache())
```

### Custom parser (e.g. select and rename columns)

```python
import io
import pandas as pd
from pybhav import BhavcopParser, NSEBhavcopy

class SlimParser(BhavcopParser):
    _COLS = {"SYMBOL": "symbol", "OPEN": "open", "HIGH": "high",
             "LOW": "low", "CLOSE": "close", "TOTTRDQTY": "volume"}

    def parse(self, data: bytes) -> pd.DataFrame:
        df = pd.read_csv(io.BytesIO(data))
        df.columns = df.columns.str.strip()
        return df[[c for c in self._COLS if c in df.columns]].rename(columns=self._COLS)

nse = NSEBhavcopy(parser=SlimParser())
df = nse.get("2025-06-30")
print(df.columns.tolist())  # ['symbol', 'open', 'high', 'low', 'close', 'volume']
```

### Custom fetcher (e.g. load from local files for backtesting)

```python
from datetime import date
from pathlib import Path
from pybhav import BhavcopFetcher, NSEBhavcopy
from pybhav.exceptions import BhavcopNotAvailable

class LocalFileFetcher(BhavcopFetcher):
    def __init__(self, directory: str):
        self._dir = Path(directory)

    def fetch(self, segment: str, dt: date) -> bytes:
        path = self._dir / f"{segment.lower()}_{dt.isoformat()}_bhav.csv"
        if not path.exists():
            raise BhavcopNotAvailable(f"No local file for {segment}/{dt}")
        return path.read_bytes()

nse = NSEBhavcopy(fetcher=LocalFileFetcher("./local_data/"))
df = nse.get("2025-06-30")
```

---

## Error Handling

All exceptions inherit from `PybhavError`.

| Exception              | When raised                                                       |
|------------------------|-------------------------------------------------------------------|
| `BhavcopNotAvailable`  | The requested date is a weekend, holiday, or future date (HTTP 404). |
| `DownloadError`        | HTTP request failed after all retry attempts.                     |
| `SessionError`         | Could not establish a valid NSE session (homepage unreachable).   |

```python
from pybhav import NSEBhavcopy, BhavcopNotAvailable, DownloadError

nse = NSEBhavcopy()
try:
    df = nse.get("2025-06-28")  # Saturday
except BhavcopNotAvailable:
    print("Market closed on this date.")
except DownloadError as e:
    print(f"Network error: {e}")
```

---

## Architecture

pybhav follows SOLID principles. The main components are:

```
NSEBhavcopy (client.py)
├── BhavcopCache   →  FileCache / NullCache       (cache.py)
├── BhavcopFetcher →  NSEHttpFetcher              (fetcher.py)
│                        └── _ZipExtractor
└── BhavcopParser  →  NSECsvParser                (parser.py)

Supporting utilities
├── session.py     —  NSE cookie/header warm-up
├── urls.py        —  URL construction per segment
└── exceptions.py  —  PybhavError hierarchy
```

Each dependency is an abstract base class (`protocols.py`). The defaults work out of the box; pass your own implementation to any of the three constructor kwargs to override.

---

## Development

```bash
# Clone and install in editable mode with dev dependencies
git clone https://github.com/prashant-fintech/pybhav.git
cd pybhav
pip install -e ".[dev]"

# Run tests
pytest
```

---

## License

MIT © [Prashant Singh](https://github.com/prashant-fintech)
