import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

from bot.alerts.commands import (
    alerts_callback,
    alerts_command,
    nueva_alerta_command,
)
from bot.alerts.repository import AlertRepository
from bot.handlers import build_bot_data, handle_text, help_command, start_command

ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    load_dotenv(ROOT / ".env")

    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        print("Missing TELEGRAM_BOT_TOKEN in .env", file=sys.stderr)
        sys.exit(1)

    mongo_uri = os.getenv("MONGODB_URI", "").strip()
    if not mongo_uri:
        print("Missing MONGODB_URI in .env", file=sys.stderr)
        sys.exit(1)

    headers_file = os.getenv("AR_HEADERS_FILE", "config/headers.json")
    headers_path = Path(headers_file)
    if not headers_path.is_absolute():
        headers_path = ROOT / headers_path

    api_base = os.getenv(
        "AR_API_BASE",
        "https://api.aerolineas.com.ar/v1/flights/offers",
    )
    mile_value = float(os.getenv("AR_MILE_VALUE", "15"))
    baggage_rules = ROOT / "config" / "baggage_rules.json"

    logging.basicConfig(
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        level=logging.WARNING,
    )

    alert_repo = AlertRepository(mongo_uri)
    alert_repo.ensure_indexes()

    app = Application.builder().token(token).build()
    app.bot_data.update(
        build_bot_data(
            headers_file=str(headers_path),
            api_base=api_base,
            mile_value=mile_value,
            baggage_rules=baggage_rules,
            alert_repo=alert_repo,
        )
    )
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("alertas", alerts_command))
    app.add_handler(CommandHandler("nuevaalerta", nueva_alerta_command))
    app.add_handler(CallbackQueryHandler(alerts_callback, pattern=r"^alerts:"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    app.run_polling(allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    main()
