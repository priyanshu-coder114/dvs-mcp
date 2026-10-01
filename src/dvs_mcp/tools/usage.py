from __future__ import annotations

from typing import Annotated, Any

from pydantic import Field

from dvs_mcp.client import get_client
from dvs_mcp.publish import LOOKUP_ANNOTATIONS, publish
from dvs_mcp.validate import InputError, error_result, normalize_drop_date


def usage(
    date: Annotated[
        str | None,
        Field(description="Usage date in yyyy-MM-dd. Omit for today."),
    ] = None,
) -> Any:
    """Return usage for every upstream API through DVS GET /usage.

    Omit date for today. Pass yyyy-MM-dd for another day. The apis list covers
    gdv, estap, estsiteinfo, estleads, dotdb, and domainiq. Each item includes
    calls, cacheHits, blocked, errors, domains, pool, and dailyLimits.
    """
    try:
        params = _date_params(date)
    except InputError as exc:
        return error_result(exc)
    return get_client().get("/usage", params)


def domainiq_usage(
    date: Annotated[
        str | None,
        Field(description="Usage date in yyyy-MM-dd. Omit for today."),
    ] = None,
) -> Any:
    """Return DomainIQ usage through DVS GET /usage/domainiq.

    Same totals as one provider in usage, plus byPlatform, byCaller, operations
    (whois, Telegram whois, live snapshot, saved snapshot), callsBySource
    (dashboard, live, livy, other), and notCounted. Omit date for today.
    """
    try:
        params = _date_params(date)
    except InputError as exc:
        return error_result(exc)
    return get_client().get("/usage/domainiq", params)


def _date_params(date: str | None) -> dict[str, str] | None:
    if date is None:
        return None
    return {"date": normalize_drop_date(date)}


def register(server) -> None:
    publish(server, usage, LOOKUP_ANNOTATIONS)
    publish(server, domainiq_usage, LOOKUP_ANNOTATIONS)
