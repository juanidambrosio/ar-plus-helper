import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta

ONE_WAY_RE = re.compile(
    r"^([A-Za-z]{3})\s+([A-Za-z]{3})\s+(\d{4})-(\d{2})$"
)
ROUND_TRIP_RE = re.compile(
    r"^([A-Za-z]{3})\s+([A-Za-z]{3})\s+"
    r"(\d{4}-\d{2}-\d{2})\s+(\d{4}-\d{2}-\d{2})\s+"
    r"d(\d+)(?:\s+D(\d+))?$"
)


@dataclass(frozen=True)
class YearMonth:
    year: int
    month: int

    @property
    def leg_date(self) -> str:
        return f"{self.year:04d}{self.month:02d}16"

    def contains(self, d: date) -> bool:
        return d.year == self.year and d.month == self.month


def months_spanning(start: date, end: date) -> list[YearMonth]:
    if start > end:
        return []
    months: list[YearMonth] = []
    y, m = start.year, start.month
    while (y, m) <= (end.year, end.month):
        months.append(YearMonth(y, m))
        if m == 12:
            y, m = y + 1, 1
        else:
            m += 1
    return months


def month_leg(origin: str, destination: str, ym: YearMonth) -> str:
    return f"{origin}-{destination}-{ym.leg_date}"


@dataclass(frozen=True)
class FlightQuery:
    origin: str
    destination: str
    year: int
    month: int

    @property
    def year_month(self) -> str:
        return f"{self.year:04d}-{self.month:02d}"

    @property
    def leg_date(self) -> str:
        return f"{self.year:04d}{self.month:02d}16"

    @property
    def leg(self) -> str:
        return f"{self.origin}-{self.destination}-{self.leg_date}"


@dataclass(frozen=True)
class RoundTripQuery:
    origin: str
    destination: str
    min_departure: date
    max_return: date
    min_days: int
    max_days: int | None

    @property
    def max_outbound(self) -> date:
        # Latest outbound that can still meet min_days before max_return
        return self.max_return - timedelta(days=self.min_days)

    @property
    def min_return_date(self) -> date:
        # Earliest return that can still meet min_days after min_departure
        return self.min_departure + timedelta(days=self.min_days)

    def outbound_months(self) -> list[YearMonth]:
        end = self.max_outbound
        if end < self.min_departure:
            return []
        return months_spanning(self.min_departure, end)

    def return_months(self) -> list[YearMonth]:
        start = self.min_return_date
        if start > self.max_return:
            return []
        return months_spanning(start, self.max_return)

    @property
    def window_label(self) -> str:
        base = (
            f"{self.min_departure.isoformat()}→{self.max_return.isoformat()} "
            f"d{self.min_days}"
        )
        if self.max_days is not None:
            return f"{base} D{self.max_days}"
        return base


def _parse_iso_date(value: str) -> date | None:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def parse_query(text: str) -> FlightQuery | RoundTripQuery | None:
    text = (text or "").strip()

    rt = ROUND_TRIP_RE.match(text)
    if rt:
        origin, destination, dep_s, ret_s, min_s, max_s = rt.groups()
        min_departure = _parse_iso_date(dep_s)
        max_return = _parse_iso_date(ret_s)
        if min_departure is None or max_return is None:
            return None
        if min_departure > max_return:
            return None

        min_days = int(min_s)
        if min_days < 1 or min_days > 90:
            return None
        max_days = int(max_s) if max_s is not None else None
        if max_days is not None:
            if max_days < min_days or max_days > 90:
                return None

        return RoundTripQuery(
            origin=origin.upper(),
            destination=destination.upper(),
            min_departure=min_departure,
            max_return=max_return,
            min_days=min_days,
            max_days=max_days,
        )

    match = ONE_WAY_RE.match(text)
    if not match:
        return None
    origin, destination, year_s, month_s = match.groups()
    year = int(year_s)
    month = int(month_s)
    if month < 1 or month > 12:
        return None
    return FlightQuery(
        origin=origin.upper(),
        destination=destination.upper(),
        year=year,
        month=month,
    )


def display_airport(code: str) -> str:
    if code.upper() in {"EZE", "AEP"}:
        return "bue"
    return code.lower()
