"""Supervisor — orchestrates the three agents over the shared state.

Production shape is a LangGraph graph (build_graph): the supervisor
fans out to Fare / Hotel / Ground in parallel (ARCHITECTURE.md §3 —
speculative fan-out, borrowed from DiffResearch's dFast), then rank →
explain. run_pipeline is the same node sequence without the LangGraph
dependency, so the scaffold, tests and evals run anywhere.
"""

from __future__ import annotations

from .agents.fare import FareAgent
from .agents.ground import GroundAgent
from .agents.hotel import HotelAgent
from .explainer import explain
from .providers.fake import (SampleGroundProvider, SampleHotelProvider,
                             SampleLegProvider)
from .ranker import rank
from .state import ItineraryState, TravelQuery


def default_state(query: TravelQuery) -> ItineraryState:
    return ItineraryState(query=query)


def run_pipeline(query: TravelQuery) -> ItineraryState:
    """Sequential runner over sample-data providers (offline demo path)."""
    state = ItineraryState(query=query)
    state = FareAgent(SampleLegProvider()).run(state)
    state = HotelAgent(SampleHotelProvider()).run(state)
    state = GroundAgent(SampleGroundProvider()).run(state)
    state = rank(state)
    state = explain(state)
    return state


def build_graph():
    """LangGraph version: parallel fan-out from the supervisor node.

    Requires `langgraph` (in requirements.txt). Each agent node returns
    ONLY its own slice (legs / hotels / ground_options) so the parallel
    branches never fight over one channel; rank and explain rebuild the
    typed state from the slices. Invoke with {"query": query.model_dump()}
    and read the result back as an ItineraryState.
    """
    from typing import TypedDict

    from langgraph.graph import END, START, StateGraph

    from .state import (GroundOption, HotelOption, LegOption, RankedItinerary,
                        TravelQuery)

    class GState(TypedDict, total=False):
        query: dict
        legs: list
        hotels: list
        ground_options: list
        ranked: list
        summary: str

    def _state(s: GState) -> ItineraryState:
        return ItineraryState(
            query=TravelQuery(**s["query"]),
            legs=[LegOption(**x) for x in s.get("legs", [])],
            hotels=[HotelOption(**x) for x in s.get("hotels", [])],
            ground_options=[GroundOption(**x) for x in s.get("ground_options", [])],
            ranked=[RankedItinerary(**x) for x in s.get("ranked", [])],
        )

    def fare(s: GState) -> dict:
        st = FareAgent(SampleLegProvider()).run(_state(s))
        return {"legs": [x.model_dump() for x in st.legs]}

    def hotel(s: GState) -> dict:
        st = HotelAgent(SampleHotelProvider()).run(_state(s))
        return {"hotels": [x.model_dump() for x in st.hotels]}

    def ground(s: GState) -> dict:
        st = GroundAgent(SampleGroundProvider()).run(_state(s))
        return {"ground_options": [x.model_dump() for x in st.ground_options]}

    def rank_node(s: GState) -> dict:
        st = rank(_state(s))
        return {"ranked": [x.model_dump() for x in st.ranked]}

    def explain_node(s: GState) -> dict:
        st = explain(_state(s))
        return {"summary": st.summary}

    g = StateGraph(GState)
    g.add_node("fare", fare)
    g.add_node("hotel", hotel)
    g.add_node("ground", ground)
    g.add_node("rank", rank_node)
    g.add_node("explain", explain_node)
    for n in ("fare", "hotel", "ground"):
        g.add_edge(START, n)
        g.add_edge(n, "rank")
    g.add_edge("rank", "explain")
    g.add_edge("explain", END)
    return g.compile()
