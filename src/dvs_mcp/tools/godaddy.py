from __future__ import annotations

from typing import Annotated, Any

from pydantic import Field

from dvs_mcp.client import freshness_params, get_client, tracking_params
from dvs_mcp.publish import LOOKUP_ANNOTATIONS, publish
from dvs_mcp.validate import (
    MAX_DOMAINS,
    InputError,
    check_cache_flags,
    check_max_age,
    error_result,
    normalize_domain,
    normalize_domains,
)


def godaddy_govalue(
    domain: Annotated[str, Field(description="One bare domain, such as example.com.")],
    max_age_days: Annotated[
        int | None,
        Field(
            description=(
                "Maximum age in days of a saved GoValue. Applies only when force_live is false. "
                "Passing it together with force_live is an error."
            )
        ),
    ] = None,
    force_live: Annotated[
        bool,
        Field(
            description=(
                "Spend a paid GoDaddy GoValue lookup and skip caches. Leave false unless the user "
                "explicitly asks for a new paid lookup. Cannot be combined with max_age_days or cache_only."
            )
        ),
    ] = False,
    cache_only: Annotated[
        bool,
        Field(
            description=(
                "Return only saved GoValue data. A cache miss must not call GoDaddy. "
                "Cannot be combined with force_live."
            )
        ),
    ] = False,
) -> Any:
    """Return the GoDaddy GoValue for one domain through DVS GET /getgdv.

    Leave force_live false unless the user explicitly asks for a new paid lookup.
    force_live spends vendor quota and cannot be combined with max_age_days or cache_only.
    """
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
    domains: Annotated[
        list[str],
        Field(description=f"Bare domains such as example.com. At most {MAX_DOMAINS}."),
    ],
    max_age_days: Annotated[
        int | None,
        Field(
            description=(
                "Maximum age in days of a saved GoValue. Applies only when force_live is false. "
                "Passing it together with force_live is an error."
            )
        ),
    ] = None,
    force_live: Annotated[
        bool,
        Field(
            description=(
                "Spend paid GoDaddy GoValue lookups and skip caches. Leave false unless the user "
                "explicitly asks for a new paid lookup. Cannot be combined with max_age_days or cache_only."
            )
        ),
    ] = False,
    cache_only: Annotated[
        bool,
        Field(
            description=(
                "Return only saved GoValue data. A cache miss must not call GoDaddy. "
                "Cannot be combined with force_live."
            )
        ),
    ] = False,
) -> Any:
    """Return GoDaddy GoValue for many domains through DVS POST /getgdvmap.

    At most 50 domains. This endpoint does not receive the source tracking
    parameter. Leave force_live false unless the user explicitly asks for a new
    paid lookup. force_live spends vendor quota and cannot be combined with
    max_age_days or cache_only.
    """
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
    publish(server, godaddy_govalue, LOOKUP_ANNOTATIONS)
    publish(server, godaddy_govalue_bulk, LOOKUP_ANNOTATIONS)
