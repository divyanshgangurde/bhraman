"""Shared itinerary state — the single object all agents read and write.

Design rule (ARCHITECTURE.md §1): specialists write ONLY their own slice.
Every option carries a `tier` so the UI can label data honestly:
  1 = live API, 2 = offline dataset / sample, 3 = deep link only.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class TravelQuery(BaseModel):
    origin: str
    destination: str
    date: str  # ISO date, e.g. "2026-11-14"
    passengers: int = 1
    nights: int = 1
    budget_inr: int | None = None  # per-person door-to-door cap
    earliest_departure: str | None = None  # ISO datetime; the supervisor sets
    # this to (international arrival + buffer) so onward legs can't leave
    # before bags/customs are realistically done.
    checked_baggage_kg: int = 0  # what the traveller is carrying


class LegOption(BaseModel):
    mode: str  # flight | train | bus
    provider: str
    origin: str
    destination: str
    depart: str  # ISO datetime
    arrive: str  # ISO datetime
    duration_min: int
    price_inr: int  # per person, incl. taxes/fees
    baggage_kg: int | None = None  # None = no practical limit (trains)
    refundable: bool = False
    tier: int = 2
    deep_link: str | None = None
    notes: str = ""


class HotelOption(BaseModel):
    name: str
    city: str
    area: str
    price_per_night_inr: int
    rating: float | None = None
    distance_to_arrival_km: float | None = None
    tier: int = 2


class GroundOption(BaseModel):
    mode: str  # metro | auto | cab | bus
    city: str  # arrival city this option serves
    from_point: str
    to_point: str
    duration_min: int
    cost_inr: int  # per booking (cab/auto) or per person (metro) — sample data
    tier: int = 2
    deep_link: str | None = None


class RankedItinerary(BaseModel):
    leg: LegOption
    hotel: HotelOption | None = None
    ground: GroundOption | None = None
    total_inr: int = 0  # whole party, door-to-door
    door_to_door_min: int = 0
    notes: list[str] = Field(default_factory=list)


class ItineraryState(BaseModel):
    query: TravelQuery
    legs: list[LegOption] = Field(default_factory=list)
    hotels: list[HotelOption] = Field(default_factory=list)
    ground_options: list[GroundOption] = Field(default_factory=list)
    ranked: list[RankedItinerary] = Field(default_factory=list)
    summary: str = ""
