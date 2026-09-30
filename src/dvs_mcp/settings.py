from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DvsSettings:
    base_url: str
    token: str | None
    source: str
    platform_type: str
    system_actor: str
    drops_wait_seconds: float
    drops_output_dir: Path

    @classmethod
    def from_env(cls) -> DvsSettings:
        raw_wait = os.environ.get("DVS_DROPS_WAIT_SECONDS", "25").strip() or "25"
        try:
            wait = float(raw_wait)
        except ValueError as exc:
            raise ValueError("DVS_DROPS_WAIT_SECONDS must be a number of seconds") from exc
        if wait <= 0:
            raise ValueError("DVS_DROPS_WAIT_SECONDS must be positive")
        token = os.environ.get("DVS_INTERNAL_TOKEN", "").strip()
        raw_dir = os.environ.get("DVS_DROPS_OUTPUT_DIR", "output/estibot-drops").strip() or "output/estibot-drops"
        return cls(
            base_url=os.environ.get("DVS_BASE_URL", "http://localhost:90").strip().rstrip("/")
            or "http://localhost:90",
            token=token or None,
            source=os.environ.get("DVS_SOURCE", "dashboard").strip() or "dashboard",
            platform_type=os.environ.get("DVS_PLATFORM_TYPE", "AMP2").strip() or "AMP2",
            system_actor=os.environ.get("DVS_SYSTEM_ACTOR", "mcp").strip() or "mcp",
            drops_wait_seconds=wait,
            drops_output_dir=Path(raw_dir).expanduser().resolve(),
        )
