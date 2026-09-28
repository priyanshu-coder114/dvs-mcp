from __future__ import annotations

import json
from pathlib import Path

import httpx

from dvs_mcp.client import set_client
from dvs_mcp.client import DvsClient
from dvs_mcp.settings import DvsSettings
from dvs_mcp.tools.estibot import estibot_appraisal, estibot_siteinfo, fetch_drops
from dvs_mcp.tools.godaddy import godaddy_govalue, godaddy_govalue_bulk


def _settings(**overrides) -> DvsSettings:
    values = {
        "base_url": "http://dvs.test",
        "token": "secret",
        "source": "dashboard",
        "platform_type": "AMP2",
        "system_actor": "mcp",
        "drops_wait_seconds": 240,
    }
    values.update(overrides)
    return DvsSettings(**values)


def _use(handler, settings: DvsSettings | None = None) -> tuple[DvsClient, list[httpx.Request]]:
    seen: list[httpx.Request] = []

    def wrapped(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return handler(request)

    client = DvsClient(settings or _settings(), transport=httpx.MockTransport(wrapped))
    set_client(client)
    return client, seen


def _query(request: httpx.Request) -> dict[str, str]:
    return dict(request.url.params)


def teardown_function() -> None:
    set_client(None)


def test_appraisal_lookup_sends_headers_and_query() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"domain": "example.com", "appraised_value": 100})

    _client, seen = _use(handler)
    result = estibot_appraisal([" example.com "])

    assert result["appraised_value"] == 100
    request = seen[0]
    assert request.method == "GET"
    assert request.url.path == "/estibot/appraisal/lookup"
    assert _query(request) == {"d": "example.com", "source": "dashboard", "platformType": "AMP2"}
    assert request.headers["x-internal-token"] == "secret"
    assert request.headers["x-system-actor"] == "mcp"
    assert request.headers["x-source"] == "dashboard"


def test_appraisal_batch_posts_json_body() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[{"domain": "a.com"}, {"domain": "b.com"}])

    _client, seen = _use(handler)
    result = estibot_appraisal(["a.com", "b.com"], max_age_days=30)

    assert len(result) == 2
    request = seen[0]
    assert request.method == "POST"
    assert request.url.path == "/estibot/appraisal/lookup"
    assert json.loads(request.content) == ["a.com", "b.com"]
    assert _query(request)["maxAgeDays"] == "30"
    assert "d" not in _query(request)


def test_force_live_uses_live_path_and_rejects_max_age() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"domain": "example.com"})

    _client, seen = _use(handler)
    rejected = estibot_appraisal(["example.com"], force_live=True, max_age_days=7)
    assert rejected == {"error": "max_age_days applies only when force_live is false"}
    assert seen == []

    estibot_appraisal(["example.com"], force_live=True)
    assert seen[0].url.path == "/estibot/appraisal/live"
    assert "maxAgeDays" not in _query(seen[0])


def test_siteinfo_query() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"success": True})

    _client, seen = _use(handler)
    estibot_siteinfo("example.com", force_live=True)

    request = seen[0]
    assert request.method == "GET"
    assert request.url.path == "/estsiteinfo"
    assert _query(request)["domain"] == "example.com"
    assert _query(request)["source"] == "dashboard"
    assert _query(request)["platformType"] == "AMP2"
    assert _query(request)["forceLive"] == "true"


def test_rate_limit_is_returned_as_status_and_body() -> None:
    body = {"error": "Rate limit exceeded", "apiType": "gdv", "retryAfter": 86400, "bucket": "principal"}

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json=body)

    _client, _seen = _use(handler, _settings(token=None))
    result = godaddy_govalue("example.com")

    assert result == {"status": 429, "body": body}
    assert "x-internal-token" not in _seen[0].headers


def test_govalue_and_bulk_paths() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200, json={"domain": "example.com", "goValue": {"value": 10}})
        return httpx.Response(200, json={"a.com": {"domain": "a.com"}, "b.com": {"domain": "b.com"}})

    _client, seen = _use(handler)
    single = godaddy_govalue("example.com", cache_only=True)
    bulk = godaddy_govalue_bulk(["a.com", " b.com "], max_age_days=14)

    assert single["domain"] == "example.com"
    assert set(bulk) == {"a.com", "b.com"}
    assert seen[0].method == "GET"
    assert seen[0].url.path == "/getgdv"
    assert _query(seen[0])["cacheOnly"] == "true"
    assert seen[1].method == "POST"
    assert seen[1].url.path == "/getgdvmap"
    assert json.loads(seen[1].content) == ["a.com", "b.com"]
    assert _query(seen[1]) == {"platformType": "AMP2", "maxAgeDays": "14"}
    assert "source" not in _query(seen[1])


def test_drops_polls_then_writes_zip_without_redirect_url(tmp_path: Path) -> None:
    polls = {"count": 0}
    payload = b"PK\x03\x04zip"

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/estibot/drops/fetch":
            return httpx.Response(
                202,
                json={
                    "jobId": "job-1",
                    "status": "queued",
                    "redirectUrlOriginal": "https://www.estibot.com/secret.zip",
                },
            )
        if request.method == "GET" and request.url.path == "/estibot/drops/fetch/job-1":
            polls["count"] += 1
            status = "queued" if polls["count"] == 1 else "ready"
            return httpx.Response(
                200,
                json={
                    "jobId": "job-1",
                    "status": status,
                    "redirectUrlOriginal": "https://www.estibot.com/secret.zip",
                },
            )
        if request.url.path == "/estibot/drops/fetch/job-1/file":
            return httpx.Response(200, content=payload, headers={"content-type": "application/zip"})
        return httpx.Response(500, json={"path": request.url.path})

    client, seen = _use(handler)
    result = fetch_drops(
        "GoDaddy Expiring Auctions",
        "2026-09-28",
        client=client,
        poll_interval=0,
        output_dir=tmp_path,
    )

    assert result["status"] == "ready"
    assert result["list"] == "godaddy expiring auctions"
    assert result["date"] == "2026-09-28"
    assert result["bytes"] == len(payload)
    assert "redirectUrlOriginal" not in result
    assert "secret" not in json.dumps(result)
    written = Path(result["path"])
    assert written.read_bytes() == payload
    assert written.parent == tmp_path.resolve()
    assert written.name == "godaddy expiring auctions-2026-09-28.zip"
    assert [request.url.path for request in seen] == [
        "/estibot/drops/fetch",
        "/estibot/drops/fetch/job-1",
        "/estibot/drops/fetch/job-1",
        "/estibot/drops/fetch/job-1/file",
    ]
    assert _query(seen[0])["list"] == "godaddy expiring auctions"
    assert _query(seen[0])["date"] == "2026-09-28"
    assert _query(seen[0])["t"] == "complete"


def test_drops_timeout_returns_job_without_calling_estibot_again() -> None:
    clock = {"now": 0.0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            return httpx.Response(202, json={"jobId": "job-9", "status": "queued"})
        return httpx.Response(200, json={"jobId": "job-9", "status": "downloading"})

    def monotonic() -> float:
        clock["now"] += 100
        return clock["now"]

    client, seen = _use(handler)
    result = fetch_drops(
        "dynadot",
        "2026-09-28",
        client=client,
        wait_seconds=50,
        poll_interval=3,
        sleep=lambda _seconds: None,
        monotonic=monotonic,
    )

    assert result["status"] == "downloading"
    assert result["jobId"] == "job-9"
    assert "same list and date" in result["message"]
    assert seen[-1].url.path == "/estibot/drops/fetch/job-9"
    assert all("estibot.com" not in str(request.url) for request in seen)


def test_drops_failed_job() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            return httpx.Response(202, json={"jobId": "job-2", "status": "queued"})
        return httpx.Response(
            200,
            json={"jobId": "job-2", "status": "failed", "message": "slow down", "retryable": True, "retryAfterMs": 90000},
        )

    client, seen = _use(handler)
    result = fetch_drops("pendingdelete", "2026-01-02", client=client, poll_interval=0)

    assert result == {
        "status": "failed",
        "message": "slow down",
        "retryable": True,
        "retryAfterMs": 90000,
    }
    assert not any(request.url.path.endswith("/file") for request in seen)


def test_unknown_drop_list_does_not_call_dvs() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("DVS should not be called")

    client, seen = _use(handler)
    result = fetch_drops("namecheap", "2026-09-28", client=client)

    assert result["error"].startswith("Unknown list:")
    assert seen == []


def test_bad_drop_date_does_not_call_dvs() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("DVS should not be called")

    client, seen = _use(handler)
    result = fetch_drops("dynadot", "09/28/2026", client=client)

    assert result == {"error": "date must be yyyy-MM-dd"}
    assert seen == []


def test_tools_register() -> None:
    from mcp.server.mcpserver import MCPServer

    from dvs_mcp.tools.estibot import register as register_estibot
    from dvs_mcp.tools.godaddy import register as register_godaddy

    server = MCPServer("dvs-test")
    register_estibot(server)
    register_godaddy(server)
    tools = list(server._tool_manager.list_tools())
    names = {tool.name for tool in tools}
    assert names == {
        "estibot_appraisal",
        "estibot_siteinfo",
        "estibot_drops",
        "godaddy_govalue",
        "godaddy_govalue_bulk",
    }
    assert all(tool.output_schema is None for tool in tools)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[{"domain": "a.com"}, {"domain": "b.com"}])

    _use(handler)
    appraisal = next(tool for tool in tools if tool.name == "estibot_appraisal")
    encoded = appraisal.fn(["a.com", "b.com"])
    assert json.loads(encoded) == [{"domain": "a.com"}, {"domain": "b.com"}]
