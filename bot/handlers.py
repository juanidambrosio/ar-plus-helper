from pathlib import Path

from telegram import Update
from telegram.ext import ContextTypes

from bot.alerts.repository import AlertRepository
from bot.ar_client import ARApiError, ARClient
from bot.baggage import BaggageResolver
from bot.format import format_results, format_round_trip_results
from bot.parse import FlightQuery, RoundTripQuery, parse_query
from bot.rank import rank_offers, rank_round_trips

HELP_TEXT = (
    "Enviá un query de aeropuerto a aeropuerto:\n"
    "`EZE COR 2026-09 1`\n"
    "`EZE COR 2026-09-01 2026-10-01 d7 D14 2`\n\n"
    "Ida: `ORIG DEST YYYY-MM [1-9]`\n"
    "Ida y vuelta: `ORIG DEST YYYY-MM-DD YYYY-MM-DD dN [DN] [1-9]`\n"
    "`1-9` = cantidad de pasajeros\n\n"
    "Alertas: `/alertas` · `/nuevaalerta ORIG DEST DATE_MIN DATE_MAX MAX_PRICE`"
)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message:
        await update.message.reply_text(HELP_TEXT, parse_mode="Markdown")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message:
        await update.message.reply_text(HELP_TEXT, parse_mode="Markdown")


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text:
        return

    text = update.message.text.strip()
    if text.startswith("/"):
        return

    query = parse_query(text)
    if query is None:
        await update.message.reply_text(
            "No entendí el query.\n"
            "Ida: `EZE COR 2026-09 1`\n"
            "Ida y vuelta: `EZE COR 2026-09-01 2026-10-01 d7 D14 2`",
            parse_mode="Markdown",
        )
        return

    cfg = context.application.bot_data
    client: ARClient = cfg["ar_client"]
    baggage: BaggageResolver = cfg["baggage"]
    mile_value: float = cfg["mile_value"]

    await update.message.chat.send_action("typing")
    try:
        if isinstance(query, RoundTripQuery):
            calendars = await client.fetch_round_trip_calendars(query)
            pairs = rank_round_trips(
                calendars,
                min_departure=query.min_departure,
                max_return=query.max_return,
                min_days=query.min_days,
                max_days=query.max_days,
                mile_value=mile_value,
                limit=10,
            )
            reply = format_round_trip_results(query, pairs, baggage)
        else:
            assert isinstance(query, FlightQuery)
            payload = await client.fetch_offers(query)
            offers = rank_offers(payload, mile_value=mile_value, limit=10)
            reply = format_results(query, offers, baggage)
        await update.message.reply_text(
            reply,
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
        print(text, flush=True)
    except ARApiError as exc:
        if exc.status_code in (401, 403):
            msg = "Bloqueado por AR Plus."
        else:
            msg = str(exc) or "Error interno, intentar nuevamente mas tarde"
        await update.message.reply_text(msg)
        print(f"{text} -> error: {msg}", flush=True)
    except Exception as exc:
        await update.message.reply_text(
            "Error interno, intentar nuevamente mas tarde"
        )
        print(f"{text} -> error: {exc}", flush=True)


def build_bot_data(
    *,
    headers_file: str,
    api_base: str,
    mile_value: float,
    baggage_rules: str | Path,
    alert_repo: AlertRepository | None = None,
) -> dict:
    data = {
        "ar_client": ARClient(base_url=api_base, headers_file=headers_file),
        "baggage": BaggageResolver(baggage_rules),
        "mile_value": mile_value,
    }
    if alert_repo is not None:
        data["alert_repo"] = alert_repo
    return data
