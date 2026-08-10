from __future__ import annotations

import logging
from datetime import date, datetime
from html import escape

import httpx

from bot.alerts.models import Alert, AlertCreate
from bot.format import format_date, format_leg_details, offer_page_url
from bot.parse import display_airport
from bot.rank import RankedOffer

logger = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org"


def _fmt_date(value: date | datetime | str | None) -> str:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if value is None:
        return "?"
    return str(value)[:10]


def format_alert_line(alert: Alert | AlertCreate) -> str:
    return (
        f"{alert.origin}→{alert.destination} "
        f"{_fmt_date(alert.date_min)}→{_fmt_date(alert.date_max)} "
        f"≤{alert.max_price}"
    )


def format_alerts_list(alerts: list[Alert]) -> str:
    if not alerts:
        return "No tenés alertas."
    lines = [f"• {format_alert_line(a)}" for a in alerts]
    return "Tus alertas:\n" + "\n".join(lines)


def format_alert_message(
    alert: Alert,
    offers: list[RankedOffer],
    *,
    passengers: int = 1,
) -> str:
    origin = display_airport(alert.origin)
    dest = display_airport(alert.destination)
    header = escape(f"🔔 {origin}→{dest} · ≤{alert.max_price} millas")
    lines = [header]
    for offer in offers:
        date_label = escape(format_date(offer.departure))
        url = escape(
            offer_page_url(
                alert.origin,
                alert.destination,
                offer.departure,
                passengers,
            )
        )
        date_link = f'<a href="{url}">{date_label}</a>'
        lines.append(f"✈️{date_link}: {format_leg_details(offer)}")
    return "\n".join(lines)


async def send_telegram_message(
    token: str,
    chat_id: str,
    text: str,
    *,
    timeout: float = 30.0,
) -> bool:
    url = f"{TELEGRAM_API}/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(url, json=payload)
        if response.status_code >= 400:
            logger.warning(
                "telegram send failed chat_id=%s status=%s body=%s",
                chat_id,
                response.status_code,
                response.text[:300],
            )
            return False
        data = response.json()
        if not data.get("ok", False):
            logger.warning(
                "telegram send not ok chat_id=%s body=%s",
                chat_id,
                response.text[:300],
            )
            return False
        return True
    except httpx.HTTPError as exc:
        logger.warning("telegram send error chat_id=%s err=%s", chat_id, exc)
        return False
