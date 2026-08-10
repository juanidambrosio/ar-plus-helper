import asyncio
import sys
from datetime import date
from pathlib import Path
from unittest import TestCase, mock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bot.alerts.checker import (
    fetch_calendars,
    matches_for_alert,
    run_daily_check,
    unique_fetch_keys,
)
from bot.alerts.models import Alert
from bot.alerts.notify import format_alert_message
from bot.rank import RankedOffer


def _offer(
    departure: str,
    miles: int,
    taxes: int = 1000,
    cabin: str = "ECONOMY",
) -> RankedOffer:
    return RankedOffer(
        departure=departure,
        miles=miles,
        taxes=taxes,
        cabin_class=cabin,
        stops=0,
        duration_minutes=120,
        seats=4,
        booking_class="X",
        fare_basis="XAWARD",
        score=float(miles * 15 + taxes),
        raw={},
    )


def _alert(**overrides) -> Alert:
    data = dict(
        id="a1",
        user_id="281943056",
        origin="EZE",
        destination="JFK",
        date_min=date(2026, 5, 1),
        date_max=date(2026, 5, 18),
        max_price=50000,
    )
    data.update(overrides)
    return Alert(**data)


class AlertModelTests(TestCase):
    def test_from_doc_parses_mongo_extended_json(self):
        doc = {
            "_id": {"$oid": "698cdfa4ef42c96e7b425f42"},
            "user_id": "281943056",
            "origin": "eze",
            "destination": "jfk",
            "date_min": {"$date": "2026-05-01T00:00:00.000Z"},
            "date_max": {"$date": "2026-05-18T00:00:00.000Z"},
            "max_price": 500000,
            "cabin_type": "ECO",
            "country": "AR",
        }
        alert = Alert.from_doc(doc)
        self.assertIsNotNone(alert)
        assert alert is not None
        self.assertEqual(alert.id, "698cdfa4ef42c96e7b425f42")
        self.assertEqual(alert.origin, "EZE")
        self.assertEqual(alert.destination, "JFK")
        self.assertEqual(alert.date_min, date(2026, 5, 1))
        self.assertEqual(alert.date_max, date(2026, 5, 18))
        self.assertEqual(alert.max_price, 500000)

    def test_from_doc_ignores_legacy_cabin_type(self):
        doc = {
            "_id": "x",
            "user_id": "1",
            "origin": "EZE",
            "destination": "COR",
            "date_min": "2026-09-01",
            "date_max": "2026-09-30",
            "max_price": 10000,
            "cabin_type": "PEC",
        }
        alert = Alert.from_doc(doc)
        self.assertIsNotNone(alert)
        assert alert is not None
        self.assertFalse(hasattr(alert, "cabin_type"))

    def test_from_doc_rejects_inverted_dates(self):
        doc = {
            "user_id": "1",
            "origin": "EZE",
            "destination": "COR",
            "date_min": "2026-10-01",
            "date_max": "2026-09-01",
            "max_price": 10000,
        }
        self.assertIsNone(Alert.from_doc(doc))


class FetchKeyTests(TestCase):
    def test_dedupes_same_route_month(self):
        alerts = [
            _alert(id="1", user_id="u1"),
            _alert(id="2", user_id="u2", max_price=10000),
            _alert(
                id="3",
                user_id="u3",
                date_min=date(2026, 5, 10),
                date_max=date(2026, 6, 5),
            ),
        ]
        keys = unique_fetch_keys(alerts)
        self.assertEqual(
            keys,
            [
                ("EZE", "JFK", 2026, 5),
                ("EZE", "JFK", 2026, 6),
            ],
        )


class MatchFilterTests(TestCase):
    def test_filters_by_date_and_miles(self):
        alert = _alert(max_price=20000)
        key = ("EZE", "JFK", 2026, 5)
        offers_by_key = {
            key: [
                _offer("2026-05-02", 15000),
                _offer("2026-05-03", 25000),  # over max
                _offer("2026-05-20", 10000),  # after date_max
                _offer("2026-04-30", 10000),  # before date_min
                _offer("2026-05-10", 12000),
            ]
        }
        matches = matches_for_alert(alert, offers_by_key, limit=5)
        self.assertEqual(
            [(m.departure, m.miles) for m in matches],
            [("2026-05-10", 12000), ("2026-05-02", 15000)],
        )

    def test_limit_top_n_by_miles(self):
        alert = _alert(max_price=100000)
        key = ("EZE", "JFK", 2026, 5)
        offers_by_key = {
            key: [_offer(f"2026-05-{d:02d}", miles) for d, miles in [
                (1, 50000),
                (2, 10000),
                (3, 20000),
                (4, 15000),
                (5, 30000),
                (6, 12000),
            ]]
        }
        matches = matches_for_alert(alert, offers_by_key, limit=3)
        self.assertEqual([m.miles for m in matches], [10000, 12000, 15000])

    def test_empty_when_no_matches(self):
        alert = _alert(max_price=1000)
        key = ("EZE", "JFK", 2026, 5)
        offers_by_key = {key: [_offer("2026-05-02", 15000)]}
        self.assertEqual(matches_for_alert(alert, offers_by_key), [])


class FetchCalendarsTests(TestCase):
    def test_single_ar_call_per_key(self):
        async def _run():
            client = mock.AsyncMock()
            client.fetch_offers.return_value = {
                "calendarOffers": {
                    "0": [
                        {
                            "departure": "2026-05-05",
                            "offerDetails": {
                                "fare": {"baseFare": 9000, "taxes": 500},
                                "cabinClass": "Economy",
                                "seatAvailability": {"seats": 2},
                                "bookingClass": "X",
                                "fareBasis": "X",
                            },
                            "leg": {"stops": 0, "totalDuration": 600},
                        }
                    ]
                }
            }
            keys = [
                ("EZE", "JFK", 2026, 5),
                ("EZE", "JFK", 2026, 6),
            ]
            results, errors = await fetch_calendars(
                client, keys, mile_value=15.0
            )
            self.assertEqual(errors, 0)
            self.assertEqual(client.fetch_offers.await_count, 2)
            self.assertEqual(len(results[keys[0]]), 1)
            self.assertEqual(results[keys[0]][0].miles, 9000)

        asyncio.run(_run())


class RunDailyCheckTests(TestCase):
    def test_notifies_only_when_matches(self):
        async def _run():
            alert_hit = _alert(id="hit", user_id="111", max_price=20000)
            alert_miss = _alert(id="miss", user_id="222", max_price=1000)
            repo = mock.Mock()
            repo.list_all.return_value = [alert_hit, alert_miss]

            client = mock.AsyncMock()
            client.fetch_offers.return_value = {
                "calendarOffers": {
                    "0": [
                        {
                            "departure": "2026-05-05",
                            "offerDetails": {
                                "fare": {"baseFare": 15000, "taxes": 500},
                                "cabinClass": "Economy",
                                "seatAvailability": {"seats": 2},
                                "bookingClass": "X",
                                "fareBasis": "X",
                            },
                            "leg": {"stops": 0, "totalDuration": 600},
                        }
                    ]
                }
            }

            with mock.patch(
                "bot.alerts.checker.send_telegram_message",
                new_callable=mock.AsyncMock,
            ) as send:
                send.return_value = True
                result = await run_daily_check(
                    repository=repo,
                    client=client,
                    telegram_token="tok",
                    mile_value=15.0,
                )

            self.assertEqual(result.alerts_total, 2)
            self.assertEqual(result.fetch_keys, 1)
            self.assertEqual(result.notified, 1)
            self.assertEqual(result.skipped_empty, 1)
            self.assertEqual(send.await_count, 1)
            args = send.await_args
            self.assertEqual(args.args[1], "111")

        asyncio.run(_run())


class FormatAlertTests(TestCase):
    def test_message_contains_header_and_offer(self):
        alert = _alert()
        text = format_alert_message(alert, [_offer("2026-05-05", 12000)])
        self.assertIn("🔔", text)
        self.assertIn("12000", text)
        self.assertIn("05/05", text)
