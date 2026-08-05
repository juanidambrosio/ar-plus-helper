import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from telegram.ext import Application, CommandHandler, MessageHandler, filters

from bot.handlers import build_bot_data, handle_text, help_command, start_command

ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    load_dotenv(ROOT / ".env")

    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        print("Missing TELEGRAM_BOT_TOKEN in .env", file=sys.stderr)
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
        level=logging.INFO,
    )

    app = Application.builder().token(token).build()
    app.bot_data.update(
        build_bot_data(
            headers_file=str(headers_path),
            api_base=api_base,
            mile_value=mile_value,
            baggage_rules=baggage_rules,
        )
    )
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    logging.getLogger(__name__).info("Starting AR Plus helper bot")
    app.run_polling(allowed_updates=["message"])


if __name__ == "__main__":
    main()
