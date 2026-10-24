# Bhraman — Frontend + API (hackathon build, main branch)

Brand: **Bhraman भ्रमण** — हर सफ़र, एक कहानी (Every journey, a story)

This adds a FastAPI API and a single-page frontend on top of the existing
backend in `src/bhraman/`. The backend (state, supervisor, ranker,
explainer, agents, sample providers) is **unchanged** — the API only
wraps `run_pipeline()` and adds display labels. All totals are still
computed by the deterministic, code-only ranker, in INR.

## Layout

```
bhraman/
├── api.py                 # FastAPI app (run target: api:app)
├── frontend/index.html    # Single-page frontend, no build step
├── README-FRONTEND.md     # this file
├── src/bhraman/           # unchanged backend
├── main.py                # original CLI demo (unchanged)
└── requirements.txt       # + fastapi, uvicorn
```

## Run

```bash
cd bhraman
pip install -r requirements.txt
uvicorn api:app --reload
```

Then open:

- Frontend: http://127.0.0.1:8000/
- Health: http://127.0.0.1:8000/health
- Demo presets: http://127.0.0.1:8000/api/demo-presets
- API docs (Swagger): http://127.0.0.1:8000/docs

To run on a different port, e.g. for testing:

```bash
uvicorn api:app --port 8001
```

## Endpoints

### GET /health
`{"status": "ok", "service": "bhraman", "data": "sample/offline, no live APIs"}`

### GET /api/demo-presets
Returns the two demo trips used by the preset buttons:

1. `diaspora-bom-pnq` — Dubai → Mumbai landed 06:00, onward to Pune
   same day. Uses `international_arrival: 2026-11-14T06:00:00`.
2. `pnq-del-budget` — Pune → Delhi, 1 passenger, 1 night,
   `budget_inr: 9000`, `checked_baggage_kg: 20`.

### POST /api/plan
Accepts a `TravelQuery` JSON plus one extra field:

```json
{
  "origin": "BOM",
  "destination": "PNQ",
  "date": "2026-11-14",
  "passengers": 1,
  "nights": 1,
  "budget_inr": null,
  "checked_baggage_kg": 0,
  "earliest_departure": null,
  "international_arrival": "2026-11-14T06:00:00"
}
```

- `international_arrival` is optional. When set, `earliest_departure`
  is auto-set to **arrival + 4 hours** (bags + customs at the first
  Indian airport). It accepts a full ISO datetime or a time-only
  `"06:00"` (combined with `date`). It takes precedence over a
  separately supplied `earliest_departure`.
- Without `international_arrival`, `earliest_departure` may be given
  directly (full ISO datetime or time-only).

Returns ranked itineraries (cheapest door-to-door first), the
explainer `summary`, tier labels, and rejected legs:

```json
{
  "query": { "...effective TravelQuery, with earliest_departure applied..." },
  "international_arrival": "2026-11-14T06:00:00",
  "earliest_departure_applied": "2026-11-14T10:00:00",
  "buffer_applied": true,
  "buffer_note": "...",
  "summary": "BOM → PNQ on 2026-11-14 — 2 option(s)...",
  "ranked": [
    {
      "rank": 1,
      "leg": { "mode": "train", "provider": "...", "depart": "...", "price_inr": 455, "tier": 2, "..." },
      "leg_tier_label": "INDICATIVE",
      "hotel": { "name": "...", "price_per_night_inr": 2200, "..." },
      "ground": { "mode": "metro", "cost_inr": 40, "..." },
      "total_inr": 2695,
      "door_to_door_min": 235,
      "door_to_door_display": "3h 55m",
      "breakdown": { "leg_total_inr": 455, "hotel_total_inr": 2200, "ground_cost_inr": 40 },
      "notes": ["...baggage shortfall if any...", "Foreign Tourist Quota (FTQ): ..."]
    }
  ],
  "rejected": [
    { "leg": { "..." }, "tier_label": "INDICATIVE", "rule": "buffer",
      "reason": "REJECTED by international-arrival buffer: departs ... before earliest allowed ..." }
  ],
  "counts": { "legs_found": 5, "ranked": 2, "rejected": 3 }
}
```

Tier labels: `1 = LIVE`, `2 = INDICATIVE` (offline dataset / sample),
`3 = SAMPLE • Deep-link` (deep-link only, e.g. buses / cabs).
Train notes get a display-only FTQ note in the API response
(foreign tourists: 365 days ahead vs 60 days general, passport +
international mobile OTP, availability INDICATIVE). This note does
not change ranking or prices.

A query with no fitting itinerary returns HTTP 200 with
`"ranked": []` and an explainer summary saying to loosen
budget/buffer — the frontend shows this gracefully, it is not an error.

## Frontend

`frontend/index.html` is one static file (HTML + CSS + JS, no build
step, no external dependencies), served by FastAPI at `/`.

- Header: Bhraman भ्रमण + tagline.
- Form: origin, destination, date, passengers, nights, budget,
  baggage kg, international arrival (optional).
- Preset buttons: Dubai → Mumbai 06:00 → Pune, and
  Pune → Delhi ₹9,000 budget (both also available from
  `/api/demo-presets`).
- Results: ranked cards, cheapest first, showing total INR,
  door-to-door time, leg mode/provider/times, hotel name/price,
  last-mile mode/cost, tier badges, price breakdown, notes
  (baggage shortfall, FTQ for trains), deep links where present,
  and a clear REJECTED / buffer section (e.g. the 07:05 flight,
  06:30 train and 09:15 bus are rejected for BOM → PNQ when
  earliest departure is 10:00 — there is no 09:00 flight in the
  sample data, so the frontend shows the actual rejected legs
  from the API rather than inventing one).
- Mobile-friendly: form and result cards stack on small screens.

## Sample data only — known limitations

- Only two routes exist in `src/bhraman/data/sample_legs.json`:
  **BOM → PNQ** and **PNQ → DEL**, on 2026-11-14. Other routes /
  dates return no results. The date field is accepted but sample
  legs are fixed to 2026-11-14, so changing the date alone will
  not change the legs returned (the ranker still applies).
- No live Duffel / LiteAPI / IRCTC / redBus calls. Duffel and
  LiteAPI adapters in `src/bhraman/providers/` are stubs needing
  API keys. Booking is a deep-link hand-off only.
- The ranker picks the cheapest hotel and cheapest ground option
  for every itinerary (existing backend behaviour); the frontend
  therefore shows one hotel / one last-mile per card, not a
  hotel/ground choice per leg.
- Money: totals in INR, stored/computed as in the original
  design (rupee totals, FX conversion in the ranker where
  applicable). Display conversions in this demo are INR-only
  because sample data is INR-only.
- No authentication, no persistence, no payments / PCI.
  Do not use this demo server for real bookings or real
  traveller data.

## Tests

```bash
pytest
python main.py
```

API smoke checks used for this build (see final report for outputs):

```bash
uvicorn api:app --port 8001 &
curl http://127.0.0.1:8001/health
curl http://127.0.0.1:8001/api/demo-presets
curl -X POST http://127.0.0.1:8001/api/plan -H 'Content-Type: application/json' \
  -d '{"origin":"BOM","destination":"PNQ","date":"2026-11-14","passengers":1,"nights":1,"international_arrival":"2026-11-14T06:00:00"}'
curl -X POST http://127.0.0.1:8001/api/plan -H 'Content-Type: application/json' \
  -d '{"origin":"PNQ","destination":"DEL","date":"2026-11-14","passengers":1,"nights":1,"budget_inr":9000,"checked_baggage_kg":20}'
```

## Pushing to main (when ready)

This workspace does **not** push automatically. After tests pass,
from a checkout with push access to
`https://github.com/divyanshgangurde/bhraman` on branch `main`:

```bash
git checkout main
git add api.py frontend/index.html requirements.txt README-FRONTEND.md README.md
git status   # confirm only intended files are staged
git commit -m "Add Bhraman FastAPI API + single-page frontend (sample data, main)"
git push origin main
```

Do not push until `pytest` passes and the curl checks above return
ranked results with sensible totals and buffer rejections.
