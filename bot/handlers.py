import logging
from pathlib import Path

from telegram import Update
from telegram.ext import ContextTypes

from bot.ar_client import ARApiError, ARClient
from bot.baggage import BaggageResolver
from bot.format import format_results
from bot.parse import parse_query
from bot.rank import rank_offers

logger = logging.getLogger(__name__)

HELP_TEXT = (
    "Enviá un query de aeropuerto a aeropuerto:\n"
    "`EZE COR 2026-09`\n\n"
    "Formato: `ORIG DEST YYYY-MM`"
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
            "No entendí el query.\nUsá: `EZE COR 2026-09`",
            parse_mode="Markdown",
        )
        return

    cfg = context.application.bot_data
    client: ARClient = cfg["ar_client"]
    baggage: BaggageResolver = cfg["baggage"]
    mile_value: float = cfg["mile_value"]

    await update.message.chat.send_action("typing")
    try:
        payload = await client.fetch_offers(query)
        offers = rank_offers(payload, mile_value=mile_value, limit=10)
        reply = format_results(query, offers, baggage)
        await update.message.reply_text(
            reply,
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
    except ARApiError as exc:
        logger.warning("AR API error: %s", exc)
        await update.message.reply_text(str(exc))
    except Exception:
        logger.exception("Unhandled error for query %s", text)
        await update.message.reply_text("Error inesperado al consultar vuelos.")


def build_bot_data(
    *,
    headers_file: str,
    api_base: str,
    mile_value: float,
    baggage_rules: str | Path,
) -> dict:
    return {
        "ar_client": ARClient(base_url=api_base, headers_file=headers_file),
        "baggage": BaggageResolver(baggage_rules),
        "mile_value": mile_value,
    }
