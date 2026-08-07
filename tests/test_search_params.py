import asyncio
import sys
from datetime import date
from pathlib import Path
from unittest import TestCase, mock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bot.ar_client import ARClient
from bot.parse import FlightQuery, RoundTripQuery, parse_query


class ParseQueryTests(TestCase):
    def test_one_way_defaults_to_economy_and_one_passenger(self):
        query = parse_query("EZE COR 2026-09")

        self.assertIsInstance(query, FlightQuery)
        assert isinstance(query, FlightQuery)
        self.assertEqual(query.cabin_type, "ECO")
        self.assertEqual(query.passengers, 1)

    def test_one_way_parses_cabin_and_passengers(self):
        query = parse_query("EZE COR 2026-09 EJE 2")

        self.assertIsInstance(query, FlightQuery)
        assert isinstance(query, FlightQuery)
        self.assertEqual(query.cabin_type, "EJE")
        self.assertEqual(query.passengers, 2)

    def test_one_way_parses_passengers_before_cabin(self):
        query = parse_query("EZE COR 2026-09 2 EJE")

        self.assertIsInstance(query, FlightQuery)
        assert isinstance(query, FlightQuery)
        self.assertEqual(query.cabin_type, "EJE")
        self.assertEqual(query.passengers, 2)

    def test_round_trip_parses_cabin_and_passengers(self):
        query = parse_query("EZE COR 2026-09-01 2026-10-01 d7 D14 EJE 3")

        self.assertIsInstance(query, RoundTripQuery)
        assert isinstance(query, RoundTripQuery)
        self.assertEqual(query.cabin_type, "EJE")
        self.assertEqual(query.passengers, 3)

    def test_round_trip_parses_passengers_before_cabin(self):
        query = parse_query("EZE COR 2026-09-01 2026-10-01 d7 D14 3 EJE")

        self.assertIsInstance(query, RoundTripQuery)
        assert isinstance(query, RoundTripQuery)
        self.assertEqual(query.cabin_type, "EJE")
        self.assertEqual(query.passengers, 3)

    def test_round_trip_defaults_to_economy_and_one_passenger(self):
        query = parse_query("EZE COR 2026-09-01 2026-10-01 d7 D14")

        self.assertIsInstance(query, RoundTripQuery)
        assert isinstance(query, RoundTripQuery)
        self.assertEqual(query.cabin_type, "ECO")
        self.assertEqual(query.passengers, 1)

    def test_rejects_invalid_cabin(self):
        self.assertIsNone(parse_query("EZE COR 2026-09 ABC 2"))

    def test_rejects_invalid_passengers(self):
        self.assertIsNone(parse_query("EZE COR 2026-09 ECO 10"))


class ARClientParamsTests(TestCase):
    def test_fetch_offers_passes_query_to_params_builder(self):
        query = FlightQuery(
            origin="EZE",
            destination="COR",
            year=2026,
            month=9,
            cabin_type="EJE",
            passengers=3,
        )
        client = ARClient(base_url="https://example.com", headers_file="/tmp/headers.json")

        with mock.patch.object(client, "_get", return_value={"ok": True}) as get_mock:
            result = asyncio.run(client.fetch_offers(query))

        self.assertEqual(result, {"ok": True})
        get_mock.assert_awaited_once_with(client._params_one_way_query(query))

    def test_one_way_request_uses_cabin_and_passengers(self):
        query = FlightQuery(
            origin="EZE",
            destination="COR",
            year=2026,
            month=9,
            cabin_type="EJE",
            passengers=3,
        )
        client = ARClient(base_url="https://example.com", headers_file="/tmp/headers.json")

        params = client._params_one_way_query(query)

        self.assertEqual(
            params,
            [
                ("adt", "3"),
                ("inf", "0"),
                ("chd", "0"),
                ("flexDates", "true"),
                ("cabinClass", "Business"),
                ("flightType", "ONE_WAY"),
                ("awardBooking", "true"),
                ("leg", "EZE-COR-20260916"),
            ],
        )

    def test_round_trip_request_uses_cabin_and_passengers(self):
        query = RoundTripQuery(
            origin="EZE",
            destination="COR",
            min_departure=date(2026, 9, 1),
            max_return=date(2026, 10, 1),
            min_days=7,
            max_days=14,
            cabin_type="ECO",
            passengers=1,
        )
        client = ARClient(base_url="https://example.com", headers_file="/tmp/headers.json")

        params = client._params_round_trip_legs(query, "EZE-COR-20260916", "COR-EZE-20260916")

        self.assertEqual(
            params,
            [
                ("adt", "1"),
                ("inf", "0"),
                ("chd", "0"),
                ("flexDates", "true"),
                ("cabinClass", "Economy"),
                ("flightType", "ROUND_TRIP"),
                ("awardBooking", "true"),
                ("leg", "EZE-COR-20260916"),
                ("leg", "COR-EZE-20260916"),
            ],
        )
