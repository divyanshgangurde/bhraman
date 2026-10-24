"""End-to-end demo — runs on sample data, no API keys needed.

    python main.py

Demo 1: Pune → Delhi under a ₹9,000 per-person door-to-door budget.
Demo 2: the diaspora case — landed in Mumbai from abroad at 06:00, onward
        to Pune the same day. The supervisor's buffer rule (arrival + 4 h)
        must kill the early departures.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from bhraman.state import TravelQuery
from bhraman.supervisor import run_pipeline


def main() -> None:
    demos = [
        TravelQuery(origin="PNQ", destination="DEL", date="2026-11-14",
                    passengers=1, nights=1, budget_inr=9000,
                    checked_baggage_kg=20),
        TravelQuery(origin="BOM", destination="PNQ", date="2026-11-14",
                    passengers=1, nights=1,
                    earliest_departure="2026-11-14T10:00:00"),  # landed 06:00 + 4h
    ]
    for q in demos:
        state = run_pipeline(q)
        print(state.summary)
        print()


if __name__ == "__main__":
    main()
