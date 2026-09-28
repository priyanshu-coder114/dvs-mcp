from __future__ import annotations

import json
from typing import Any

import httpx

from dvs_mcp.settings import DvsSettings

_client: DvsClient | None = None


class DvsClient:
    def __init__(
        self,
        settings: DvsSettings,
        transport: httpx.BaseTransport | None = None,
        timeout: float = 180.0,
    ) -> None:
        self.settings = settings
        self._client = httpx.Client(
            base_url=settings.base_url,
            headers=self._headers(),
            transport=transport,
            timeout=httpx.Timeout(timeout, connect=30.0),
        )

    @classmethod
    def from_env(cls) -> DvsClient:
        return cls(DvsSettings.from_env())

    def close(self) -> None:
        self._client.close()

    def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        return self._send("GET", path, params=params)

    def post(self, path: str, params: dict[str, Any] | None = None, json_body: Any = None) -> Any:
        return self._send("POST", path, params=params, json_body=json_body)

    def download(self, path: str, dest) -> dict[str, Any]:
        try:
            with self._client.stream("GET", path, headers={"Accept": "*/*"}) as response:
                if response.status_code >= 400:
                    raw = response.read()
                    return {
                        "status": response.status_code,
                        "body": _decode_bytes(raw, response.headers.get("content-type", "")),
                    }
                dest.parent.mkdir(parents=True, exist_ok=True)
                written = 0
                try:
                    with dest.open("wb") as handle:
                        for chunk in response.iter_bytes():
                            if not chunk:
                                continue
                            handle.write(chunk)
                            written += len(chunk)
                except Exception:
                    dest.unlink(missing_ok=True)
                    raise
        except httpx.HTTPError as exc:
            dest.unlink(missing_ok=True)
            return {"error": str(exc)}
        if written == 0:
            dest.unlink(missing_ok=True)
            return {"error": "DVS returned an empty drops file"}
        return {"bytes": written}

    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/json",
            "X-System-Actor": self.settings.system_actor,
            "X-Source": self.settings.source,
        }
        if self.settings.token:
            headers["X-Internal-Token"] = self.settings.token
        return headers

    def _send(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        json_body: Any = None,
    ) -> Any:
        try:
            response = self._client.request(
                method,
                path,
                params=_compact(params),
                json=json_body,
            )
        except httpx.HTTPError as exc:
            return {"error": str(exc)}
        body = _decode_response(response)
        if response.status_code >= 400:
            return {"status": response.status_code, "body": body}
        return body


def get_client() -> DvsClient:
    global _client
    if _client is None:
        _client = DvsClient.from_env()
    return _client


def set_client(client: DvsClient | None) -> None:
    global _client
    _client = client


def tracking_params(settings: DvsSettings) -> dict[str, str]:
    return {"source": settings.source, "platformType": settings.platform_type}


def freshness_params(
    max_age_days: int | None,
    force_live: bool,
    cache_only: bool = False,
) -> dict[str, Any]:
    params: dict[str, Any] = {}
    if max_age_days is not None:
        params["maxAgeDays"] = max_age_days
    if force_live:
        params["forceLive"] = "true"
    if cache_only:
        params["cacheOnly"] = "true"
    return params


def _compact(params: dict[str, Any] | None) -> dict[str, Any] | None:
    if not params:
        return None
    compact = {key: value for key, value in params.items() if value is not None}
    return compact or None


def _decode_response(response: httpx.Response) -> Any:
    return _decode_bytes(response.content, response.headers.get("content-type", ""))


def _decode_bytes(raw: bytes, content_type: str) -> Any:
    if not raw:
        return None
    if "json" in content_type or raw[:1] in (b"{", b"["):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return raw.decode(errors="replace")
    return raw.decode(errors="replace")
