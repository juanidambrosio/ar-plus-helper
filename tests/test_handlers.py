import asyncio
import sys
from unittest import TestCase, mock
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import emoji
from bot.handlers import handle_text

class HandlersTests(TestCase):
    def test_handle_text_sends_searching_message(self):
        update = mock.MagicMock()
        update.message.reply_text = mock.AsyncMock()
        update.message.chat.send_action = mock.AsyncMock()
        update.message.text = "EZE COR 2026-09 1"
        
        context = mock.MagicMock()
        context.application.bot_data = {
            "ar_client": mock.AsyncMock(),
            "baggage": mock.MagicMock(),
            "mile_value": 15.0,
        }
        
        context.application.bot_data["ar_client"].fetch_offers.return_value = {
            "brandedOffers": {}
        }
        
        asyncio.run(handle_text(update, context))
        
        expected_status_message = emoji.emojize(":magnifying_glass_tilted_left: Buscando las mejores ofertas...")
        update.message.reply_text.assert_any_call(
            expected_status_message
        )

    def test_handle_text_sends_searching_message_for_round_trip(self):
        update = mock.MagicMock()
        update.message.reply_text = mock.AsyncMock()
        update.message.chat.send_action = mock.AsyncMock()
        update.message.text = "EZE COR 2026-09-01 2026-10-01 d7 D14 2"
        
        context = mock.MagicMock()
        context.application.bot_data = {
            "ar_client": mock.AsyncMock(),
            "baggage": mock.MagicMock(),
            "mile_value": 15.0,
        }
        
        context.application.bot_data["ar_client"].fetch_round_trip_calendars.return_value = ([], [])
        
        asyncio.run(handle_text(update, context))
        
        expected_status_message = emoji.emojize(":magnifying_glass_tilted_left: Buscando las mejores ofertas...")
        update.message.reply_text.assert_any_call(
            expected_status_message
        )
