from html import escape
from urllib.parse import urlencode

from bot.baggage import BaggageResolver
from bot.parse import FlightQuery, display_airport
from bot.rank import RankedOffer

OFFERS_PAGE_BASE = "https://www.aerolineas.com.ar/flights-offers"


def format_taxes(taxes: int) -> str:
    if taxes >= 1000:
        thousands = round(taxes / 1000)
        return f"${thousands}K"
    return f"${taxes}"


def format_duration(minutes: int) -> str:
    if minutes <= 0:
        return "🕐0hs"
    hours = max(1, round(minutes / 60))
    return f"🕐{hours}hs"


def format_stops(stops: int) -> str:
    if stops <= 0:
        return "directo"
    if stops == 1:
        return "1 escala"
    return f"{stops} escalas"


def format_date(departure: str) -> str:
    # YYYY-MM-DD -> DD/MM
    parts = departure.split("-")
    if len(parts) >= 3:
        return f"{parts[2]}/{parts[1]}"
    return departure


def departure_leg_date(departure: str) -> str:
    # YYYY-MM-DD -> YYYYMMDD
    return departure.replace("-", "")[:8]


def offer_page_url(origin: str, destination: str, departure: str) -> str:
    leg = f"{origin.upper()}-{destination.upper()}-{departure_leg_date(departure)}"
    params = {
        "adt": "1",
        "inf": "0",
        "chd": "0",
        "flexDates": "false",
        "cabinClass": "Economy",
        "flightType": "ONE_WAY",
        "awardBooking": "true",
        "leg": leg,
    }
    return f"{OFFERS_PAGE_BASE}?{urlencode(params)}"


def checked_bags_for_cabin(cabin_class: str) -> int:
    return 1 if (cabin_class or "").strip().upper() == "BUSINESS" else 0


def format_offer_line(
    offer: RankedOffer,
    query: FlightQuery,
    baggage: BaggageResolver,
) -> str:
    checked_bags = checked_bags_for_cabin(offer.cabin_class)
    date_label = escape(format_date(offer.departure))
    url = escape(offer_page_url(query.origin, query.destination, offer.departure))
    date_link = f'<a href="{url}">{date_label}</a>'
    return (
        f"✈️{date_link}: {offer.miles} + {format_taxes(offer.taxes)}, "
        f"{escape(offer.cabin_class)},{format_stops(offer.stops)},"
        f"{format_duration(offer.duration_minutes)},"
        f"💺{offer.seats}🧳{checked_bags}"
    )


def format_results(
    query: FlightQuery,
    offers: list[RankedOffer],
    baggage: BaggageResolver,
) -> str:
    origin = display_airport(query.origin)
    dest = display_airport(query.destination)
    header = escape(f"{origin} {dest} {query.year_month}")
    if not offers:
        return f"{header}\nSin ofertas disponibles."
    lines = [header] + [format_offer_line(o, query, baggage) for o in offers]
    return "\n".join(lines)
