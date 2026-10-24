import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from bhraman.state import TravelQuery
from bhraman.supervisor import run_pipeline


def test_door_to_door_totals():
    st = run_pipeline(TravelQuery(origin="PNQ", destination="DEL",
                                  date="2026-11-14", budget_inr=9000))
    top = st.ranked[0]
    assert top.leg.mode == "bus"  # 1499 leg + 60 metro + 1800 hotel
    assert top.total_inr == 1499 + 60 + 1800


def test_budget_filter_excludes_flight():
    st = run_pipeline(TravelQuery(origin="PNQ", destination="DEL",
                                  date="2026-11-14", budget_inr=4000))
    assert all(r.leg.mode != "flight" for r in st.ranked)


def test_international_buffer_rule():
    st = run_pipeline(TravelQuery(origin="BOM", destination="PNQ",
                                  date="2026-11-14",
                                  earliest_departure="2026-11-14T10:00:00"))
    assert st.ranked, "expected some onward options after 10:00"
    assert all(r.leg.depart >= "2026-11-14T10:00:00" for r in st.ranked)


def test_baggage_shortfall_flagged_not_hidden():
    st = run_pipeline(TravelQuery(origin="PNQ", destination="DEL",
                                  date="2026-11-14", checked_baggage_kg=25))
    flight = [r for r in st.ranked if r.leg.mode == "flight"]
    assert flight and any("Baggage shortfall" in n for n in flight[0].notes)


def test_all_modes_compared_and_sorted():
    st = run_pipeline(TravelQuery(origin="PNQ", destination="DEL", date="2026-11-14"))
    assert {leg.mode for leg in st.legs} == {"flight", "train", "bus"}
    totals = [r.total_inr for r in st.ranked]
    assert totals == sorted(totals)
