# AR Plus Helper

Telegram bot that queries Aerolíneas Argentinas AR Plus award offers and returns the best mile deals for a month.

## Setup

1. Python 3.11+ (Homebrew `python3` works).
2. Create a virtualenv and install deps:

```bash
cd ar-plus-helper
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

3. Copy env and headers templates:

```bash
cp .env.example .env
cp headers.example.json config/headers.json
```

4. Set `TELEGRAM_BOT_TOKEN` in `.env` (from [@BotFather](https://t.me/BotFather)).

5. Export browser headers into `config/headers.json` (keys alphabetical):
   - Open [aerolineas.com.ar](https://www.aerolineas.com.ar) and search an award flight.
   - DevTools → Network → the `offers` request to `api.aerolineas.com.ar`.
   - Copy request headers (Cookie, Authorization, any `x-*`, User-Agent, etc.) into `config/headers.json` as a JSON object.

6. Optional: set `AR_MILE_VALUE` (ARS per mile, default `15`) used to rank offers:
   `score = miles * AR_MILE_VALUE + taxes`.

7. Fill real bag rules in `config/baggage_rules.json` when you have them.

## Run

```bash
source .venv/bin/activate
python -m bot.main
```

## Usage

Send a chat message:

```
EZE COR 2026-09
```

Format: `ORIG DEST YYYY-MM`

The bot calls:

`GET /v1/flights/offers?...&flexDates=true&awardBooking=true&leg=EZE-COR-20260916`

and replies with the top 10 offers by ARS value, e.g.:

```
bue cor 2026-09
✈️03/09: 900 + $79K, ECONOMY,directo,🕐2hs,💺9🧳0
```

## Notes

- API returns 401/403 when browser cookies/headers expire — refresh `config/headers.json`.
- EZE/AEP are shown as `bue` in the header.
- Ranking: lowest `miles * CPM + taxes`, then miles, taxes, date.
