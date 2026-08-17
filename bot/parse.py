import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

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
    passengers: int = 1

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
    passengers: int = 1

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


def _parse_passengers(value: str) -> int | None:
    if not value.isdigit():
        return None
    passengers = int(value)
    if 1 <= passengers <= 9:
        return passengers
    return None


def _parse_query_extras(tokens: list[str]) -> int | None:
    passengers = 1
    for token in tokens:
        if not token:
            continue
        pax = _parse_passengers(token)
        if pax is not None:
            passengers = pax
            continue
        return None
    return passengers


def _parse_round_trip_tokens(tokens: list[str]) -> RoundTripQuery | None:
    if len(tokens) < 5:
        return None
    origin, destination, dep_s, ret_s, min_s = tokens[:5]
    if not min_s.startswith("d") or not min_s[1:].isdigit():
        return None
    min_departure = _parse_iso_date(dep_s)
    max_return = _parse_iso_date(ret_s)
    if min_departure is None or max_return is None:
        return None
    if min_departure > max_return:
        return None

    min_days = int(min_s[1:])
    if min_days < 1 or min_days > 90:
        return None

    idx = 5
    max_days: int | None = None
    if len(tokens) > idx and tokens[idx].startswith("D") and tokens[idx][1:].isdigit():
        max_days = int(tokens[idx][1:])
        idx += 1
        if max_days < min_days or max_days > 90:
            return None

    passengers = _parse_query_extras(tokens[idx:])
    if passengers is None:
        return None

    return RoundTripQuery(
        origin=origin.upper(),
        destination=destination.upper(),
        min_departure=min_departure,
        max_return=max_return,
        min_days=min_days,
        max_days=max_days,
        passengers=passengers,
    )


def _parse_one_way_tokens(tokens: list[str]) -> FlightQuery | None:
    if len(tokens) < 3:
        return None
    origin, destination, year_month = tokens[:3]
    year_month_parts = year_month.split("-")
    if len(year_month_parts) != 2:
        return None
    year_s, month_s = year_month_parts
    try:
        year = int(year_s)
        month = int(month_s)
    except ValueError:
        return None
    if month < 1 or month > 12:
        return None

    passengers = _parse_query_extras(tokens[3:])
    if passengers is None:
        return None

    return FlightQuery(
        origin=origin.upper(),
        destination=destination.upper(),
        year=year,
        month=month,
        passengers=passengers,
    )


def parse_query(text: str) -> FlightQuery | RoundTripQuery | None:
    text = (text or "").strip()
    tokens = text.split()
    if not tokens:
        return None

    if len(tokens) >= 5 and tokens[4].startswith("d"):
        parsed = _parse_round_trip_tokens(tokens)
        if parsed is not None:
            return parsed

    return _parse_one_way_tokens(tokens)


def display_airport(code: str) -> str:
    if code.upper() in {"EZE", "AEP"}:
        return "bue"
    return code.lower()


def parse_branded_offers(
    payload: dict[str, Any],
    target_date_str: str,
    calendar_offers_accum: dict[str, list[dict[str, Any]]],
) -> None:
    branded = payload.get("brandedOffers")
    if isinstance(branded, dict):
        for key, flights in branded.items():
            if isinstance(flights, list):
                if key not in calendar_offers_accum:
                    calendar_offers_accum[key] = []
                for flight_option in flights:
                    if not isinstance(flight_option, dict):
                        continue
                    offers = flight_option.get("offers") or []
                    lowest_offer = None
                    for offer in offers:
                        if not isinstance(offer, dict):
                            continue
                        fare = offer.get("fare") or {}
                        base_fare = fare.get("baseFare")
                        if base_fare is None:
                            continue
                        try:
                            base_fare_val = int(base_fare)
                            if base_fare_val <= 0:
                                continue
                        except (TypeError, ValueError):
                            continue
                        if lowest_offer is None:
                            lowest_offer = offer
                        else:
                            current_lowest = lowest_offer.get("fare", {}).get("baseFare", float("inf"))
                            if base_fare_val < current_lowest:
                                lowest_offer = offer
                    if lowest_offer:
                        legs = flight_option.get("legs") or []
                        leg_info = legs[0] if legs else {}
                        segments = leg_info.get("segments") or []
                        departure_time = segments[0].get("departure") if segments else None
                        if not departure_time:
                            departure_time = target_date_str
                        fare = lowest_offer.get("fare") or {}
                        base_fare = fare.get("baseFare")
                        taxes = fare.get("taxes") or 0
                        cabin_class = lowest_offer.get("cabinClass") or "Economy"
                        seat_avail = lowest_offer.get("seatAvailability") or {}
                        seats = seat_avail.get("seats") or 1
                        booking_class = lowest_offer.get("bookingClass") or ""
                        fare_basis = lowest_offer.get("fareBasis") or ""
                        detailed_offer = {
                            "departure": departure_time,
                            "offerDetails": {
                                "fare": {
                                    "baseFare": base_fare,
                                    "taxes": taxes
                                },
                                "cabinClass": cabin_class,
                                "seatAvailability": {
                                    "seats": seats
                                },
                                "bookingClass": booking_class,
                                "fareBasis": fare_basis
                            },
                            "leg": {
                                "stops": leg_info.get("stops") or 0,
                                "totalDuration": leg_info.get("totalDuration") or 0
                            }
                        }
                        calendar_offers_accum[key].append(detailed_offer)
