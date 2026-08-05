from dataclasses import dataclass
from datetime import date, datetime
from typing import Any


@dataclass
class RankedOffer:
    departure: str
    miles: int
    taxes: int
    cabin_class: str
    stops: int
    duration_minutes: int
    seats: int
    booking_class: str
    fare_basis: str
    score: float
    raw: dict[str, Any]


@dataclass
class RankedRoundTrip:
    outbound: RankedOffer
    return_offer: RankedOffer
    miles: int
    taxes: int
    score: float


def _as_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _parse_date(value: str) -> date | None:
    try:
        return datetime.strptime(value[:10], "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def extract_offers(payload: dict[str, Any]) -> list[dict[str, Any]]:
    calendar = payload.get("calendarOffers") or {}
    offers: list[dict[str, Any]] = []
    if isinstance(calendar, dict):
        for day_offers in calendar.values():
            if isinstance(day_offers, list):
                offers.extend(day_offers)
    elif isinstance(calendar, list):
        offers.extend(calendar)
    return offers


def extract_leg_offers(payload: dict[str, Any], leg_key: str) -> list[dict[str, Any]]:
    calendar = payload.get("calendarOffers") or {}
    if not isinstance(calendar, dict):
        return []
    day_offers = calendar.get(leg_key)
    if isinstance(day_offers, list):
        return [o for o in day_offers if isinstance(o, dict)]
    return []


def normalize_offer(offer: dict[str, Any], mile_value: float) -> RankedOffer | None:
    if offer.get("soldOut"):
        return None

    details = offer.get("offerDetails") or {}
    fare = details.get("fare") or {}
    seats_info = details.get("seatAvailability") or {}
    leg = offer.get("leg") or {}

    miles = _as_int(fare.get("baseFare"))
    if miles <= 0:
        return None

    taxes = _as_int(fare.get("taxes"))
    departure = offer.get("departure") or ""
    if not departure:
        segments = leg.get("segments") or []
        if segments:
            dep = segments[0].get("departure") or ""
            departure = dep[:10] if dep else ""
    if not departure:
        return None

    cabin = (details.get("cabinClass") or "Economy").upper()
    stops = _as_int(leg.get("stops"))
    duration = _as_int(leg.get("totalDuration"))
    seats = _as_int(seats_info.get("seats"))
    booking_class = (details.get("bookingClass") or "").strip()
    fare_basis = (details.get("fareBasis") or "").strip()
    score = miles * float(mile_value) + taxes

    return RankedOffer(
        departure=departure[:10],
        miles=miles,
        taxes=taxes,
        cabin_class=cabin,
        stops=stops,
        duration_minutes=duration,
        seats=seats,
        booking_class=booking_class,
        fare_basis=fare_basis,
        score=score,
        raw=offer,
    )


def rank_offers(
    payload: dict[str, Any],
    mile_value: float,
    limit: int = 10,
) -> list[RankedOffer]:
    ranked: list[RankedOffer] = []
    for offer in extract_offers(payload):
        if not isinstance(offer, dict):
            continue
        normalized = normalize_offer(offer, mile_value)
        if normalized is not None:
            ranked.append(normalized)
    ranked.sort(key=lambda o: (o.score, o.miles, o.taxes, o.departure))
    return ranked[:limit]


def _normalize_leg_list(
    raw_offers: list[dict[str, Any]],
    mile_value: float,
    *,
    min_date: date | None = None,
    max_date: date | None = None,
) -> list[RankedOffer]:
    ranked: list[RankedOffer] = []
    for offer in raw_offers:
        if not isinstance(offer, dict):
            continue
        normalized = normalize_offer(offer, mile_value)
        if normalized is None:
            continue
        dep = _parse_date(normalized.departure)
        if dep is None:
            continue
        if min_date is not None and dep < min_date:
            continue
        if max_date is not None and dep > max_date:
            continue
        ranked.append(normalized)
    return ranked


def rank_round_trips(
    calendars: dict[str, list[dict[str, Any]]],
    *,
    min_departure: date,
    max_return: date,
    min_days: int,
    max_days: int | None,
    mile_value: float,
    limit: int = 10,
) -> list[RankedRoundTrip]:
    outbound = _normalize_leg_list(
        calendars.get("0") or [],
        mile_value,
        min_date=min_departure,
        max_date=max_return,
    )
    returns = _normalize_leg_list(
        calendars.get("1") or [],
        mile_value,
        min_date=min_departure,
        max_date=max_return,
    )

    pairs: list[RankedRoundTrip] = []
    for out in outbound:
        out_date = _parse_date(out.departure)
        if out_date is None:
            continue
        for ret in returns:
            ret_date = _parse_date(ret.departure)
            if ret_date is None:
                continue
            trip_days = (ret_date - out_date).days
            if trip_days < min_days:
                continue
            if max_days is not None and trip_days > max_days:
                continue
            miles = out.miles + ret.miles
            taxes = out.taxes + ret.taxes
            score = miles * float(mile_value) + taxes
            pairs.append(
                RankedRoundTrip(
                    outbound=out,
                    return_offer=ret,
                    miles=miles,
                    taxes=taxes,
                    score=score,
                )
            )

    pairs.sort(
        key=lambda p: (
            p.score,
            p.miles,
            p.taxes,
            p.outbound.departure,
            p.return_offer.departure,
        )
    )
    return pairs[:limit]
