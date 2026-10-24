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

### POST /api/chat
Natural-language chat endpoint. Accepts `{"message": "..."}` and
parses it into a TravelQuery, then calls the same `plan()` logic
above — no new pricing code, no invented prices.

Example prompts that work:

```text
I have to go from Mumbai to Pune, I landed at 06:00, help me plan
I have to go from Pune to Delhi, budget Rs 9000, help me plan
Plan a trip from Pune to Delhi for 2 people
I have to go from Pune to Delhi next Friday, Rs 9000 max, help me plan
```

Parsing handles, at minimum: city names and codes (Mumbai/BOM,
Pune/PNQ, Delhi/DEL, Dubai as a diaspora origin — Dubai → Mumbai →
Pune is treated as BOM → PNQ), "from X to Y" / "X to Y",
budget (`Rs 9000`, `₹9,000`, `9000 max`), passengers
(`2 people`, `for 2`), nights (`2 nights`), baggage (`20 kg`),
and international arrival (`landed at 06:00`, `arrived 6am` —
sets earliest onward departure to arrival + 4h).

Returns the `/api/plan` response plus `status`, `assistant_text`
(1–2 sentences), `parsed_query` (including a plain-words `plain`
echo), `date_note` and `route_note`.

- If origin/destination cannot be parsed, or the route is not
  BOM → PNQ or PNQ → DEL, it returns `status: "clarification"`
  with a helpful message listing the demo routes, and **no prices**
  — it never invents a price for an unsupported route.
- Date: sample data is fixed to 2026-11-14. Relative dates
  ("tomorrow", "next Friday") are mapped to that sample date and
  the response says so openly in `date_note`.

## Frontend — AI chat interface (maroon and cream)

`frontend/index.html` is one static file (HTML + CSS + JS, no build
step, no external dependencies), served by FastAPI at `/`. The old
form UI was replaced completely with a chat interface.

Colour scheme: maroon `#800020` / dark maroon `#5c0014` for the
header, user bubbles, Send button, chips and top-ranked cards;
cream `#fff8e7` for the page background, assistant bubbles and
cards. Tier badges use maroon/cream shades too, with the text
labels LIVE / INDICATIVE / SAMPLE kept so the tiers stay
distinguishable.

- Header: Bhraman भ्रमण + tagline हर सफ़र, एक कहानी.
- Chat area: user bubbles on the right, assistant bubbles on the
  left with an avatar, a typing indicator while planning, and a
  welcome message on load.
- Input at the bottom: type a natural prompt, Send button, or
  Enter to send (Shift+Enter for a new line).
- Suggestion chips above the input: the three example prompts
  above, which send as chat messages.
- Assistant replies in-chat show: a short plain-language summary,
  the parsed query in plain words, then ranked itinerary cards
  (cheapest first: total INR, door-to-door time, leg
  mode/provider/times, hotel, last-mile, tier badges, breakdown,
  baggage/FTQ notes, deep links), then a REJECTED section when
  applicable (e.g. the 07:05 flight, 06:30 train and 09:15 bus are
  rejected for BOM → PNQ when earliest departure is 10:00 — there
  is no 09:00 flight in the sample data, so the chat shows the
  actual rejected legs from the API rather than inventing one),
  and a graceful no-results message.
- Mobile-friendly: bubbles and cards stack on small screens.

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
curl -X POST http://127.0.0.1:8001/api/chat -H 'Content-Type: application/json' \
  -d '{"message":"I have to go from Mumbai to Pune, I landed at 06:00, help me plan"}'
curl -X POST http://127.0.0.1:8001/api/chat -H 'Content-Type: application/json' \
  -d '{"message":"I have to go from Pune to Delhi, budget Rs 9000, help me plan"}'
curl -X POST http://127.0.0.1:8001/api/chat -H 'Content-Type: application/json' \
  -d '{"message":"I have to go from Pune to Delhi for 2 people"}'
```

Chat UI checks: `GET /` must contain `id="chat"`, `id="msg"`,
`/api/chat` and the typing indicator. The old form UI is gone;
there is no form endpoint in the chat frontend, `/api/plan`
remains available for direct API use.

## Pushing to main (when ready)

This workspace does **not** push automatically. After tests pass,
from a checkout with push access to
`https://github.com/divyanshgangurde/bhraman` on branch `main`:

```bash
git checkout main
git add api.py frontend/index.html README-FRONTEND.md README.md
git status   # confirm only intended files are staged
git commit -m "Replace form UI with maroon-and-cream AI chat frontend + /api/chat (sample data, main)"
git push origin main
```

`requirements.txt` is unchanged in the chat-UI push — it already
includes fastapi and uvicorn from the first frontend push.

Do not push until `pytest` passes and the curl checks above return
ranked results with sensible totals and buffer rejections.
