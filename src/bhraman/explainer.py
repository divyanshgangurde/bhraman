"""Explainer — turns ranked itineraries into plain language.

The LLM lives here and ONLY here: it narrates the ranker's output and
adds guidance (FTQ notes, document reminders). It never computes a
price or invents an option — everything it says traces to state.ranked.

The scaffold ships a template explainer that needs no API key.
LLMExplainer is the drop-in replacement once a key is configured.
"""

from __future__ import annotations

from .state import ItineraryState


def _fmt(mins: int) -> str:
    return f"{mins // 60}h {mins % 60:02d}m"


def explain(state: ItineraryState) -> ItineraryState:
    q = state.query
    if not state.ranked:
        state.summary = (f"No itinerary for {q.origin} → {q.destination} fits "
                         f"the constraints (budget/buffer). Loosen one and retry.")
        return state
    lines = [f"{q.origin} → {q.destination} on {q.date} — "
             f"{len(state.ranked)} option(s), cheapest door-to-door first:"]
    for i, r in enumerate(state.ranked, 1):
        lines.append(
            f"{i}. {r.leg.mode.upper()} via {r.leg.provider} — "
            f"₹{r.total_inr:,} total, {_fmt(r.door_to_door_min)} door-to-door "
            f"(leg ₹{r.leg.price_inr:,}"
            + (f", hotel ₹{r.hotel.price_per_night_inr:,}/night at {r.hotel.name}"
               if r.hotel else "")
            + (f", last mile {r.ground.mode} ₹{r.ground.cost_inr}" if r.ground else "")
            + ").")
        for n in r.notes:
            lines.append(f"   Note: {n}")
    state.summary = "\n".join(lines)
    return state


class LLMExplainer:
    """TODO: call the configured model (config.settings.model) with
    state.ranked serialised as JSON; instruct it to explain, not alter,
    the ranking. Keep explain() above as the offline fallback."""

    def run(self, state: ItineraryState) -> ItineraryState:
        raise NotImplementedError("Wire to the model API — see docstring.")
