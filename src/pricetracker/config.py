"""Load settings.yaml + environment (.env) into one typed object."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml

try:
    from dotenv import load_dotenv
except ImportError:  # optional
    load_dotenv = None

PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass
class StoreSelection:
    cities: list[str] = field(default_factory=list)
    max_stores_per_chain: int = 12
    include_store_ids: dict[str, list[int]] = field(default_factory=dict)


@dataclass
class Settings:
    enabled_chains: list[str]
    store_selection: StoreSelection
    file_types: list[str]
    raw_keep: bool
    raw_dir: Path
    raw_retention_days: int
    http_timeout: int
    http_retries: int
    database_url: str | None

    @classmethod
    def load(cls, path: str | Path | None = None) -> "Settings":
        if load_dotenv is not None:
            load_dotenv(PROJECT_ROOT / ".env")
        path = Path(path or os.environ.get("PRICETRACKER_CONFIG", PROJECT_ROOT / "config" / "settings.yaml"))
        cfg = yaml.safe_load(path.read_text(encoding="utf-8")) or {}

        chains = cfg.get("chains", {})
        enabled = [k for k, v in chains.items() if (v or {}).get("enabled", True)]

        sel = cfg.get("store_selection", {}) or {}
        raw = cfg.get("raw", {}) or {}
        http = cfg.get("http", {}) or {}
        raw_dir = Path(raw.get("dir", "data/raw"))
        if not raw_dir.is_absolute():
            raw_dir = PROJECT_ROOT / raw_dir

        return cls(
            enabled_chains=enabled,
            store_selection=StoreSelection(
                cities=[c.strip() for c in sel.get("cities", []) or [] if c and c.strip()],
                max_stores_per_chain=int(sel.get("max_stores_per_chain", 12)),
                include_store_ids={k: [int(x) for x in v] for k, v in (sel.get("include_store_ids") or {}).items()},
            ),
            file_types=list(cfg.get("file_types", ["PriceFull", "PromoFull"])),
            raw_keep=bool(raw.get("keep_files", True)),
            raw_dir=raw_dir,
            raw_retention_days=int(raw.get("retention_days", 14)),
            http_timeout=int(http.get("timeout_seconds", 60)),
            http_retries=int(http.get("retries", 3)),
            database_url=os.environ.get("DATABASE_URL"),
        )
