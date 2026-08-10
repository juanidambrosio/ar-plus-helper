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
   - Copy request headers (Cookie, any `x-*`, User-Agent, etc.) into `config/headers.json` as a JSON object.
   - `Authorization` is fetched automatically from the site HTML (`window.__ACCESS_TOKEN__`) and refreshed on 401/403.

6. Set `MONGODB_URI` in `.env` (local or Atlas). DB: `ar_plus_helper`, collection: `alerts`.

7. Optional: set `AR_MILE_VALUE` (ARS per mile, default `15`) used to rank offers:
   `score = miles * AR_MILE_VALUE + taxes`.

8. Fill real bag rules in `config/baggage_rules.json` when you have them.



## Run

```bash
source .venv/bin/activate
python -m bot.main
```

## Usage

### One-way

```
EZE COR 2026-09 1
```

Format: `ORIG DEST YYYY-MM [1-9]`

Calls:

`GET /v1/flights/offers?...&adt=1&flexDates=true&flightType=ONE_WAY&awardBooking=true&leg=EZE-COR-20260916`

### Round-trip

```
EZE COR 2026-09-01 2026-10-01 d7 D14 2
```

Format: `ORIG DEST YYYY-MM-DD YYYY-MM-DD dN [DN] [1-9]`

- First date = minimum outbound departure
- Second date = maximum return departure
- `dN` = minimum days between outbound and return (1–90)
- `DN` = optional maximum days (≤90)
- `1-9` = passengers

Uses day **16** legs (same as one-way) so each call returns a full month calendar:

`GET /v1/flights/offers?...&flightType=ROUND_TRIP&...&leg=EZE-COR-20260916&leg=COR-EZE-20260916`

When the window spans more than one month:

- Months needed by **both** legs → extra `ROUND_TRIP` call (day 16 / day 16 for that month)
- Months needed by **only** outbound or return → `ONE_WAY` call for that leg/month

Pairs every outbound offer with every return inside the `d`/`D` window and ranks by total ARS value.

Example reply:

```
bue cor 2026-09-01→2026-10-01 d7 D14
✈️03/09→15/09: 1800 + $150K
 → 900 + $79K, ECONOMY,directo,🕐2hs,💺9🧳0
 ← 900 + $71K, ECONOMY,directo,🕐2hs,💺5🧳0
```

Date links open the RT offers page for that pair, e.g.:

`https://www.aerolineas.com.ar/flights-offers?adt=1&inf=0&chd=0&flexDates=false&flightType=ROUND_TRIP&awardBooking=true&leg=EZE-COR-20260903&leg=COR-EZE-20260915`

### Alerts

```
/alertas
/nuevaalerta EZE MIA 2025-01-01 2025-02-01 100000
```

- `/alertas` — menu: create, list, delete (inline buttons + confirm)
- `/nuevaalerta ORIG DEST DATE_MIN DATE_MAX MAX_PRICE`
  - stored in MongoDB `ar_plus_helper.alerts` keyed by Telegram `user_id`

### Daily alert checker (Lambda)

```bash
# local
python -m bot.alerts.handler

# deploy (needs serverless + serverless-python-requirements)
export TELEGRAM_BOT_TOKEN=... MONGODB_URI=... AR_HEADERS_JSON="$(cat config/headers.json)"
npx serverless deploy
```

EventBridge cron runs once a day: load alerts → dedupe AR month fetches → filter by date/max miles → Telegram notify top matches.

## Notes

- Bearer token is scraped from the homepage and refreshed on expiry / 401/403. If still blocked, refresh cookies/`x-*` in `config/headers.json`.
- EZE/AEP are shown as `bue` in the header.
- One-way ranking: lowest `miles * CPM + taxes`, then miles, taxes, date.
- Round-trip ranking: lowest combined `(out+ret miles) * CPM + (out+ret taxes)`, then miles, taxes, dates.
