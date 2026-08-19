from html import escape
from urllib.parse import urlencode

from bot.baggage import BaggageResolver
from bot.parse import FlightQuery, RoundTripQuery, display_airport
from bot.rank import RankedOffer, RankedRoundTrip

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


def offer_page_url(
    origin: str,
    destination: str,
    departure: str,
    passengers: int,
) -> str:
    leg = f"{origin.upper()}-{destination.upper()}-{departure_leg_date(departure)}"
    params = [
        ("adt", str(passengers)),
        ("inf", "0"),
        ("chd", "0"),
        ("flexDates", "false"),
        ("flightType", "ONE_WAY"),
        ("awardBooking", "true"),
        ("leg", leg),
    ]
    return f"{OFFERS_PAGE_BASE}?{urlencode(params)}"


def round_trip_offer_page_url(
    origin: str,
    destination: str,
    outbound_departure: str,
    return_departure: str,
    passengers: int,
) -> str:
    out_leg = (
        f"{origin.upper()}-{destination.upper()}-"
        f"{departure_leg_date(outbound_departure)}"
    )
    ret_leg = (
        f"{destination.upper()}-{origin.upper()}-"
        f"{departure_leg_date(return_departure)}"
    )
    params = [
        ("adt", str(passengers)),
        ("inf", "0"),
        ("chd", "0"),
        ("flexDates", "false"),
        ("flightType", "ROUND_TRIP"),
        ("awardBooking", "true"),
        ("leg", out_leg),
        ("leg", ret_leg),
    ]
    return f"{OFFERS_PAGE_BASE}?{urlencode(params)}"


def format_cabin_type(cabin_class: str, booking_class: str) -> str:
    cabin = (cabin_class or "").strip().upper()
    booking = (booking_class or "").strip().upper()
    if cabin == "BUSINESS":
        if booking == "Z":
            return "PREMIUM ECONOMY"
        return "BUSINESS"
    return cabin


def checked_bags_for_offer(cabin_class: str, booking_class: str) -> int:
    cabin = (cabin_class or "").strip().upper().replace(" ", "")
    if cabin in {"PREMIUMECONOMY", "BUSINESS"}:
        return 1
    return 1 if (booking_class or "").strip().upper() == "X" else 0


def format_leg_details(offer: RankedOffer) -> str:
    cabin_type = format_cabin_type(offer.cabin_class, offer.booking_class)
    checked_bags = checked_bags_for_offer(cabin_type, offer.booking_class)
    return (
        f"{offer.miles} + {format_taxes(offer.taxes)}, "
        f"{escape(cabin_type)},{format_stops(offer.stops)},"
        f"{format_duration(offer.duration_minutes)},"
        f"💺{offer.seats}🧳{checked_bags}"
    )


def format_offer_line(
    offer: RankedOffer,
    query: FlightQuery,
    baggage: BaggageResolver,
) -> str:
    date_label = escape(format_date(offer.departure))
    url = escape(offer_page_url(query.origin, query.destination, offer.departure, query.passengers))
    date_link = f'<a href="{url}">{date_label}</a>'
    return f"✈️{date_link}: {format_leg_details(offer)}"


def format_results(
    query: FlightQuery,
    offers: list[RankedOffer],
    baggage: BaggageResolver,
) -> str:
    origin = display_airport(query.origin)
    dest = display_airport(query.destination)
    header = escape(f"{origin} {dest} {query.year_month}")
    if not offers:
        return "No se encontraron ofertas para este tramo."
    lines = [header] + [format_offer_line(o, query, baggage) for o in offers]
    return "\n".join(lines)


def format_round_trip_line(
    pair: RankedRoundTrip,
    query: RoundTripQuery,
    baggage: BaggageResolver,
) -> str:
    out_label = escape(format_date(pair.outbound.departure))
    ret_label = escape(format_date(pair.return_offer.departure))
    url = escape(
        round_trip_offer_page_url(
            query.origin,
            query.destination,
            pair.outbound.departure,
            pair.return_offer.departure,
            query.passengers,
        )
    )
    dates_link = f'<a href="{url}">{out_label}→{ret_label}</a>'
    return (
        f"✈️{dates_link}: {pair.miles} + {format_taxes(pair.taxes)}\n"
        f" → {format_leg_details(pair.outbound)}\n"
        f" ← {format_leg_details(pair.return_offer)}"
    )


def format_round_trip_results(
    query: RoundTripQuery,
    pairs: list[RankedRoundTrip],
    baggage: BaggageResolver,
) -> str:
    origin = display_airport(query.origin)
    dest = display_airport(query.destination)
    header = escape(f"{origin} {dest} {query.window_label}")
    if not pairs:
        return "No se encontraron ofertas para este tramo."
    blocks = [format_round_trip_line(p, query, baggage) for p in pairs]
    return "\n".join([header] + blocks)
