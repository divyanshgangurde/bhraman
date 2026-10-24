"""Provider interfaces. Every data source — live API, offline dataset,
deep link — sits behind one of these so agents never care where data
came from, and every live provider has a sample-data stand-in (fake.py)
for offline development and demos. See ARCHITECTURE.md §6.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..state import GroundOption, HotelOption, LegOption, TravelQuery


class LegProvider(ABC):
    """Flights, trains and buses all normalise into LegOption."""

    @abstractmethod
    def search_legs(self, query: TravelQuery) -> list[LegOption]:
        ...


class HotelProvider(ABC):
    @abstractmethod
    def search_hotels(self, query: TravelQuery) -> list[HotelOption]:
        ...


class GroundProvider(ABC):
    @abstractmethod
    def search_ground(self, query: TravelQuery) -> list[GroundOption]:
        ...
