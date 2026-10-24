"""LiteAPI hotels adapter — interface-complete stub.

LiteAPI (Nuitée) is the self-serve hotel option: sandbox with no card,
2.6M+ properties. Booking.com / Expedia Rapid / Hotelbeds are all
partner-gated; MakeMyTrip has no public API. Implement search_hotels
against the LiteAPI search endpoint and map results onto HotelOption
(tier=1), keeping distance_to_arrival_km so ranking can prefer stays
near the arrival point.
"""

from __future__ import annotations

from ..state import HotelOption, TravelQuery
from .base import HotelProvider


class LiteApiHotelProvider(HotelProvider):
    def __init__(self, api_key: str):
        self.api_key = api_key

    def search_hotels(self, query: TravelQuery) -> list[HotelOption]:
        raise NotImplementedError("Wire to LiteAPI search — see docstring.")
