from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from bot.alerts.models import Alert
from bot.alerts.notify import format_alert_message, send_telegram_message
from bot.alerts.repository import AlertRepository
from bot.ar_client import ARApiError, ARClient
from bot.parse import FlightQuery, YearMonth, months_spanning
from bot.rank import RankedOffer, normalize_offer

logger = logging.getLogger(__name__)

FetchKey = tuple[str, str, int, int]  # origin, dest, year, month


@dataclass(frozen=True)
class CheckResult:
    alerts_total: int
    fetch_keys: int
    fetch_errors: int
    notified: int
    skipped_empty: int
    notify_errors: int


def alert_months(alert: Alert) -> list[YearMonth]:
    return months_spanning(alert.date_min, alert.date_max)


def unique_fetch_keys(alerts: list[Alert]) -> list[FetchKey]:
    keys: set[FetchKey] = set()
    for alert in alerts:
        for ym in alert_months(alert):
            keys.add(
                (
                    alert.origin,
                    alert.destination,
                    ym.year,
                    ym.month,
                )
            )
    return sorted(keys)


def _parse_departure(value: str) -> date | None:
    try:
        return datetime.strptime(value[:10], "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def normalize_calendar(
    payload: dict[str, Any],
    mile_value: float,
) -> list[RankedOffer]:
    from bot.rank import extract_offers

    ranked: list[RankedOffer] = []
    for offer in extract_offers(payload):
        if not isinstance(offer, dict):
            continue
        normalized = normalize_offer(offer, mile_value)
        if normalized is not None:
            ranked.append(normalized)
    return ranked


async def fetch_calendars(
    client: ARClient,
    keys: list[FetchKey],
    *,
    mile_value: float,
    passengers: int = 1,
) -> tuple[dict[FetchKey, list[RankedOffer]], int]:
    results: dict[FetchKey, list[RankedOffer]] = {}
    errors = 0
    for key in keys:
        origin, dest, year, month = key
        query = FlightQuery(
            origin=origin,
            destination=dest,
            year=year,
            month=month,
            passengers=passengers,
        )
        try:
            payload = await client.fetch_offers(query)
            results[key] = normalize_calendar(payload, mile_value)
        except ARApiError as exc:
            errors += 1
            logger.warning("AR fetch failed key=%s err=%s", key, exc)
            results[key] = []
        except Exception as exc:  # noqa: BLE001 — isolate per-key failures
            errors += 1
            logger.exception("AR fetch error key=%s err=%s", key, exc)
            results[key] = []
    return results, errors


def matches_for_alert(
    alert: Alert,
    offers_by_key: dict[FetchKey, list[RankedOffer]],
    *,
    limit: int = 5,
) -> list[RankedOffer]:
    matched: list[RankedOffer] = []
    seen: set[tuple[str, int, int]] = set()
    for ym in alert_months(alert):
        key: FetchKey = (
            alert.origin,
            alert.destination,
            ym.year,
            ym.month,
        )
        for offer in offers_by_key.get(key, []):
            dep = _parse_departure(offer.departure)
            if dep is None:
                continue
            if dep < alert.date_min or dep > alert.date_max:
                continue
            if offer.miles > alert.max_price:
                continue
            dedupe = (offer.departure, offer.miles, offer.taxes)
            if dedupe in seen:
                continue
            seen.add(dedupe)
            matched.append(offer)

    matched.sort(key=lambda o: (o.miles, o.taxes, o.departure))
    return matched[:limit]


async def run_daily_check(
    *,
    repository: AlertRepository,
    client: ARClient,
    telegram_token: str,
    mile_value: float = 15.0,
    match_limit: int = 5,
    passengers: int = 1,
) -> CheckResult:
    alerts = repository.list_all()
    if not alerts:
        logger.info("no alerts found")
        return CheckResult(0, 0, 0, 0, 0, 0)

    keys = unique_fetch_keys(alerts)
    offers_by_key, fetch_errors = await fetch_calendars(
        client,
        keys,
        mile_value=mile_value,
        passengers=passengers,
    )

    notified = 0
    skipped_empty = 0
    notify_errors = 0

    for alert in alerts:
        matches = matches_for_alert(
            alert, offers_by_key, limit=match_limit
        )
        if not matches:
            skipped_empty += 1
            continue
        text = format_alert_message(alert, matches, passengers=passengers)
        ok = await send_telegram_message(telegram_token, alert.user_id, text)
        if ok:
            notified += 1
        else:
            notify_errors += 1

    result = CheckResult(
        alerts_total=len(alerts),
        fetch_keys=len(keys),
        fetch_errors=fetch_errors,
        notified=notified,
        skipped_empty=skipped_empty,
        notify_errors=notify_errors,
    )
    logger.info("daily check done %s", result)
    return result
