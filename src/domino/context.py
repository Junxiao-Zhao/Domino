from __future__ import annotations

import inspect
from collections.abc import Callable, Mapping, MutableMapping, Sequence
from typing import Any

from domino.exceptions import DominoConfigError


def build_step_kwargs(
    func: Callable[..., Any],
    ctx: Mapping[str, Any],
    kwargs: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    explicit_kwargs = dict(kwargs or {})
    signature = inspect.signature(func)
    resolved: dict[str, Any] = dict(explicit_kwargs)

    for name, parameter in signature.parameters.items():
        if parameter.kind in (
            inspect.Parameter.VAR_POSITIONAL,
            inspect.Parameter.VAR_KEYWORD,
        ):
            continue

        if name in resolved:
            continue
        elif name == "ctx":
            resolved[name] = ctx
        elif name in ctx:
            resolved[name] = ctx[name]

    return resolved


def store_result(
    ctx: MutableMapping[str, Any],
    step_name: str,
    result: Any,
    return_key: str | Sequence[str] | None,
) -> None:
    if result is None:
        return

    if return_key is None:
        ctx[step_name] = result
        return

    if isinstance(return_key, str):
        ctx[return_key] = result
        return

    if isinstance(return_key, Sequence):
        if not isinstance(result, Sequence):
            raise DominoConfigError(
                f"Step '{step_name}' must return a sequence when return_key is a list."
            )
        if len(result) != len(return_key):
            raise DominoConfigError(
                f"Step '{step_name}' return_key length {len(return_key)} does not "
                f"match result length {len(result)}."
            )
        for key, value in zip(return_key, result, strict=True):
            ctx[str(key)] = value
        return

    raise DominoConfigError(
        f"Step '{step_name}' return_key must be null, a string, or a list of strings."
    )
