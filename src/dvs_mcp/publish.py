from __future__ import annotations

import inspect
import json
from typing import Any, Callable, get_type_hints

from mcp_types import ToolAnnotations

LOOKUP_ANNOTATIONS = ToolAnnotations(
    read_only_hint=True,
    destructive_hint=False,
    idempotent_hint=True,
    open_world_hint=True,
)
DROPS_ANNOTATIONS = ToolAnnotations(
    read_only_hint=False,
    destructive_hint=False,
    idempotent_hint=True,
    open_world_hint=True,
)


def publish(server, fn: Callable[..., Any], annotations: ToolAnnotations | None = None) -> None:
    """Register a tool that returns one JSON document."""
    server.tool(structured_output=False, annotations=annotations)(_json_result(fn))


def _json_result(fn: Callable[..., Any]) -> Callable[..., str]:
    def wrapped(*args, **kwargs) -> str:
        result = fn(*args, **kwargs)
        if isinstance(result, str):
            return result
        return json.dumps(result, indent=2, ensure_ascii=False)

    hints = get_type_hints(fn, include_extras=True)
    signature = inspect.signature(fn)
    parameters = [
        param.replace(annotation=hints.get(name, param.annotation))
        for name, param in signature.parameters.items()
    ]
    wrapped.__name__ = fn.__name__
    wrapped.__doc__ = fn.__doc__
    wrapped.__module__ = fn.__module__
    wrapped.__signature__ = signature.replace(parameters=parameters, return_annotation=str)  # type: ignore[attr-defined]
    wrapped.__annotations__ = {name: hints[name] for name in signature.parameters if name in hints}
    wrapped.__annotations__["return"] = str
    return wrapped
