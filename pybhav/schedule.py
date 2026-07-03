"""NSE bhavcopy publish-time schedule.

Implements the :class:`BhavcopSchedule` strategy that decides which
trading date's bhavcopy is currently downloadable, based on the NSE
publish time of 19:00 IST.

All time-zone and cutoff constants live here — ``client.py`` has zero
knowledge of IST, clocks, or publish times (SRP fix).
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import Callable, Optional

from .protocols import BhavcopCalendar, BhavcopSchedule


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: IST timezone — UTC +05:30
_IST = timezone(timedelta(hours=5, minutes=30))

#: NSE publishes each day's bhavcopy after this time (IST).
#: Changing this constant is the *only* edit required if NSE shifts the
#: publish window — no other file needs to change (OCP).
_BHAVCOPY_CUTOFF: time = time(19, 0)


# ---------------------------------------------------------------------------
# Concrete strategy
# ---------------------------------------------------------------------------

class NSEBhavSchedule(BhavcopSchedule):
    """NSE publish-time strategy: bhavcopy is available after 19:00 IST.

    Applies the following decision rules (all times in IST):

    - Today is a **trading day** AND current time **≥ 19:00** → **today**
    - Before 19:00, weekend, or holiday → **most recent previous trading day**

    This class is injected into :class:`~pybhav.client.NSEBhavcopy` via its
    ``schedule`` constructor kwarg, keeping time logic out of the client
    (Single Responsibility) and making it swappable (Open/Closed + Strategy).

    Args:
        clock: Optional ``Callable[[], datetime]`` that returns the current
               aware datetime in **IST**. Defaults to
               ``lambda: datetime.now(_IST)``.

               Inject a fixed-time callable in tests to avoid any dependency
               on wall-clock time — no ``unittest.mock.patch`` required::

                   IST = timezone(timedelta(hours=5, minutes=30))
                   fixed = lambda: datetime(2025, 6, 9, 20, 0, tzinfo=IST)
                   schedule = NSEBhavSchedule(clock=fixed)

    Examples::

        # Production — clock defaults to now()
        schedule = NSEBhavSchedule()

        # Custom cutoff subclass (OCP extension, no modification)
        class EarlySchedule(NSEBhavSchedule):
            _CUTOFF = time(17, 0)  # hypothetical earlier publish time

            def latest_trading_date(self, calendar):
                now = self._clock()
                today = now.date()
                if calendar.is_trading_day(today) and now.time() >= self._CUTOFF:
                    return today
                return calendar.previous_trading_day(today, inclusive=False)
    """

    def __init__(
        self,
        clock: Optional[Callable[[], datetime]] = None,
    ) -> None:
        #: Callable that returns the current IST datetime.
        self._clock: Callable[[], datetime] = clock or (lambda: datetime.now(_IST))

    def latest_trading_date(self, calendar: BhavcopCalendar) -> date:
        """Return the date of the latest available NSE bhavcopy.

        Args:
            calendar: Calendar used to classify dates as trading / non-trading.
        """
        now_ist = self._clock()
        today = now_ist.date()
        # Strip timezone info for comparison against the naive _BHAVCOPY_CUTOFF
        current_time = now_ist.time().replace(tzinfo=None)

        if calendar.is_trading_day(today) and current_time >= _BHAVCOPY_CUTOFF:
            return today

        # Before cut-off, weekend, or holiday → fall back to last trading day
        return calendar.previous_trading_day(today, inclusive=False)


# ---------------------------------------------------------------------------
# Module-level convenience singleton (default production schedule)
# ---------------------------------------------------------------------------

#: Default schedule instance (real wall-clock, IST).
nse_schedule = NSEBhavSchedule()
