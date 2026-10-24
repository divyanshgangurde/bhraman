"""Sample-data providers — the offline stand-ins behind the interfaces.

They read the JSON files in ../data and return normalised options, so the
whole pipeline (agents → ranker → explainer → evals) runs with no API keys
and no network. Live adapters implement the same interfaces.
"""

from __future__ import annotations

import json
from pathlib import Path

from ..state import GroundOption, HotelOption, LegOption, TravelQuery
from .base import GroundProvider, HotelProvider, LegProvider

_DATA = Path(__file__).parent.parent / "data"


def _load(name: str) -> list[dict]:
    return json.loads((_DATA / name).read_text())


class SampleLegProvider(LegProvider):
    """All modes in one sample set; a live setup splits this per mode
    (Duffel for flights, RapidAPI/DataMeet for trains, deep links for buses)."""

    def search_legs(self, query: TravelQuery) -> list[LegOption]:
        return [LegOption(**row) for row in _load("sample_legs.json")
                if row["origin"] == query.origin and row["destination"] == query.destination]


class SampleHotelProvider(HotelProvider):
    def search_hotels(self, query: TravelQuery) -> list[HotelOption]:
        return [HotelOption(**row) for row in _load("sample_hotels.json")
                if row["city"] == query.destination]


class SampleGroundProvider(GroundProvider):
    def search_ground(self, query: TravelQuery) -> list[GroundOption]:
        return [GroundOption(**row) for row in _load("sample_ground.json")
                if row["city"] == query.destination]
