from __future__ import annotations

import inspect
import json
from typing import Any, Callable


def publish(server, fn: Callable[..., Any]) -> None:
    """Register a tool that returns one JSON document."""
    server.tool(structured_output=False)(_json_result(fn))


def _json_result(fn: Callable[..., Any]) -> Callable[..., str]:
    def wrapped(*args, **kwargs) -> str:
        result = fn(*args, **kwargs)
        if isinstance(result, str):
            return result
        return json.dumps(result, indent=2, ensure_ascii=False)

    signature = inspect.signature(fn)
    wrapped.__name__ = fn.__name__
    wrapped.__doc__ = fn.__doc__
    wrapped.__module__ = fn.__module__
    wrapped.__signature__ = signature.replace(return_annotation=str)  # type: ignore[attr-defined]
    wrapped.__annotations__ = {name: param.annotation for name, param in signature.parameters.items()}
    wrapped.__annotations__["return"] = str
    return wrapped
