from __future__ import annotations

from bot.alerts.models import AlertCreate
from bot.parse import CABIN_TYPES, _parse_cabin_type, _parse_iso_date

NUEVA_ALERTA_USAGE = (
    "Uso: `/nuevaalerta ORIG DEST DATE_MIN DATE_MAX MAX_PRICE [ECO|PEC]`\n"
    "Ej: `/nuevaalerta EZE MIA 2025-01-01 2025-02-01 100000`\n"
    "Ej: `/nuevaalerta EZE MIA 2025-01-01 2025-02-01 100000 PEC`"
)


def parse_nueva_alerta(args: list[str]) -> AlertCreate | str:
    """Parse /nuevaalerta args. Returns AlertCreate or error message string."""
    if len(args) < 5 or len(args) > 6:
        return NUEVA_ALERTA_USAGE

    origin, destination, date_min_s, date_max_s, price_s = args[:5]
    if len(origin) != 3 or not origin.isalpha():
        return "Origen inválido (3 letras IATA)."
    if len(destination) != 3 or not destination.isalpha():
        return "Destino inválido (3 letras IATA)."

    d_min = _parse_iso_date(date_min_s)
    d_max = _parse_iso_date(date_max_s)
    if d_min is None or d_max is None:
        return "Fechas inválidas. Usá YYYY-MM-DD."
    if d_min > d_max:
        return "date_min no puede ser posterior a date_max."

    try:
        max_price = int(price_s)
    except ValueError:
        return "max_price debe ser un número entero."
    if max_price <= 0:
        return "max_price debe ser mayor a 0."

    cabin_type = "ECO"
    if len(args) == 6:
        cabin = _parse_cabin_type(args[5])
        if cabin is None:
            return f"Cabina inválida. Usá {' o '.join(sorted(CABIN_TYPES))}."
        cabin_type = cabin

    return AlertCreate(
        origin=origin.upper(),
        destination=destination.upper(),
        date_min=d_min,
        date_max=d_max,
        max_price=max_price,
        cabin_type=cabin_type,
    )
