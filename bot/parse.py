import re
from dataclasses import dataclass

QUERY_RE = re.compile(
    r"^([A-Za-z]{3})\s+([A-Za-z]{3})\s+(\d{4})-(\d{2})$"
)


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


def parse_query(text: str) -> FlightQuery | None:
    text = (text or "").strip()
    match = QUERY_RE.match(text)
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
