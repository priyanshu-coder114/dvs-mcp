from __future__ import annotations

from typing import Any

from dvs_mcp.client import freshness_params, get_client, tracking_params
from dvs_mcp.publish import publish
from dvs_mcp.validate import (
    InputError,
    check_cache_flags,
    check_max_age,
    error_result,
    normalize_domain,
    normalize_domains,
)


def godaddy_govalue(
    domain: str,
    max_age_days: int | None = None,
    force_live: bool = False,
    cache_only: bool = False,
) -> Any:
    """Return the GoDaddy GoValue for one domain through DVS GET /getgdv."""
    try:
        cleaned = normalize_domain(domain)
        check_cache_flags(force_live, cache_only)
        max_age = check_max_age(max_age_days, force_live)
    except InputError as exc:
        return error_result(exc)
    client = get_client()
    params = {
        "domain": cleaned,
        **tracking_params(client.settings),
        **freshness_params(max_age, force_live, cache_only),
    }
    return client.get("/getgdv", params)


def godaddy_govalue_bulk(
    domains: list[str],
    max_age_days: int | None = None,
    force_live: bool = False,
    cache_only: bool = False,
) -> Any:
    """Return GoDaddy GoValue for many domains through DVS POST /getgdvmap."""
    try:
        cleaned = normalize_domains(domains)
        check_cache_flags(force_live, cache_only)
        max_age = check_max_age(max_age_days, force_live)
    except InputError as exc:
        return error_result(exc)
    client = get_client()
    params = {
        "platformType": client.settings.platform_type,
        **freshness_params(max_age, force_live, cache_only),
    }
    return client.post("/getgdvmap", params, cleaned)


def register(server) -> None:
    publish(server, godaddy_govalue)
    publish(server, godaddy_govalue_bulk)
