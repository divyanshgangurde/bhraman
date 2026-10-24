"""Ground agent — owns state.ground_options. Its per-arrival time and
cost are what let the ranker price the whole door-to-door trip.
"""

from __future__ import annotations

from ..providers.base import GroundProvider
from ..state import ItineraryState


class GroundAgent:
    def __init__(self, provider: GroundProvider):
        self.provider = provider

    def run(self, state: ItineraryState) -> ItineraryState:
        state.ground_options = self.provider.search_ground(state.query)
        return state
