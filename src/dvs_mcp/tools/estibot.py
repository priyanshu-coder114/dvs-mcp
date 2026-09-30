from __future__ import annotations

import time
from pathlib import Path
from typing import Annotated, Any, Callable

from pydantic import Field

from dvs_mcp.client import DvsClient, freshness_params, get_client, tracking_params
from dvs_mcp.publish import DROPS_ANNOTATIONS, LOOKUP_ANNOTATIONS, publish
from dvs_mcp.validate import (
    ALLOWED_DROP_LISTS,
    MAX_DOMAINS,
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
    normalize_job_id,
)

_DROP_LISTS = ", ".join(sorted(ALLOWED_DROP_LISTS))
_STILL_RUNNING = (
    "Drops job is still running. Call estibot_drops_status with this jobId, drop_list, and drop_date."
)


def estibot_appraisal(
    domains: Annotated[
        list[str],
        Field(description=f"Bare domains such as example.com. At most {MAX_DOMAINS}. One domain uses GET; several use POST."),
    ],
    force_live: Annotated[
        bool,
        Field(
            description=(
                "Spend a paid Estibot appraisal and skip caches. Leave false unless the user "
                "explicitly asks for a new paid lookup. Cannot be combined with max_age_days."
            )
        ),
    ] = False,
    max_age_days: Annotated[
        int | None,
        Field(
            description=(
                "Maximum age in days of a saved appraisal. Applies only when force_live is false. "
                "Passing it together with force_live is an error."
            )
        ),
    ] = None,
) -> Any:
    """Look up Estibot appraisals through DVS.

    One domain uses GET. Several domains use POST, at most 50. The default path
    checks saved data, then Estibot cache, then a live appraisal. Leave force_live
    false unless the user explicitly asks for a new paid lookup. force_live spends
    vendor quota and cannot be combined with max_age_days.
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
    domain: Annotated[str, Field(description="One bare domain, such as example.com.")],
    max_age_days: Annotated[
        int | None,
        Field(
            description=(
                "Maximum age in days of saved site info. Applies only when force_live is false. "
                "Passing it together with force_live is an error."
            )
        ),
    ] = None,
    force_live: Annotated[
        bool,
        Field(
            description=(
                "Spend a paid Estibot site-info lookup and skip caches. Leave false unless the user "
                "explicitly asks for a new paid lookup. Cannot be combined with max_age_days or cache_only."
            )
        ),
    ] = False,
    cache_only: Annotated[
        bool,
        Field(
            description=(
                "Return only saved site info. A cache miss must not call Estibot. "
                "Cannot be combined with force_live."
            )
        ),
    ] = False,
) -> Any:
    """Fetch Estibot site info for one domain through DVS GET /estsiteinfo.

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
    return client.get("/estsiteinfo", params)


def estibot_drops(
    drop_list: Annotated[str, Field(description=f"Drop list name. One of: {_DROP_LISTS}.")],
    drop_date: Annotated[str, Field(description="Drop date in yyyy-MM-dd.")],
    drop_type: Annotated[
        str,
        Field(description="Estibot drop file type. Use complete unless the user names another type."),
    ] = "complete",
) -> dict[str, Any]:
    """Download an Estibot daily drop ZIP through DVS.

    Starts the job and waits only for the configured drops budget (25 seconds by
    default). When the ZIP is ready, the result path is an absolute path on the
    machine running this server, not a chat attachment. The tool does not return
    the file bytes or Estibot's download URL. If the result is still running,
    call estibot_drops_status with the returned jobId, drop_list, and drop_date.
    DVS reuses that job for 12 hours.
    """
    return fetch_drops(drop_list, drop_date, drop_type)


def estibot_drops_status(
    job_id: Annotated[str, Field(description="jobId returned by estibot_drops.")],
    drop_list: Annotated[str, Field(description=f"Same drop list passed to estibot_drops. One of: {_DROP_LISTS}.")],
    drop_date: Annotated[str, Field(description="Same yyyy-MM-dd date passed to estibot_drops.")],
) -> dict[str, Any]:
    """Poll an existing Estibot drops job and download the ZIP when it is ready.

    Does not start a new job. The ZIP is written on the machine running this
    server. The result path is an absolute local path, not a chat attachment.
    If the job is still running, call this tool again with the same arguments.
    """
    return poll_drops(job_id, drop_list, drop_date)


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
    if _is_failure(started):
        return started
    job_id = started.get("jobId") if isinstance(started, dict) else None
    if not job_id or "/" in str(job_id) or ".." in str(job_id):
        return {"error": "DVS did not return a drops job id", "body": started}
    return _poll_job(
        active,
        str(job_id),
        resolved_list,
        resolved_date,
        budget,
        poll_interval=poll_interval,
        output_dir=output_dir,
        sleep=sleep,
        monotonic=monotonic,
    )


def poll_drops(
    job_id: str,
    drop_list: str,
    drop_date: str,
    *,
    client: DvsClient | None = None,
    poll_interval: float = 3.0,
    wait_seconds: float | None = None,
    output_dir: Path | None = None,
    sleep: Callable[[float], None] = time.sleep,
    monotonic: Callable[[], float] = time.monotonic,
) -> dict[str, Any]:
    try:
        resolved_id = normalize_job_id(job_id)
        resolved_list = normalize_drop_list(drop_list)
        resolved_date = normalize_drop_date(drop_date)
    except InputError as exc:
        return error_result(exc)

    active = client or get_client()
    budget = active.settings.drops_wait_seconds if wait_seconds is None else wait_seconds
    return _poll_job(
        active,
        resolved_id,
        resolved_list,
        resolved_date,
        budget,
        poll_interval=poll_interval,
        output_dir=output_dir,
        sleep=sleep,
        monotonic=monotonic,
    )


def _poll_job(
    active: DvsClient,
    job_id: str,
    drop_list: str,
    drop_date: str,
    budget: float,
    *,
    poll_interval: float,
    output_dir: Path | None,
    sleep: Callable[[float], None],
    monotonic: Callable[[], float],
) -> dict[str, Any]:
    deadline = monotonic() + budget
    status_path = f"/estibot/drops/fetch/{job_id}"
    while True:
        job = active.get(status_path)
        if _is_failure(job):
            return job
        status = job.get("status") if isinstance(job, dict) else None
        if status == "ready":
            return _download_ready(active, job_id, drop_list, drop_date, output_dir)
        if status == "failed":
            return {
                "status": "failed",
                "message": job.get("message"),
                "retryable": job.get("retryable"),
                "retryAfterMs": job.get("retryAfterMs"),
            }
        if monotonic() >= deadline:
            return {"status": status, "jobId": job_id, "message": _STILL_RUNNING}
        sleep(poll_interval)


def _download_ready(
    client: DvsClient,
    job_id: str,
    drop_list: str,
    drop_date: str,
    output_dir: Path | None,
) -> dict[str, Any]:
    dest = drop_destination(output_dir or client.settings.drops_output_dir, drop_list, drop_date)
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


def _is_failure(payload: Any) -> bool:
    return isinstance(payload, dict) and isinstance(payload.get("error"), str)


def register(server) -> None:
    publish(server, estibot_appraisal, LOOKUP_ANNOTATIONS)
    publish(server, estibot_siteinfo, LOOKUP_ANNOTATIONS)
    publish(server, estibot_drops, DROPS_ANNOTATIONS)
    publish(server, estibot_drops_status, DROPS_ANNOTATIONS)
