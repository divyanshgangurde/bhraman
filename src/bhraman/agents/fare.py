"""Fare agent — owns state.legs. Compares flights, trains and buses
through one LegProvider interface; in a live setup, compose several
providers (Duffel + train info + bus deep links) behind it.
"""

from __future__ import annotations

from ..providers.base import LegProvider
from ..state import ItineraryState


class FareAgent:
    def __init__(self, provider: LegProvider):
        self.provider = provider

    def run(self, state: ItineraryState) -> ItineraryState:
        state.legs = self.provider.search_legs(state.query)
        return state
