from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

ALLOWED_DROP_LISTS = frozenset(
    {
        "dynadot",
        "dropcatch",
        "redemptionperiod",
        "snapnames exclusive drops",
        "godaddy expiring auctions",
        "pendingdelete",
    }
)

MAX_DOMAINS = 50

_UNSAFE_FILENAME = re.compile(r"[^A-Za-z0-9._ -]+")
_DOMAIN = re.compile(r"^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,}$")


class InputError(Exception):
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


def error_result(exc: InputError) -> dict:
    return {"error": exc.message}


def normalize_domain(domain: str) -> str:
    cleaned = domain.strip().lower()
    if cleaned.startswith("https://"):
        cleaned = cleaned[len("https://") :]
    elif cleaned.startswith("http://"):
        cleaned = cleaned[len("http://") :]
    cleaned = cleaned.split("/")[0].split("?")[0].split("#")[0]
    if cleaned.endswith("."):
        cleaned = cleaned[:-1]
    if not cleaned or not _DOMAIN.fullmatch(cleaned):
        raise InputError(f"invalid domain: {domain.strip()}")
    return cleaned


def normalize_domains(domains: list[str]) -> list[str]:
    present = [domain for domain in domains if domain and domain.strip()]
    if not present:
        raise InputError("at least one domain is required")
    if len(present) > MAX_DOMAINS:
        raise InputError(f"at most {MAX_DOMAINS} domains are allowed")
    return [normalize_domain(domain) for domain in present]


def check_max_age(max_age_days: int | None, force_live: bool) -> int | None:
    if max_age_days is None:
        return None
    if force_live:
        raise InputError("max_age_days applies only when force_live is false")
    if isinstance(max_age_days, bool) or not isinstance(max_age_days, int) or max_age_days < 1:
        raise InputError("max_age_days must be a positive integer")
    return max_age_days


def check_cache_flags(force_live: bool, cache_only: bool) -> None:
    if force_live and cache_only:
        raise InputError("force_live and cache_only cannot both be true")


def normalize_drop_list(value: str) -> str:
    cleaned = " ".join(value.strip().lower().split())
    if cleaned not in ALLOWED_DROP_LISTS:
        allowed = ", ".join(sorted(ALLOWED_DROP_LISTS))
        raise InputError(f"Unknown list: {value.strip()}. Allowed lists: {allowed}")
    return cleaned


def normalize_drop_date(value: str) -> str:
    try:
        parsed = datetime.strptime(value.strip(), "%Y-%m-%d")
    except ValueError as exc:
        raise InputError("date must be yyyy-MM-dd") from exc
    return parsed.date().isoformat()


def normalize_drop_type(value: str) -> str:
    cleaned = value.strip()
    return cleaned or "complete"


def normalize_job_id(job_id: str) -> str:
    cleaned = job_id.strip()
    if not cleaned or "/" in cleaned or ".." in cleaned:
        raise InputError("invalid drops job id")
    return cleaned


def drop_destination(output_dir: Path, drop_list: str, drop_date: str) -> Path:
    root = output_dir.expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    cleaned = _UNSAFE_FILENAME.sub("-", drop_list).replace("..", "").strip(" .-")
    if not cleaned:
        cleaned = "drops"
    dest = (root / f"{cleaned}-{drop_date}.zip").resolve()
    if dest.parent != root:
        raise InputError("unsafe drops filename")
    return dest
