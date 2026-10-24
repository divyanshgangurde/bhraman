# Bhraman (India / Diaspora) — Revised Architecture

Revision inputs: API/dataset research (24 Oct 2026) + five research-radar papers
(Raw-RAG vs agentic memory, OpenDS-World, DiffResearch, Self-HPO, Kimi K3.1 Pro).
Each choice below carries its justification. Nothing here relies on an API that
turned out to be partner-gated or decommissioned.

## Shape

```
                        ┌─────────────────────────────┐
   user query ────────► │  SUPERVISOR (LangGraph)     │
                        │  intent parse → fan-out     │
                        └──────┬───────────┬──────────┘
              parallel (speculative, see §3)  │
                        ┌──────▼───┐ ┌─────▼────┐ ┌───▼────────┐
                        │ FARE     │ │ HOTEL    │ │ GROUND     │
                        │ agent    │ │ agent    │ │ agent      │
                        └──────┬───┘ └─────┬────┘ └───┬────────┘
                               └──────┬────┴──────────┘
                        ┌─────────────▼───────────────┐
                        │  SHARED ITINERARY STATE     │  (Pydantic, one object)
                        │  legs + hotels + ground +   │
                        │  totals, tier tags, buffers │
                        └─────────────┬───────────────┘
                        ┌─────────────▼───────────────┐
                        │  DETERMINISTIC RANKER       │  code only — no LLM math
                        │  door-to-door totals, FX,   │
                        │  buffers, budget filters    │
                        └─────────────┬───────────────┘
                        ┌─────────────▼───────────────┐
                        │  EXPLAINER (LLM)            │  narrates ranker output,
                        │  diaspora guidance, FTQ etc │  never invents prices
                        └─────────────────────────────┘

   Cross-cutting: Raw-RAG memory (§2) · tiered data access (§4) ·
   provider adapters with offline fakes (§6) · eval harness (§7) ·
   Self-HPO improvement loop, Phase 2 (§8)
```

## 1. Orchestration — LangGraph supervisor, shared state

- A LangGraph graph with one supervisor node and three specialist agents.
  Specialists write ONLY their slice of a single Pydantic `ItineraryState`
  (legs / hotels / ground options + provenance). No agent-to-agent chat.
- **Why LangGraph:** graph control is deterministic, it checkpoints state,
  and it supports human-in-the-loop approval before any booking handoff.
  CrewAI demos faster but gives weaker control; AutoGen's free conversation
  is non-deterministic; Google ADK ties you to GCP.
- **Why one shared typed state:** prices, times and constraints stay in one
  auditable object; every option carries its source tier (see §4) so the UI
  can label "live price" vs "indicative" honestly.

## 2. Memory — Raw-RAG over raw history (radar: Raw-RAG paper)

- Store the user's raw history as-is: past conversations, past itineraries,
  stated preferences. Retrieve with dense embeddings + a reranker; feed the
  reader LLM the raw passages.
- **NO** agentic-memory framework (no mutation, no learned memory graph).
- **Justification:** the paper shows naive RAG over raw history beat complex
  agentic memory systems on 6 of 7 benchmark settings; raw evidence also
  preserves exact facts (a fare quoted earlier, "window seat", "no red-eye")
  that transformed memory stores lose. Simpler to build, better measured
  results — rare combination.

## 3. Latency — speculative parallel fan-out (radar: DiffResearch / dFast)

- DiffResearch's dFast extracts sub-queries from intermediate states before
  generation finishes (~2x on decomposition alone). Our equivalent:
  the supervisor parses route + dates from the FIRST intent pass and fires
  Fare, Hotel and Ground searches **in parallel immediately**, using
  provisional arrival windows for hotel/ground; when fare results land, the
  windows are refined and only the affected slices re-run.
- **Justification:** multi-step planning latency is the known bottleneck of
  research/planning agents; the three searches are independent until the
  ranker stage. Sequential agent chains would multiply wait time by ~3.

## 4. Data layer — strict tiers (radar: OpenDS-World)

Best frontier model scores 39% on live-web multi-step search (OpenDS-World).
So web search is never a foundation here. Every data need resolves in order:

| Tier | Source | Use |
|---|---|---|
| 1 — live APIs (self-serve only) | Duffel (flights), SerpApi Google Flights (search-only, 250 free/mo), LiteAPI (hotels), RapidAPI train listings (info), Google Maps Routes/Places | primary |
| 2 — offline datasets | DataMeet railway timetable (~417K entries), Kaggle flight-fare data, OYO / Cities42 hotel sets | fallback + offline demo |
| 3 — deep links | redBus / AbhiBus / 12Go (buses), Uber / Ola (rides), ixigo/ConfirmTkt (train booking) | hand-off where no API exists |
| 4 — web search | last resort only, output flagged UNVERIFIED in state + UI | never for prices presented as real |

Excluded entirely (verified gated/dead): Amadeus self-service
(decommissioned Jul 2026), Skyscanner (partner-only), Kiwi Tequila
(invite-only), MakeMyTrip (no public API), IRCTC booking (authorised
partners only), redBus API (partner programme).

## 5. Per-agent design

- **Fare agent.** Queries flights (Duffel test mode; SerpApi fallback),
  trains (RapidAPI info + DataMeet timetable; availability labeled
  *indicative* — no public IRCTC API exists), buses (curated sample +
  FlixBus GTFS where present; deep links for booking). Normalises everything
  into one `LegOption` schema: mode, depart/arrive, duration, **total price
  incl. taxes/fees**, baggage, refundability, source tier.
- **Hotel agent.** LiteAPI sandbox primary (Duffel Stays alternate); OYO /
  Cities42 datasets as offline fallback. Filters by distance to the arrival
  station/airport using Ground agent data, not just city centre.
- **Ground agent.** Google Maps Routes (free caps) or OSRM/OpenTripPlanner;
  Delhi GTFS (DTC + DMRC, static + realtime) where available; cab deep links.
  Outputs last-mile **time + cost per arrival point** — this is what lets the
  ranker price the *whole door-to-door trip*, the comparison nobody else
  (ixigo, Myra, global planners) currently does for India.

## 6. Deterministic ranker + provider adapters (software improvements)

- **Ranker is pure code:** totals, FX conversion (stored in INR paise;
  display conversion stamped with rate + date), budget filters, and hard
  diaspora rules — ≥3–4 h buffer after an international arrival before a
  domestic leg (bags/customs at first Indian airport), domestic 15 kg
  baggage check vs international 23–32 kg, FTQ eligibility note for trains
  (365-day window, passport + international-mobile OTP).
  **Justification:** TravelPlanner's GPT-4 pass rate on full itineraries is
  0.6% — free-planning LLMs fail constraint satisfaction. Code can't
  hallucinate a train; the LLM only explains the ranker's output.
- **Provider adapter layer:** every API sits behind an interface with a
  dataset-backed fake implementation. **Justification:** hackathon Wi-Fi,
  rate caps (SerpApi's 250/mo) and sandbox flakiness can't kill the demo;
  the same adapters make unit tests possible without burning API quota.
- **Aggressive caching** of fare/hotel searches keyed by (route, date, pax).
  **Justification:** free-tier caps are the binding constraint, and travel
  searches repeat heavily in a session.
- **Model behind an interface.** Primary: Kimi K3.1 Pro API — 1M context
  holds the full option set + history, $2/$10 per M tokens fits a student
  budget, strong agentic benchmarks. **Caveat wired into the design:** its
  headline scores are vendor-reported, so nothing correctness-critical
  depends on the model; swapping models is a config change.

## 7. Evaluation harness (software improvement)

- A fixed golden set of ~15 queries (e.g. "Pune→Delhi, 2 adults, budget
  ₹15k, no red-eye"; "land BOM 06:00 from Dubai, onward to Pune same day")
  scored TravelPlanner-style on constraint satisfaction: totals correct?
  buffer respected? budget respected? every price sourced (tier ≥ 2)?
- **Justification:** without it, prompt tweaks are vibes. With it, every
  change — including the Phase-2 loop below — is measured.

## 8. Phase 2 — Self-HPO improvement loop (radar: Self-HPO)

- Log every failure class (parse misses, dead results, ranker rejections,
  user overrides). Periodically alternate: (H-step) revise the harness —
  prompts, tool configs, fallback order, ranker weights — using the failure
  log as the search set; (P-step) re-tune model settings under the new
  harness. Gate every change on the §7 eval harness.
- **Justification:** Self-HPO shows harness and policy co-determine agent
  performance and joint gains exceed the sum of parts. Explicitly NOT in
  the MVP — it needs a working system and a failure log to chew on.

## MVP stack (1–2 days, all free/self-serve)

LangGraph + Kimi K3.1 Pro API · Duffel test / SerpApi free (flights) ·
RapidAPI + DataMeet (trains, indicative) · curated bus sample + deep links ·
LiteAPI sandbox (hotels) · Google Maps Routes free caps / OSRM (ground) ·
Raw-RAG memory (embeddings + reranker over raw history) · Pydantic state ·
golden-query eval set. Booking is always a deep-link hand-off — production
transacting (IRCTC partner, redBus partner, payments/PCI) is a business-
development problem, not a code problem.
