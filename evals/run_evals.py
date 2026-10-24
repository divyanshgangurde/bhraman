"""Golden-query eval harness (ARCHITECTURE.md §7).

Runs the offline pipeline against fixed trips and checks CONSTRAINTS,
TravelPlanner-style: totals within budget, buffer respected, every rule
the ranker promises. If a check fails, the system regressed — prompts
and tweaks are not merged on vibes.

    python evals/run_evals.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from bhraman.state import TravelQuery
from bhraman.supervisor import run_pipeline


def check(case: dict) -> list[str]:
    q = TravelQuery(**case["query"])
    state = run_pipeline(q)
    exp = case["expect"]
    failures = []
    if "min_leg_modes" in exp:
        modes = {leg.mode for leg in state.legs}
        if len(modes) < exp["min_leg_modes"]:
            failures.append(f"only {len(modes)} modes found: {modes}")
    if "top_total_max_inr" in exp:
        if not state.ranked or state.ranked[0].total_inr > exp["top_total_max_inr"]:
            failures.append("cheapest itinerary over the expected cap")
    if "no_depart_before" in exp:
        for r in state.ranked:
            if r.leg.depart < exp["no_depart_before"]:
                failures.append(f"buffer violated by {r.leg.mode} at {r.leg.depart}")
    if "ranked_excludes_mode" in exp:
        if any(r.leg.mode == exp["ranked_excludes_mode"] for r in state.ranked):
            failures.append(f"{exp['ranked_excludes_mode']} should have been filtered out")
    if "mode_note_contains" in exp:
        want = exp["mode_note_contains"]
        hit = any(r.leg.mode == want["mode"] and
                  any(want["text"] in n for n in r.notes) for r in state.ranked)
        if not hit:
            failures.append(f"no '{want['text']}' note on the {want['mode']} itinerary")
    return failures


def main() -> int:
    cases = json.loads((Path(__file__).parent / "golden_queries.json").read_text())
    bad = 0
    for case in cases:
        failures = check(case)
        print(("PASS " if not failures else "FAIL ") + case["name"])
        for f in failures:
            print(f"     - {f}")
            bad += 1
    print(f"\n{len(cases) - (1 if bad else 0) and len(cases)}/{len(cases)} cases clean"
          if not bad else f"\n{bad} check(s) failed")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
