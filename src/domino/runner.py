from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from omegaconf import DictConfig, OmegaConf

from domino.context import build_step_kwargs, store_result
from domino.exceptions import DominoConfigError, DominoExecutionError
from domino.loader import resolve_callable


def run(cfg: DictConfig | Mapping[str, Any]) -> dict[str, Any]:
    config = _to_container(cfg, resolve=False)
    workflow = config.get("workflow")
    if not isinstance(workflow, Mapping):
        raise DominoConfigError("Config must define workflow as a mapping.")

    ctx = _initial_ctx(cfg)

    for step_name, raw_step in workflow.items():
        print(f"Start running step {step_name}...")
        if not isinstance(raw_step, Mapping):
            raise DominoConfigError(f"Workflow step '{step_name}' must be a mapping.")

        step = _resolve_step(config, step_name, ctx)

        callable_spec = step.get("callable")
        if not isinstance(callable_spec, str) or not callable_spec:
            raise DominoConfigError(
                f"Workflow step '{step_name}' must define callable."
            )

        kwargs = step.get("kwargs") or {}
        if not isinstance(kwargs, Mapping):
            raise DominoConfigError(
                f"Workflow step '{step_name}' kwargs must be a mapping."
            )

        func = resolve_callable(callable_spec, ctx)
        call_kwargs = build_step_kwargs(func, ctx, kwargs)

        try:
            result = func(**call_kwargs)
        except Exception as exc:
            raise DominoExecutionError(
                f"Workflow step '{step_name}' failed while executing '{callable_spec}'."
            ) from exc

        store_result(ctx, str(step_name), result, step.get("return_key"))
        print(f"Finish step {step_name}.")

    return ctx


def _initial_ctx(cfg: DictConfig | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(cfg, DictConfig):
        raw_ctx = cfg.get("ctx") or {}
        if isinstance(raw_ctx, DictConfig):
            container = OmegaConf.to_container(raw_ctx, resolve=True)
        else:
            container = raw_ctx
    else:
        container = cfg.get("ctx") or {}

    if not isinstance(container, Mapping):
        raise DominoConfigError("Config ctx must be a mapping when provided.")

    return dict(container)


def _resolve_step(
    config: Mapping[str, Any],
    step_name: Any,
    ctx: Mapping[str, Any],
) -> dict[str, Any]:
    runtime_config = dict(config)
    runtime_config["ctx"] = ctx
    runtime_cfg = OmegaConf.create(runtime_config, flags={"allow_objects": True})
    resolved = OmegaConf.to_container(
        runtime_cfg["workflow"][step_name],
        resolve=True,
    )

    if not isinstance(resolved, dict):
        raise DominoConfigError(f"Workflow step '{step_name}' must be a mapping.")

    return resolved


def _to_container(
    cfg: DictConfig | Mapping[str, Any],
    *,
    resolve: bool,
) -> dict[str, Any]:
    if isinstance(cfg, DictConfig):
        container = OmegaConf.to_container(cfg, resolve=resolve)
    else:
        container = dict(cfg)

    if not isinstance(container, dict):
        raise DominoConfigError("Config must be a mapping.")
    return container
