from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Callable

from dvs_mcp.client import DvsClient, freshness_params, get_client, tracking_params
from dvs_mcp.publish import publish
from dvs_mcp.validate import (
    InputError,
    check_cache_flags,
    check_max_age,
    drop_destination,
    error_result,
    normalize_domain,
    normalize_domains,
    normalize_drop_date,
    normalize_drop_list,
    normalize_drop_type,
)


def estibot_appraisal(
    domains: list[str],
    force_live: bool = False,
    max_age_days: int | None = None,
) -> Any:
    """Look up Estibot appraisals through DVS.

    One domain uses GET. Several domains use POST. The default path checks
    saved data, then Estibot cache, then a live appraisal. Set force_live to
    skip caches. max_age_days limits how old a saved appraisal can be and is
    ignored unless force_live is false.
    """
    try:
        cleaned = normalize_domains(domains)
        max_age = check_max_age(max_age_days, force_live)
    except InputError as exc:
        return error_result(exc)
    client = get_client()
    path = "/estibot/appraisal/live" if force_live else "/estibot/appraisal/lookup"
    params = tracking_params(client.settings)
    if max_age is not None:
        params["maxAgeDays"] = max_age
    if len(cleaned) == 1:
        params["d"] = cleaned[0]
        return client.get(path, params)
    return client.post(path, params, cleaned)


def estibot_siteinfo(
    domain: str,
    max_age_days: int | None = None,
    force_live: bool = False,
    cache_only: bool = False,
) -> Any:
    """Fetch Estibot site info for one domain through DVS GET /estsiteinfo."""
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
    return client.get("/estsiteinfo", params)


def estibot_drops(list: str, date: str, t: str = "complete") -> dict[str, Any]:
    """Download an Estibot daily drop ZIP through DVS.

    list is one of: dynadot, dropcatch, redemptionperiod,
    snapnames exclusive drops, godaddy expiring auctions, pendingdelete.
    date is yyyy-MM-dd. The tool waits for DVS to finish and returns the local
    ZIP path. It does not return the file bytes or Estibot's download URL.
    If the result status is still running, call this tool again with the same
    list and date. DVS reuses that job for 12 hours.
    """
    return fetch_drops(list, date, t)


def fetch_drops(
    drop_list: str,
    drop_date: str,
    drop_type: str = "complete",
    *,
    client: DvsClient | None = None,
    poll_interval: float = 3.0,
    wait_seconds: float | None = None,
    output_dir: Path | None = None,
    sleep: Callable[[float], None] = time.sleep,
    monotonic: Callable[[], float] = time.monotonic,
) -> dict[str, Any]:
    try:
        resolved_list = normalize_drop_list(drop_list)
        resolved_date = normalize_drop_date(drop_date)
        resolved_type = normalize_drop_type(drop_type)
    except InputError as exc:
        return error_result(exc)

    active = client or get_client()
    budget = active.settings.drops_wait_seconds if wait_seconds is None else wait_seconds
    params = {
        "list": resolved_list,
        "date": resolved_date,
        "t": resolved_type,
        **tracking_params(active.settings),
    }
    started = active.post("/estibot/drops/fetch", params)
    if _is_http_error(started):
        return started
    job_id = started.get("jobId") if isinstance(started, dict) else None
    if not job_id or "/" in str(job_id) or ".." in str(job_id):
        return {"error": "DVS did not return a drops job id", "body": started}

    deadline = monotonic() + budget
    status_path = f"/estibot/drops/fetch/{job_id}"
    while True:
        job = active.get(status_path)
        if _is_http_error(job):
            return job
        status = job.get("status") if isinstance(job, dict) else None
        if status == "ready":
            return _download_ready(active, job_id, resolved_list, resolved_date, output_dir)
        if status == "failed":
            return {
                "status": "failed",
                "message": job.get("message"),
                "retryable": job.get("retryable"),
                "retryAfterMs": job.get("retryAfterMs"),
            }
        if monotonic() >= deadline:
            return {
                "status": status,
                "jobId": job_id,
                "message": "Drops job is still running. Call estibot_drops again with the same list and date.",
            }
        sleep(poll_interval)


def _download_ready(
    client: DvsClient,
    job_id: str,
    drop_list: str,
    drop_date: str,
    output_dir: Path | None,
) -> dict[str, Any]:
    dest = drop_destination(output_dir or Path("output") / "estibot-drops", drop_list, drop_date)
    saved = client.download(f"/estibot/drops/fetch/{job_id}/file", dest)
    if "bytes" not in saved:
        return saved
    return {
        "status": "ready",
        "path": str(dest),
        "bytes": saved["bytes"],
        "list": drop_list,
        "date": drop_date,
    }


def _is_http_error(payload: Any) -> bool:
    return isinstance(payload, dict) and isinstance(payload.get("status"), int)


def register(server) -> None:
    publish(server, estibot_appraisal)
    publish(server, estibot_siteinfo)
    publish(server, estibot_drops)
