# Bhraman — Multi-Agent Travel Planner for India & the Diaspora

**One question — "Pune to Delhi next Friday, ₹9,000 max" — answered as a full door-to-door comparison: flight vs train vs bus, plus the hotel and the last mile, with the real total for each.**

Three cooperating agents plan the trip over one shared itinerary state:

- **Fare agent** — compares flights, trains and buses for the route, normalised into one schema with total prices.
- **Hotel agent** — finds stays near where you actually arrive (station/airport), not just the city centre.
- **Ground agent** — prices the last mile (metro, auto, cab) so itineraries are compared **door-to-door**, which no existing India travel planner does.

Built for the Indian diaspora as much as domestic travellers: international-arrival buffers, the Foreign Tourist Quota for trains, INR + home-currency totals, and honest labels where data is indicative rather than live.

## Why it's built this way

- **APIs first, web search never as a foundation.** Amadeus self-service was decommissioned in July 2026; Skyscanner and Kiwi are partner-gated; **IRCTC has no public API** and **buses have no public API at all**. The design uses tiered data (live self-serve APIs → offline datasets → deep links) instead of pretending otherwise. Full research: see `ARCHITECTURE.md` references.
- **Code does the math, the LLM does the talking.** A deterministic ranker computes totals, FX, buffers and budget checks. TravelPlanner's 0.6% GPT-4 pass rate is what happens when an LLM plans freely.
- **Memory is Raw-RAG.** Plain retrieval over the user's raw travel history beats complex agentic-memory frameworks on current benchmarks — and it's simpler.

## Project structure

```
bhraman/
├── README.md                  ← you are here
├── ARCHITECTURE.md            ← full design, with justifications
├── main.py                    ← end-to-end demo on sample data (no API keys)
├── requirements.txt
├── .env.example               ← optional API keys (demo runs without them)
├── src/bhraman/
│   ├── state.py               ← Pydantic models: query, options, itinerary state
│   ├── config.py              ← settings from environment
│   ├── supervisor.py          ← LangGraph graph + plain fallback runner
│   ├── agents/
│   │   ├── fare.py            ← Fare agent
│   │   ├── hotel.py           ← Hotel agent
│   │   └── ground.py          ← Ground agent
│   ├── providers/
│   │   ├── base.py            ← provider interfaces
│   │   ├── fake.py            ← sample-data providers (offline, default)
│   │   ├── duffel.py          ← flights adapter (stub — needs API key)
│   │   └── liteapi.py         ← hotels adapter (stub — needs API key)
│   ├── ranker.py              ← deterministic ranker: totals, buffers, budget
│   ├── memory.py              ← Raw-RAG memory over raw history
│   ├── explainer.py           ← turns ranked itineraries into plain language
│   └── data/                  ← sample legs / hotels / ground options (JSON)
├── evals/
│   ├── golden_queries.json    ← fixed test trips with pass/fail expectations
│   └── run_evals.py           ← constraint-satisfaction harness
└── tests/                     ← ranker rules, pipeline, memory
```

## Run the demo

```bash
pip install -r requirements.txt
python main.py        # two demo trips, ranked door-to-door, no keys needed
pytest                # unit tests
python evals/run_evals.py   # golden-query checks
```

The demo runs entirely on the sample-data providers. To go live, copy
`.env.example` to `.env`, add keys, and implement the adapter stubs in
`providers/` — every live source sits behind the same interface as the fakes.

## Data sources (MVP)

| Leg | Live (self-serve) | Offline fallback |
|---|---|---|
| Flights | Duffel (test mode), SerpApi Google Flights | Kaggle fare datasets |
| Trains | RapidAPI listings (info only — *indicative*) | DataMeet timetable (~417K entries) |
| Buses | — none exists — | curated sample + redBus/AbhiBus deep links |
| Hotels | LiteAPI sandbox, Duffel Stays | OYO / Cities42 datasets |
| Ground | Google Maps Routes, Delhi GTFS | OSRM / sample data |

Booking is always a deep-link hand-off in the MVP. Transacting (IRCTC
partner access, redBus partner programme, payments) is a partnership
problem, not a code problem — see the verdict in `ARCHITECTURE.md`.

## Status

Scaffold: architecture, shared state, three agents, deterministic ranker,
Raw-RAG memory, provider interfaces with working offline providers, eval
harness, tests. Live adapters are interface-complete stubs.
