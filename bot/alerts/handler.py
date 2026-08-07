from __future__ import annotations

import asyncio
import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any

from bot.alerts.checker import run_daily_check
from bot.alerts.repository import AlertRepository
from bot.ar_client import ARClient
from bot.token import AccessTokenProvider

logger = logging.getLogger(__name__)


def _configure_logging() -> None:
    level_name = (os.getenv("LOG_LEVEL") or "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    logging.basicConfig(
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        level=level,
        force=True,
    )


def _resolve_headers_file() -> str:
    """Prefer AR_HEADERS_JSON (Lambda secret); fall back to AR_HEADERS_FILE path."""
    raw_json = (os.getenv("AR_HEADERS_JSON") or "").strip()
    if raw_json:
        data = json.loads(raw_json)
        if not isinstance(data, dict):
            raise RuntimeError("AR_HEADERS_JSON must be a JSON object")
        tmp = Path(tempfile.gettempdir()) / "ar_headers.json"
        tmp.write_text(json.dumps(data), encoding="utf-8")
        return str(tmp)

    headers_file = (os.getenv("AR_HEADERS_FILE") or "config/headers.json").strip()
    path = Path(headers_file)
    if not path.is_absolute():
        # Lambda package root or local repo root
        candidates = [
            Path.cwd() / path,
            Path(__file__).resolve().parents[2] / path,
        ]
        for candidate in candidates:
            if candidate.exists():
                return str(candidate)
        return str(candidates[0])
    return str(path)


async def _async_handler() -> dict[str, Any]:
    token = (os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
    if not token:
        raise RuntimeError("Missing TELEGRAM_BOT_TOKEN")

    mongo_uri = (os.getenv("MONGODB_URI") or "").strip()
    if not mongo_uri:
        raise RuntimeError("Missing MONGODB_URI")

    api_base = (
        os.getenv("AR_API_BASE")
        or "https://api.aerolineas.com.ar/v1/flights/offers"
    ).strip()
    mile_value = float(os.getenv("AR_MILE_VALUE") or "15")
    match_limit = int(os.getenv("ALERT_MATCH_LIMIT") or "5")
    headers_file = _resolve_headers_file()

    repository = AlertRepository(mongo_uri)
    client = ARClient(
        base_url=api_base,
        headers_file=headers_file,
        token_provider=AccessTokenProvider(),
    )
    try:
        result = await run_daily_check(
            repository=repository,
            client=client,
            telegram_token=token,
            mile_value=mile_value,
            match_limit=match_limit,
        )
    finally:
        repository.close()

    return {
        "ok": True,
        "alerts_total": result.alerts_total,
        "fetch_keys": result.fetch_keys,
        "fetch_errors": result.fetch_errors,
        "notified": result.notified,
        "skipped_empty": result.skipped_empty,
        "notify_errors": result.notify_errors,
    }


def handler(event: dict[str, Any] | None = None, context: Any = None) -> dict[str, Any]:
    """AWS Lambda entrypoint (EventBridge scheduled)."""
    _configure_logging()
    logger.info("alert checker invoked event_keys=%s", list((event or {}).keys()))
    return asyncio.run(_async_handler())


def main() -> None:
    """Local CLI: python -m bot.alerts.handler"""
    from dotenv import load_dotenv

    root = Path(__file__).resolve().parents[2]
    load_dotenv(root / ".env")
    _configure_logging()
    result = asyncio.run(_async_handler())
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
