from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from omegaconf import DictConfig, OmegaConf

from domino.context import build_step_kwargs, store_result
from domino.exceptions import DominoConfigError, DominoExecutionError
from domino.loader import load_callable


def run(cfg: DictConfig | Mapping[str, Any]) -> dict[str, Any]:
    config = _to_container(cfg)
    workflow = config.get("workflow")
    if not isinstance(workflow, Mapping):
        raise DominoConfigError("Config must define workflow as a mapping.")

    raw_ctx = config.get("ctx") or {}
    if not isinstance(raw_ctx, Mapping):
        raise DominoConfigError("Config ctx must be a mapping when provided.")
    ctx = dict(raw_ctx)

    for step_name, raw_step in workflow.items():
        if not isinstance(raw_step, Mapping):
            raise DominoConfigError(f"Workflow step '{step_name}' must be a mapping.")

        callable_spec = raw_step.get("callable")
        if not isinstance(callable_spec, str) or not callable_spec:
            raise DominoConfigError(
                f"Workflow step '{step_name}' must define callable."
            )

        raw_kwargs = raw_step.get("kwargs") or {}
        if not isinstance(raw_kwargs, Mapping):
            raise DominoConfigError(
                f"Workflow step '{step_name}' kwargs must be a mapping."
            )

        func = load_callable(callable_spec)
        call_kwargs = build_step_kwargs(func, ctx, raw_kwargs)

        try:
            result = func(**call_kwargs)
        except Exception as exc:
            raise DominoExecutionError(
                f"Workflow step '{step_name}' failed while executing '{callable_spec}'."
            ) from exc

        store_result(ctx, str(step_name), result, raw_step.get("return_key"))

    return ctx


def _to_container(cfg: DictConfig | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(cfg, DictConfig):
        container = OmegaConf.to_container(cfg, resolve=True)
    else:
        container = dict(cfg)

    if not isinstance(container, dict):
        raise DominoConfigError("Config must be a mapping.")
    return container
