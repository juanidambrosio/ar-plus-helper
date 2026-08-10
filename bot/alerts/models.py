from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any


def as_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, dict) and "$date" in value:
        return as_date(value["$date"])
    if isinstance(value, (int, float)):
        ts = float(value)
        if ts > 1e12:
            ts /= 1000.0
        return datetime.utcfromtimestamp(ts).date()
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            return datetime.fromisoformat(text).date()
        except ValueError:
            pass
        try:
            return datetime.strptime(text[:10], "%Y-%m-%d").date()
        except ValueError:
            return None
    return None


def as_int(value: Any) -> int | None:
    try:
        if value is None:
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def date_to_utc_datetime(value: date) -> datetime:
    return datetime(value.year, value.month, value.day, tzinfo=timezone.utc)


@dataclass(frozen=True)
class Alert:
    """Persisted alert (MongoDB `ar_plus_helper.alerts`)."""

    id: str
    user_id: str
    origin: str
    destination: str
    date_min: date
    date_max: date
    max_price: int
    country: str | None = None

    @classmethod
    def from_doc(cls, doc: dict[str, Any]) -> Alert | None:
        if not isinstance(doc, dict):
            return None

        raw_id = doc.get("_id")
        if raw_id is None:
            alert_id = ""
        elif isinstance(raw_id, dict) and "$oid" in raw_id:
            alert_id = str(raw_id["$oid"])
        else:
            alert_id = str(raw_id)

        user_id = str(doc.get("user_id") or "").strip()
        origin = str(doc.get("origin") or "").strip().upper()
        destination = str(doc.get("destination") or "").strip().upper()
        date_min = as_date(doc.get("date_min"))
        date_max = as_date(doc.get("date_max"))
        max_price = as_int(doc.get("max_price"))
        country = doc.get("country")
        country_s = str(country).strip() if country is not None else None

        if not user_id or len(origin) != 3 or len(destination) != 3:
            return None
        if date_min is None or date_max is None or max_price is None:
            return None
        if date_min > date_max or max_price < 0:
            return None

        return cls(
            id=alert_id,
            user_id=user_id,
            origin=origin,
            destination=destination,
            date_min=date_min,
            date_max=date_max,
            max_price=max_price,
            country=country_s or None,
        )


@dataclass(frozen=True)
class AlertCreate:
    """Validated input for creating an alert (not yet persisted)."""

    origin: str
    destination: str
    date_min: date
    date_max: date
    max_price: int

    @property
    def date_min_dt(self) -> datetime:
        return date_to_utc_datetime(self.date_min)

    @property
    def date_max_dt(self) -> datetime:
        return date_to_utc_datetime(self.date_max)
