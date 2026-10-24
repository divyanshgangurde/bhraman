"""Hotel agent — owns state.hotels."""

from __future__ import annotations

from ..providers.base import HotelProvider
from ..state import ItineraryState


class HotelAgent:
    def __init__(self, provider: HotelProvider):
        self.provider = provider

    def run(self, state: ItineraryState) -> ItineraryState:
        state.hotels = self.provider.search_hotels(state.query)
        return state
