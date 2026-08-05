import json
import logging
from pathlib import Path
from typing import Any

import httpx

from bot.parse import (
    FlightQuery,
    RoundTripQuery,
    YearMonth,
    month_leg,
)

logger = logging.getLogger(__name__)


class ARApiError(Exception):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class ARClient:
    def __init__(
        self,
        base_url: str,
        headers_file: str | Path,
        timeout: float = 30.0,
    ):
        self.base_url = base_url.rstrip("?")
        self.headers_file = Path(headers_file)
        self.timeout = timeout

    def load_headers(self) -> dict[str, str]:
        if not self.headers_file.exists():
            logger.error("Headers file not found: %s", self.headers_file)
            raise ARApiError("Error interno, intentar nuevamente mas tarde")
        with self.headers_file.open(encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            logger.error("Headers file is not a JSON object: %s", self.headers_file)
            raise ARApiError("Error interno, intentar nuevamente mas tarde")
        headers = {str(k): str(v) for k, v in data.items() if v is not None}
        # httpx sets Host/Content-Length; strip hop-by-hop if present
        for drop in ("host", "content-length", "connection", "content-encoding"):
            keys = [k for k in headers if k.lower() == drop]
            for k in keys:
                del headers[k]
        return headers

    def _params_one_way_leg(self, leg: str) -> list[tuple[str, str]]:
        return [
            ("adt", "1"),
            ("inf", "0"),
            ("chd", "0"),
            ("flexDates", "true"),
            ("cabinClass", "Economy"),
            ("flightType", "ONE_WAY"),
            ("awardBooking", "true"),
            ("leg", leg),
        ]

    def _params_round_trip_legs(
        self, outbound_leg: str, return_leg: str
    ) -> list[tuple[str, str]]:
        return [
            ("adt", "1"),
            ("inf", "0"),
            ("chd", "0"),
            ("flexDates", "true"),
            ("cabinClass", "Economy"),
            ("flightType", "ROUND_TRIP"),
            ("awardBooking", "true"),
            ("leg", outbound_leg),
            ("leg", return_leg),
        ]

    async def _get(self, params: list[tuple[str, str]]) -> dict[str, Any]:
        headers = self.load_headers()
        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
            try:
                response = await client.get(self.base_url, params=params, headers=headers)
            except httpx.TimeoutException as exc:
                raise ARApiError(
                    "Error interno, intentar nuevamente mas tarde",
                ) from exc
            except httpx.HTTPError as exc:
                raise ARApiError(
                    "Error interno, intentar nuevamente mas tarde",
                ) from exc

        if response.status_code in (401, 403):
            raise ARApiError(
                "Bloqueado por AR Plus.",
                status_code=response.status_code,
            )
        if response.status_code >= 400:
            raise ARApiError(
                "Error interno, intentar nuevamente mas tarde",
                status_code=response.status_code,
            )

        try:
            payload = response.json()
        except ValueError as exc:
            raise ARApiError(
                "Error interno, intentar nuevamente mas tarde",
            ) from exc
        if not isinstance(payload, dict):
            raise ARApiError("Error interno, intentar nuevamente mas tarde")
        return payload

    async def fetch_offers(self, query: FlightQuery) -> dict[str, Any]:
        return await self._get(self._params_one_way_leg(query.leg))

    async def fetch_round_trip_calendars(
        self, query: RoundTripQuery
    ) -> dict[str, list[dict[str, Any]]]:
        """Fetch month calendars (day-16 legs) and merge outbound/return offers.

        - Months needed by both legs → ROUND_TRIP call (day 16 each leg).
        - Months needed by only one leg → ONE_WAY call for that leg.
        """
        out_months = query.outbound_months()
        ret_months = query.return_months()
        out_set = {(m.year, m.month): m for m in out_months}
        ret_set = {(m.year, m.month): m for m in ret_months}
        common_keys = sorted(set(out_set) & set(ret_set))
        out_only = sorted(set(out_set) - set(ret_set))
        ret_only = sorted(set(ret_set) - set(out_set))

        outbound: list[dict[str, Any]] = []
        returns: list[dict[str, Any]] = []

        for key in common_keys:
            ym = out_set[key]
            out_leg = month_leg(query.origin, query.destination, ym)
            ret_leg = month_leg(query.destination, query.origin, ym)
            logger.info("RT calendar fetch %s / %s", out_leg, ret_leg)
            payload = await self._get(self._params_round_trip_legs(out_leg, ret_leg))
            outbound.extend(_calendar_leg(payload, "0"))
            returns.extend(_calendar_leg(payload, "1"))

        for key in out_only:
            ym = out_set[key]
            leg = month_leg(query.origin, query.destination, ym)
            logger.info("OW outbound calendar fetch %s", leg)
            payload = await self._get(self._params_one_way_leg(leg))
            outbound.extend(_calendar_one_way(payload))

        for key in ret_only:
            ym = ret_set[key]
            leg = month_leg(query.destination, query.origin, ym)
            logger.info("OW return calendar fetch %s", leg)
            payload = await self._get(self._params_one_way_leg(leg))
            returns.extend(_calendar_one_way(payload))

        return {
            "0": _dedupe_offers(outbound),
            "1": _dedupe_offers(returns),
        }


def _calendar_leg(payload: dict[str, Any], leg_key: str) -> list[dict[str, Any]]:
    calendar = payload.get("calendarOffers") or {}
    if not isinstance(calendar, dict):
        return []
    day_offers = calendar.get(leg_key)
    if isinstance(day_offers, list):
        return [o for o in day_offers if isinstance(o, dict)]
    return []


def _calendar_one_way(payload: dict[str, Any]) -> list[dict[str, Any]]:
    calendar = payload.get("calendarOffers") or {}
    offers: list[dict[str, Any]] = []
    if isinstance(calendar, dict):
        # Prefer leg "0"; otherwise flatten all lists
        if "0" in calendar and isinstance(calendar["0"], list):
            return [o for o in calendar["0"] if isinstance(o, dict)]
        for day_offers in calendar.values():
            if isinstance(day_offers, list):
                offers.extend(o for o in day_offers if isinstance(o, dict))
    elif isinstance(calendar, list):
        offers.extend(o for o in calendar if isinstance(o, dict))
    return offers


def _offer_key(offer: dict[str, Any]) -> tuple:
    details = offer.get("offerDetails") or {}
    fare = details.get("fare") or {}
    return (
        str(offer.get("departure") or "")[:10],
        fare.get("baseFare"),
        fare.get("taxes"),
        details.get("cabinClass"),
        (offer.get("leg") or {}).get("stops"),
    )


def _dedupe_offers(offers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple] = set()
    unique: list[dict[str, Any]] = []
    for offer in offers:
        key = _offer_key(offer)
        if key in seen:
            continue
        seen.add(key)
        unique.append(offer)
    return unique
