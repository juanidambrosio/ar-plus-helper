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

### One-way

```
EZE COR 2026-09
```

Format: `ORIG DEST YYYY-MM`

Calls:

`GET /v1/flights/offers?...&flightType=ONE_WAY&flexDates=true&awardBooking=true&leg=EZE-COR-20260916`

### Round-trip

```
EZE COR 2026-09-01 2026-10-01 d7 D14
```

Format: `ORIG DEST YYYY-MM-DD YYYY-MM-DD dN [DN]`

- First date = minimum outbound departure
- Second date = maximum return departure
- `dN` = minimum days between outbound and return (1–90)
- `DN` = optional maximum days (≤90)

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

`https://www.aerolineas.com.ar/flights-offers?adt=1&inf=0&chd=0&flexDates=false&cabinClass=Economy&flightType=ROUND_TRIP&awardBooking=true&leg=EZE-COR-20260903&leg=COR-EZE-20260915`

## Notes

- API returns 401/403 when browser cookies/headers expire — refresh `config/headers.json`.
- EZE/AEP are shown as `bue` in the header.
- One-way ranking: lowest `miles * CPM + taxes`, then miles, taxes, date.
- Round-trip ranking: lowest combined `(out+ret miles) * CPM + (out+ret taxes)`, then miles, taxes, dates.
