"""Deterministic ranker — pure code, no LLM (ARCHITECTURE.md §6).

Rules enforced here, never by the model:
  * Door-to-door totals: leg (x passengers) + ground + hotel x nights.
  * Buffer rule: legs departing before query.earliest_departure are
    excluded (the supervisor sets it to international arrival + 3-4 h).
  * Budget: itineraries over budget_inr x passengers are excluded.
  * Baggage: a leg whose allowance is below what the traveller carries
    is kept but flagged — the traveller decides, the ranker informs.
"""

from __future__ import annotations

from .state import ItineraryState, RankedItinerary


def rank(state: ItineraryState) -> ItineraryState:
    q = state.query
    ground = min(state.ground_options, key=lambda g: g.cost_inr, default=None)
    hotel = min(state.hotels, key=lambda h: h.price_per_night_inr, default=None)
    party_budget = q.budget_inr * q.passengers if q.budget_inr else None

    ranked: list[RankedItinerary] = []
    for leg in state.legs:
        if q.earliest_departure and leg.depart < q.earliest_departure:
            continue  # buffer rule
        total = leg.price_inr * q.passengers
        door = leg.duration_min
        notes: list[str] = []
        if ground:
            total += ground.cost_inr
            door += ground.duration_min
        if hotel:
            total += hotel.price_per_night_inr * q.nights
        if q.checked_baggage_kg and leg.baggage_kg is not None \
                and leg.baggage_kg < q.checked_baggage_kg:
            notes.append(
                f"Baggage shortfall: this {leg.mode} allows {leg.baggage_kg} kg, "
                f"you are carrying {q.checked_baggage_kg} kg.")
        if leg.notes:
            notes.append(leg.notes)
        if party_budget is not None and total > party_budget:
            continue  # budget rule
        ranked.append(RankedItinerary(leg=leg, hotel=hotel, ground=ground,
                                      total_inr=total, door_to_door_min=door,
                                      notes=notes))
    state.ranked = sorted(ranked, key=lambda r: r.total_inr)
    return state
