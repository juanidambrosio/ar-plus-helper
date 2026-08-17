import asyncio
import sys
from datetime import date
from pathlib import Path
from unittest import TestCase, mock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bot.ar_client import ARClient, ARApiError
from bot.parse import FlightQuery, RoundTripQuery, parse_query


class ParseQueryTests(TestCase):
    def test_one_way_defaults_to_one_passenger(self):
        query = parse_query("EZE COR 2026-09")

        self.assertIsInstance(query, FlightQuery)
        assert isinstance(query, FlightQuery)
        self.assertEqual(query.passengers, 1)

    def test_one_way_parses_passengers(self):
        query = parse_query("EZE COR 2026-09 2")

        self.assertIsInstance(query, FlightQuery)
        assert isinstance(query, FlightQuery)
        self.assertEqual(query.passengers, 2)

    def test_round_trip_parses_passengers(self):
        query = parse_query("EZE COR 2026-09-01 2026-10-01 d7 D14 3")

        self.assertIsInstance(query, RoundTripQuery)
        assert isinstance(query, RoundTripQuery)
        self.assertEqual(query.passengers, 3)

    def test_round_trip_defaults_to_one_passenger(self):
        query = parse_query("EZE COR 2026-09-01 2026-10-01 d7 D14")

        self.assertIsInstance(query, RoundTripQuery)
        assert isinstance(query, RoundTripQuery)
        self.assertEqual(query.passengers, 1)

    def test_rejects_unknown_token(self):
        self.assertIsNone(parse_query("EZE COR 2026-09 ABC 2"))

    def test_rejects_cabin_token(self):
        self.assertIsNone(parse_query("EZE COR 2026-09 ECO"))
        self.assertIsNone(parse_query("EZE COR 2026-09 PEC 2"))

    def test_rejects_invalid_passengers(self):
        self.assertIsNone(parse_query("EZE COR 2026-09 10"))


class ARClientParamsTests(TestCase):
    def test_fetch_offers_passes_query_to_params_builder(self):
        query = FlightQuery(
            origin="EZE",
            destination="COR",
            year=2026,
            month=9,
            passengers=3,
        )
        client = ARClient(base_url="https://example.com", headers_file="/tmp/headers.json")

        with mock.patch.object(client, "_get", return_value={"ok": True}) as get_mock:
            result = asyncio.run(client.fetch_offers(query))

        self.assertEqual(result, {"ok": True})
        get_mock.assert_awaited_once_with(client._params_one_way_query(query))

    def test_one_way_request_uses_passengers(self):
        query = FlightQuery(
            origin="EZE",
            destination="COR",
            year=2026,
            month=9,
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
                ("flightType", "ONE_WAY"),
                ("awardBooking", "true"),
                ("leg", "EZE-COR-20260916"),
            ],
        )

    def test_round_trip_request_uses_passengers(self):
        query = RoundTripQuery(
            origin="EZE",
            destination="COR",
            min_departure=date(2026, 9, 1),
            max_return=date(2026, 10, 1),
            min_days=7,
            max_days=14,
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
                ("flightType", "ROUND_TRIP"),
                ("awardBooking", "true"),
                ("leg", "EZE-COR-20260916"),
                ("leg", "COR-EZE-20260916"),
            ],
        )


class ARClientRetryTests(TestCase):
    def test_retry_on_500(self):
        client = ARClient(base_url="https://example.com", headers_file="/tmp/headers.json")
        client._auth_headers = mock.AsyncMock(return_value={})
        mock_response_500 = mock.Mock()
        mock_response_500.status_code = 500
        mock_response_200 = mock.Mock()
        mock_response_200.status_code = 200
        mock_response_200.json.return_value = {
            "brandedOffers": {
                "0": [
                    {
                        "legs": [
                            {
                                "segments": [
                                    {"departure": "2026-09-04T06:55:00"}
                                ],
                                "stops": 0,
                                "totalDuration": 135
                            }
                        ],
                        "offers": [
                            {
                                "cabinClass": "Economy",
                                "bookingClass": "P",
                                "fareBasis": "PYSM/YSM",
                                "seatAvailability": {"seats": 9},
                                "fare": {"baseFare": 5000, "taxes": 63917}
                            }
                        ]
                    }
                ]
            }
        }
        call_count = 0
        async def mock_get(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return mock_response_500
            return mock_response_200
        with mock.patch("httpx.AsyncClient.get", new=mock_get):
            params = [
                ("adt", "1"),
                ("flexDates", "true"),
                ("flightType", "ONE_WAY"),
                ("leg", "EZE-COR-20260916")
            ]
            result = asyncio.run(client._get(params))
        self.assertEqual(call_count, 31)
        self.assertIn("calendarOffers", result)
        self.assertIn("0", result["calendarOffers"])
        offers = result["calendarOffers"]["0"]
        self.assertGreater(len(offers), 0)
        detailed_offer = [o for o in offers if o["departure"] == "2026-09-04T06:55:00"]
        self.assertEqual(len(detailed_offer), 1)
        self.assertEqual(detailed_offer[0]["offerDetails"]["fare"]["baseFare"], 5000)
        self.assertEqual(detailed_offer[0]["offerDetails"]["fare"]["taxes"], 63917)
        self.assertEqual(detailed_offer[0]["offerDetails"]["cabinClass"], "Economy")

    def test_no_retry_on_400(self):
        client = ARClient(base_url="https://example.com", headers_file="/tmp/headers.json")
        client._auth_headers = mock.AsyncMock(return_value={})
        call_count_err = 0
        async def mock_get_400(*args, **kwargs):
            nonlocal call_count_err
            call_count_err += 1
            mock_resp = mock.Mock()
            mock_resp.status_code = 400
            return mock_resp
        with mock.patch("httpx.AsyncClient.get", new=mock_get_400):
            params = [
                ("adt", "1"),
                ("flexDates", "true"),
                ("flightType", "ONE_WAY"),
                ("leg", "EZE-COR-20260916")
            ]
            with self.assertRaises(ARApiError) as ctx:
                asyncio.run(client._get(params))
            self.assertEqual(ctx.exception.status_code, 400)
            self.assertEqual(call_count_err, 1)
