import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from bhraman.memory import RawMemory


def test_raw_memory_retrieves_relevant_passage():
    m = RawMemory()
    m.add("Divyansh prefers window seats and no red-eye flights.")
    m.add("Last Pune trip: stayed near Deccan, liked the metro for last mile.")
    hits = m.search("window seat preference", k=1)
    assert hits and "window seats" in hits[0]


def test_raw_memory_keeps_raw_text():
    m = RawMemory()
    m.add("Quoted fare was exactly Rs 5,499 on the morning flight.")
    assert m.search("fare")[0].startswith("Quoted fare was exactly")
