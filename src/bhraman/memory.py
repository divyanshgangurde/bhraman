"""Raw-RAG memory (ARCHITECTURE.md §2).

Stores the user's travel history RAW — past conversations, past
itineraries, stated preferences — and retrieves passages for the agents.
No agentic-memory framework: the Raw-RAG paper shows dense retrieval +
reranking over raw history beats complex memory systems on 6 of 7
benchmark settings, and raw text preserves exact facts (a quoted fare,
"window seat", "no red-eye") that transformed stores lose.

v0 ranking is token-overlap + recency so the scaffold runs with zero
dependencies. Swap in dense embeddings + a reranker behind this same
interface — callers do not change.
"""

from __future__ import annotations

import re
import time


class RawMemory:
    def __init__(self):
        self._items: list[tuple[str, dict, float]] = []  # text, meta, ts

    def add(self, text: str, **meta) -> None:
        self._items.append((text, meta, time.time()))

    def search(self, query: str, k: int = 3) -> list[str]:
        q = set(re.findall(r"[a-z0-9]+", query.lower()))
        scored = []
        for text, _meta, ts in self._items:
            words = set(re.findall(r"[a-z0-9]+", text.lower()))
            overlap = len(q & words)
            if overlap:
                scored.append((overlap, ts, text))
        scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
        return [t for _s, _ts, t in scored[:k]]
