"""Bhraman FastAPI layer — thin wrapper over the existing backend.

Layout (chosen for the hackathon demo):
  api.py            <- this file; run with `uvicorn api:app --reload`
  frontend/index.html  <- single-page frontend, served at GET /
  src/bhraman/      <- UNCHANGED backend (state, supervisor, ranker, explainer)

This file does NOT change ranker/state/supervisor logic. It only:
  * parses the API request into a TravelQuery,
  * applies the international-arrival rule (arrival + 4h = earliest_departure),
  * runs the existing run_pipeline(),
  * enriches the response for display (tier labels, rejected-leg reasons,
    an FTQ display note for trains) without inventing any price.

All prices/totals come from the deterministic ranker, in INR.
Sample data only: no live Duffel / LiteAPI calls in this build.
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).parent / "src"))

from bhraman.state import TravelQuery  # noqa: E402
from bhraman.supervisor import run_pipeline  # noqa: E402

ROOT = Path(__file__).parent
FRONTEND_INDEX = ROOT / "frontend" / "index.html"

app = FastAPI(title="Bhraman", description="Bhraman भ्रमण — one itinerary, priced door to door.")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------- models

class PlanRequest(BaseModel):
    origin: str
    destination: str
    date: str = "2026-11-14"
    passengers: int = 1
    nights: int = 1
    budget_inr: int | None = None
    earliest_departure: str | None = None
    checked_baggage_kg: int = 0
    # Optional international arrival. When set, earliest_departure is
    # auto-set to arrival + 4h (bags + customs at the first Indian airport).
    # Accepts "2026-11-14T06:00:00" or a time-only "06:00" (combined with date).
    international_arrival: str | None = None


# ---------------------------------------------------------------- helpers

def _parse_arrival(date: str, value: str) -> datetime:
    value = value.strip()
    if "T" in value:
        return datetime.fromisoformat(value)
    if ":" in value:
        # Time-only, e.g. "06:00" or "06:00:00"
        parts = value.split(":")
        hour = int(parts[0])
        minute = int(parts[1]) if len(parts) > 1 else 0
        second = int(parts[2]) if len(parts) > 2 else 0
        day = datetime.fromisoformat(date).date()
        return datetime(day.year, day.month, day.day, hour, minute, second)
    return datetime.fromisoformat(value)


def _fmt_dt(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%S")


def _fmt_mins(mins: int) -> str:
    return f"{mins // 60}h {mins % 60:02d}m"


def tier_label(tier: int, deep_link: str | None = None) -> str:
    """Display label for the backend tier int.

    Backend tiers (state.py): 1 = live API, 2 = offline dataset/sample,
    3 = deep-link only. For display we keep the task's wording:
    LIVE (1), INDICATIVE (2), SAMPLE / Deep-link (3).
    """
    if tier == 1:
        return "LIVE"
    if tier == 3:
        return "SAMPLE • Deep-link" if deep_link else "SAMPLE"
    return "INDICATIVE"


FTQ_NOTE = (
    "Foreign Tourist Quota (FTQ): foreign tourists can book Indian trains "
    "365 days ahead (vs 60 days general) — passport + international mobile "
    "OTP required. Availability here is INDICATIVE."
)


def resolve_earliest(req: PlanRequest) -> tuple[str | None, bool]:
    """Return (earliest_departure, buffer_applied)."""
    if req.international_arrival:
        arrival = _parse_arrival(req.date, req.international_arrival)
        return _fmt_dt(arrival + timedelta(hours=4)), True
    if req.earliest_departure:
        raw = req.earliest_departure.strip()
        if "T" in raw:
            return _fmt_dt(datetime.fromisoformat(raw)), False
        # Time-only earliest_departure: combine with the query date.
        return _fmt_dt(_parse_arrival(req.date, raw)), False
    return None, False


# ---------------------------------------------------------------- presets

DEMO_PRESETS = [
    {
        "id": "diaspora-bom-pnq",
        "name": "Dubai → Mumbai 06:00 → Pune, same day",
        "description": (
            "Diaspora case: landed in Mumbai at 06:00. The 4h buffer "
            "(bags + customs) rejects early onward legs."
        ),
        "query": {
            "origin": "BOM",
            "destination": "PNQ",
            "date": "2026-11-14",
            "passengers": 1,
            "nights": 1,
            "budget_inr": None,
            "checked_baggage_kg": 0,
            "international_arrival": "2026-11-14T06:00:00",
            "earliest_departure": None,
        },
    },
    {
        "id": "pnq-del-budget",
        "name": "Pune → Delhi, ₹9,000 budget",
        "description": (
            "Domestic case: 1 passenger, 1 night, ₹9,000 per-person "
            "door-to-door cap, 20 kg checked baggage."
        ),
        "query": {
            "origin": "PNQ",
            "destination": "DEL",
            "date": "2026-11-14",
            "passengers": 1,
            "nights": 1,
            "budget_inr": 9000,
            "checked_baggage_kg": 20,
            "international_arrival": None,
            "earliest_departure": None,
        },
    },
]


# ---------------------------------------------------------------- routes

@app.get("/health")
def health():
    return {"status": "ok", "service": "bhraman", "data": "sample/offline, no live APIs"}


@app.get("/api/demo-presets")
def demo_presets():
    return {"presets": DEMO_PRESETS}


@app.post("/api/plan")
def plan(req: PlanRequest):
    earliest, buffer_applied = resolve_earliest(req)

    query = TravelQuery(
        origin=req.origin.strip().upper(),
        destination=req.destination.strip().upper(),
        date=req.date,
        passengers=req.passengers,
        nights=req.nights,
        budget_inr=req.budget_inr,
        earliest_departure=earliest,
        checked_baggage_kg=req.checked_baggage_kg,
    )
    state = run_pipeline(query)

    # Cheapest hotel / ground, mirroring the ranker, for budget-reason checks.
    ground = min(state.ground_options, key=lambda g: g.cost_inr, default=None)
    hotel = min(state.hotels, key=lambda h: h.price_per_night_inr, default=None)
    party_budget = query.budget_inr * query.passengers if query.budget_inr else None
    ranked_leg_keys = {
        (r.leg.mode, r.leg.provider, r.leg.depart, r.leg.arrive) for r in state.ranked
    }

    rejected = []
    for leg in state.legs:
        key = (leg.mode, leg.provider, leg.depart, leg.arrive)
        if key in ranked_leg_keys:
            continue
        if earliest and leg.depart < earliest:
            rejected.append({
                "leg": leg.model_dump(),
                "tier_label": tier_label(leg.tier, leg.deep_link),
                "reason": (
                    "REJECTED by international-arrival buffer: departs "
                    f"{leg.depart} before earliest allowed {earliest} "
                    "(arrival + 4h for bags + customs at the first Indian airport)."
                ),
                "rule": "buffer",
            })
        elif party_budget is not None:
            total = leg.price_inr * query.passengers
            if ground:
                total += ground.cost_inr
            if hotel:
                total += hotel.price_per_night_inr * query.nights
            if total > party_budget:
                rejected.append({
                    "leg": leg.model_dump(),
                    "tier_label": tier_label(leg.tier, leg.deep_link),
                    "reason": (
                        f"Excluded by budget: door-to-door total ₹{total:,} "
                        f"exceeds the party cap ₹{party_budget:,} "
                        f"(₹{query.budget_inr:,} × {query.passengers})."
                    ),
                    "rule": "budget",
                })

    ranked_out = []
    for i, r in enumerate(state.ranked, 1):
        notes = list(r.notes)
        # Display-only FTQ note for trains (no price invented, no ranker change).
        if r.leg.mode == "train" and not any("Foreign Tourist Quota" in n for n in notes):
            notes.append(FTQ_NOTE)
        leg_total = r.leg.price_inr * query.passengers
        hotel_total = (
            r.hotel.price_per_night_inr * query.nights if r.hotel else 0
        )
        ground_cost = r.ground.cost_inr if r.ground else 0
        ranked_out.append({
            "rank": i,
            "leg": r.leg.model_dump(),
            "leg_tier_label": tier_label(r.leg.tier, r.leg.deep_link),
            "hotel": r.hotel.model_dump() if r.hotel else None,
            "hotel_tier_label": tier_label(r.hotel.tier) if r.hotel else None,
            "ground": r.ground.model_dump() if r.ground else None,
            "ground_tier_label": tier_label(r.ground.tier, r.ground.deep_link) if r.ground else None,
            "total_inr": r.total_inr,
            "door_to_door_min": r.door_to_door_min,
            "door_to_door_display": _fmt_mins(r.door_to_door_min),
            "breakdown": {
                "leg_total_inr": leg_total,
                "hotel_total_inr": hotel_total,
                "ground_cost_inr": ground_cost,
            },
            "notes": notes,
        })

    return {
        "query": query.model_dump(),
        "international_arrival": req.international_arrival,
        "earliest_departure_applied": earliest,
        "buffer_applied": buffer_applied,
        "buffer_note": (
            "International-arrival buffer applied: onward legs before "
            f"{earliest} are rejected (arrival + 4h for bags + customs)."
            if buffer_applied and earliest
            else None
        ),
        "summary": state.summary,
        "ranked": ranked_out,
        "rejected": rejected,
        "counts": {
            "legs_found": len(state.legs),
            "ranked": len(ranked_out),
            "rejected": len(rejected),
        },
    }


# ---------------------------------------------------------------- chat
# Natural-language chat parsing (POST /api/chat).
# This ONLY parses words into a TravelQuery and calls plan() above.
# It never invents a price: all totals still come from run_pipeline()
# via the deterministic ranker, and routes outside the sample data
# get a clarification reply, not a fabricated itinerary.

import re

SAMPLE_DATE = "2026-11-14"
SAMPLE_ROUTES = {("BOM", "PNQ"), ("PNQ", "DEL")}
CITY_WORDS = {
    "mumbai": "BOM", "bombay": "BOM", "bom": "BOM",
    "pune": "PNQ", "poona": "PNQ", "pnq": "PNQ",
    "delhi": "DEL", "new delhi": "DEL", "del": "DEL",
    "dubai": "DXB", "dxb": "DXB",
}
CITY_NAMES = {"BOM": "Mumbai", "PNQ": "Pune", "DEL": "Delhi", "DXB": "Dubai"}


class ChatRequest(BaseModel):
    message: str


def _city_mentions(text: str) -> list[tuple[int, str]]:
    """(position, code) for every city name/code mention, in order."""
    found: list[tuple[int, str]] = []
    for word, code in CITY_WORDS.items():
        for m in re.finditer(rf"\b{re.escape(word)}\b", text):
            found.append((m.start(), code))
    # De-duplicate overlapping matches (e.g. "new delhi" vs "delhi"):
    # keep the earliest start, and for the same start the longest word.
    found.sort(key=lambda x: x[0])
    deduped: list[tuple[int, str]] = []
    last_end = -1
    for pos, code in found:
        if pos >= last_end:
            deduped.append((pos, code))
            # length of the matched word is not tracked; use a safe span
            last_end = pos + 3
    return deduped


def _to_24h(hour: int, minute: int, ampm: str | None) -> tuple[int, int]:
    if ampm == "pm" and hour < 12:
        hour += 12
    if ampm == "am" and hour == 12:
        hour = 0
    return hour, minute


def _parse_chat_message(raw: str) -> dict:
    text = (raw or "").strip()
    low = text.lower()
    result: dict = {
        "origin": None, "destination": None, "passengers": 1, "nights": 1,
        "budget_inr": None, "checked_baggage_kg": 0,
        "international_arrival": None, "date_note": None,
        "route_note": None,
    }
    if not text:
        return result

    mentions = _city_mentions(low)
    codes_in_order = [c for _, c in mentions]

    # Diaspora case first: Dubai -> Mumbai -> Pune means BOM -> PNQ.
    if "DXB" in codes_in_order and "BOM" in codes_in_order and "PNQ" in codes_in_order:
        result["origin"], result["destination"] = "BOM", "PNQ"
        result["route_note"] = "Dubai to Pune via Mumbai, so the onward leg is Mumbai to Pune."
    else:
        m = re.search(
            r"from\s+(new delhi|mumbai|bombay|pune|poona|delhi|bom|pnq|del)\b"
            r".{0,40}?\bto\s+(new delhi|mumbai|bombay|pune|poona|delhi|bom|pnq|del)\b",
            low)
        if m:
            result["origin"] = CITY_WORDS[m.group(1)]
            result["destination"] = CITY_WORDS[m.group(2)]
        else:
            route_codes = [c for c in codes_in_order if c != "DXB"]
            distinct: list[str] = []
            for c in route_codes:
                if c not in distinct:
                    distinct.append(c)
            if len(distinct) >= 2:
                result["origin"], result["destination"] = distinct[0], distinct[1]
            elif "landed" in low or "arrived" in low or "landing" in low:
                # "landed in Mumbai, onward to Pune" etc. is handled by the
                # from/to and distinct-city branches above in most cases;
                # fall through to clarification if it did not resolve.
                pass

    # Budget: "Rs 9000", "₹9,000", "INR 9000", "9000 max", "budget 9000".
    bm = re.search(r"(?:rs\.?|₹|inr|rupees?)\s*([0-9][0-9,]*)", low)
    if not bm:
        bm = re.search(r"([0-9][0-9,]*)\s*(?:rs\.?|₹|inr|rupees?|max|budget)\b", low)
    if bm:
        result["budget_inr"] = int(bm.group(1).replace(",", ""))

    pm = re.search(r"(\d+)\s*(people|passengers?|persons?|travellers?|travelers?)", low)
    if pm:
        result["passengers"] = int(pm.group(1))
    else:
        fm = re.search(r"for\s+(\d+)(?!\s*nights?\b)", low)
        if fm:
            result["passengers"] = int(fm.group(1))

    nm = re.search(r"(\d+)\s*nights?\b", low)
    if nm:
        result["nights"] = int(nm.group(1))

    kg = re.search(r"(\d+)\s*kg\b", low)
    if kg:
        result["checked_baggage_kg"] = int(kg.group(1))

    # International arrival: "landed at 06:00", "arrived 6am", "landing 06:00".
    arrival_time: str | None = None
    if re.search(r"\b(landed|arrived|landing|arrive|land)\b", low):
        tm = re.search(r"(\d{1,2}):(\d{2})(?::\d{2})?\s*(am|pm)?", low)
        if tm:
            h, mi = _to_24h(int(tm.group(1)), int(tm.group(2)), tm.group(3))
            arrival_time = f"{h:02d}:{mi:02d}"
        else:
            tm2 = re.search(r"(\d{1,2})\s*(am|pm)\b", low)
            if tm2:
                h, mi = _to_24h(int(tm2.group(1)), 0, tm2.group(2))
                arrival_time = f"{h:02d}:{mi:02d}"
    if arrival_time:
        result["international_arrival"] = f"{SAMPLE_DATE}T{arrival_time}:00"

    # Date: sample data is fixed to SAMPLE_DATE. Map relative dates to it
    # openly, never invent another date's prices.
    if "tomorrow" in low or "next friday" in low or "next week" in low or "friday" in low:
        result["date_note"] = (
            "Sample data is fixed to 2026-11-14, so I used that date for "
            "this demo (your tomorrow / next Friday wording is mapped to "
            "the sample date, not to other dates' prices)."
        )
    return result


def _plain_echo(parsed: dict, earliest: str | None) -> str:
    parts = []
    if parsed["origin"] and parsed["destination"]:
        parts.append(
            f"{CITY_NAMES.get(parsed['origin'], parsed['origin'])} → "
            f"{CITY_NAMES.get(parsed['destination'], parsed['destination'])}")
    parts.append(f"{parsed['passengers']} person{'s' if parsed['passengers'] != 1 else ''}")
    parts.append(f"{parsed['nights']} night{'s' if parsed['nights'] != 1 else ''}")
    if parsed["budget_inr"]:
        parts.append(f"budget ₹{parsed['budget_inr']:,} per person")
    else:
        parts.append("no budget cap")
    if parsed["checked_baggage_kg"]:
        parts.append(f"{parsed['checked_baggage_kg']} kg baggage")
    if parsed["international_arrival"]:
        parts.append(
            f"landed {parsed['international_arrival'][11:16]} "
            f"(onward travel only from {earliest[11:16]} after the 4-hour buffer)")
    return " · ".join(parts)


@app.post("/api/chat")
def chat(req: ChatRequest):
    parsed = _parse_chat_message(req.message)
    origin, destination = parsed["origin"], parsed["destination"]

    if not origin or not destination:
        return {
            "status": "clarification",
            "assistant_text": (
                "I could not work out both places from that. "
                "Try something like: “I have to go from Mumbai to Pune, "
                "I landed at 06:00, help me plan” or “I have to go from "
                "Pune to Delhi, budget Rs 9000, help me plan”."),
            "parsed_query": parsed,
            "demo_routes": ["Mumbai (BOM) → Pune (PNQ)", "Pune (PNQ) → Delhi (DEL)"],
            "ranked": [], "rejected": [], "summary": "", "counts": {"ranked": 0, "rejected": 0, "legs_found": 0},
        }
    if (origin, destination) not in SAMPLE_ROUTES:
        return {
            "status": "clarification",
            "assistant_text": (
                f"I understood {CITY_NAMES.get(origin, origin)} → "
                f"{CITY_NAMES.get(destination, destination)}, but this demo "
                "only has sample data for Mumbai → Pune and Pune → Delhi, "
                "so I cannot price that route honestly yet. Please try one "
                "of the demo routes above."),
            "parsed_query": parsed,
            "demo_routes": ["Mumbai (BOM) → Pune (PNQ)", "Pune (PNQ) → Delhi (DEL)"],
            "ranked": [], "rejected": [], "summary": "", "counts": {"ranked": 0, "rejected": 0, "legs_found": 0},
        }

    plan_req = PlanRequest(
        origin=origin, destination=destination, date=SAMPLE_DATE,
        passengers=parsed["passengers"], nights=parsed["nights"],
        budget_inr=parsed["budget_inr"],
        checked_baggage_kg=parsed["checked_baggage_kg"],
        international_arrival=parsed["international_arrival"],
    )
    out = plan(plan_req)
    ranked = out.get("ranked", [])
    if ranked:
        top = ranked[0]
        assistant_text = (
            f"Found {len(ranked)} option{'s' if len(ranked) != 1 else ''} from "
            f"{CITY_NAMES.get(origin, origin)} to {CITY_NAMES.get(destination, destination)}. "
            f"Cheapest door-to-door is {top['leg']['mode']} at "
            f"₹{top['total_inr']:,} ({top['door_to_door_display']}), "
            "including hotel and last mile.")
    else:
        assistant_text = (
            "No itinerary fits those constraints in the sample data. "
            "Try loosening the budget or the arrival buffer, or use a demo route.")
    return {
        "status": "ok",
        "assistant_text": assistant_text,
        "parsed_query": {
            **parsed,
            "plain": _plain_echo(parsed, out.get("earliest_departure_applied")),
        },
        "date_note": parsed["date_note"],
        "route_note": parsed["route_note"],
        "demo_routes": ["Mumbai (BOM) → Pune (PNQ)", "Pune (PNQ) → Delhi (DEL)"],
        **out,
    }


@app.get("/")
def index():
    if FRONTEND_INDEX.exists():
        return FileResponse(FRONTEND_INDEX)
    return JSONResponse(
        {"service": "bhraman", "hint": "frontend/index.html not found; API at /api/plan, /api/demo-presets, /health"},
        status_code=404,
    )


@app.get("/favicon.ico")
def favicon():
    return JSONResponse({}, status_code=204)
