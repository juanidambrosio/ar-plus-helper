from dataclasses import dataclass
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


def _as_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


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
