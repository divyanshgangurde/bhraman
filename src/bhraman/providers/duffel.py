"""Duffel flights adapter — interface-complete stub.

Duffel is the only self-serve, bookable flight API left (Amadeus
self-service was decommissioned Jul 2026; Skyscanner is partner-only).
Test-mode token is instant on signup. Pricing: $3 per confirmed order
+ 1% managed content. Implement search_legs against the Duffel Offer
Requests API and map offers onto LegOption (tier=1).
"""

from __future__ import annotations

from ..state import LegOption, TravelQuery
from .base import LegProvider


class DuffelFlightProvider(LegProvider):
    def __init__(self, api_key: str):
        self.api_key = api_key

    def search_legs(self, query: TravelQuery) -> list[LegOption]:
        raise NotImplementedError("Wire to Duffel Offer Requests API — see docstring.")
