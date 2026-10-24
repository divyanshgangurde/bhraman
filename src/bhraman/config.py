"""Settings. Everything optional — the demo runs on sample data with no keys.

Model choice (ARCHITECTURE.md §6): Kimi K3.1 Pro by default — 1M context,
$2/$10 per M tokens. It sits behind the explainer interface, so swapping
models is a config change, never a refactor.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class Settings:
    model: str = os.environ.get("TRAVEL_MODEL", "kimi-k3.1-pro")
    kimi_api_key: str | None = os.environ.get("KIMI_API_KEY")
    duffel_api_key: str | None = os.environ.get("DUFFEL_API_KEY")
    liteapi_key: str | None = os.environ.get("LITEAPI_KEY")
    serpapi_key: str | None = os.environ.get("SERPAPI_KEY")
    google_maps_key: str | None = os.environ.get("GOOGLE_MAPS_API_KEY")


settings = Settings()
