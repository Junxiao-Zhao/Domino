from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from omegaconf import DictConfig, OmegaConf

from domino.context import build_step_kwargs, store_result
from domino.exceptions import DominoConfigError, DominoExecutionError
from domino.loader import resolve_callable

_CTX_INTERPOLATION_PATTERN = re.compile(r"(?<!\\)\$\{ctx\.([^}:]+)\}")


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
    workflow = config.get("workflow")
    if not isinstance(workflow, Mapping):
        raise DominoConfigError("Config must define workflow as a mapping.")

    raw_step = workflow[step_name]
    if not isinstance(raw_step, Mapping):
        raise DominoConfigError(f"Workflow step '{step_name}' must be a mapping.")

    raw_kwargs = raw_step.get("kwargs") or {}
    if not isinstance(raw_kwargs, Mapping):
        raise DominoConfigError(
            f"Workflow step '{step_name}' kwargs must be a mapping."
        )

    resolver_name = f"_domino_ctx_{id(ctx)}_{id(raw_step)}"

    def resolve_ctx_reference(path: str) -> Any:
        return _select_ctx_value(ctx, path, step_name)

    OmegaConf.register_new_resolver(
        resolver_name,
        resolve_ctx_reference,
        replace=True,
        use_cache=False,
    )
    runtime_config = _rewrite_ctx_interpolations(config, resolver_name)

    try:
        runtime_cfg = OmegaConf.create(runtime_config, flags={"allow_objects": True})
        resolved_step = OmegaConf.to_container(
            runtime_cfg["workflow"][step_name],
            resolve=True,
        )
    finally:
        OmegaConf.clear_resolver(resolver_name)

    if not isinstance(resolved_step, dict):
        raise DominoConfigError(f"Workflow step '{step_name}' must be a mapping.")

    resolved_kwargs = resolved_step.get("kwargs") or {}
    if not isinstance(resolved_kwargs, Mapping):
        raise DominoConfigError(
            f"Workflow step '{step_name}' kwargs must be a mapping."
        )

    resolved_step["kwargs"] = dict(resolved_kwargs)
    return resolved_step


def _rewrite_ctx_interpolations(value: Any, resolver_name: str) -> Any:
    if isinstance(value, str):
        return _CTX_INTERPOLATION_PATTERN.sub(
            lambda match: f"${{{resolver_name}:{match.group(1)}}}",
            value,
        )

    if isinstance(value, Mapping):
        return {
            key: _rewrite_ctx_interpolations(item, resolver_name)
            for key, item in value.items()
        }

    if isinstance(value, list):
        return [_rewrite_ctx_interpolations(item, resolver_name) for item in value]

    if isinstance(value, tuple):
        return tuple(_rewrite_ctx_interpolations(item, resolver_name) for item in value)

    return value


def _select_ctx_value(
    ctx: Mapping[str, Any],
    path: str,
    step_name: Any,
) -> Any:
    parts = path.split(".")
    if any(not part for part in parts):
        raise DominoConfigError(
            f"Workflow step '{step_name}' references invalid context path 'ctx.{path}'."
        )

    root_name = parts[0]
    if root_name not in ctx:
        raise DominoConfigError(
            f"Workflow step '{step_name}' references missing context key "
            f"'ctx.{root_name}'."
        )

    value = ctx[root_name]
    resolved_path = [root_name]
    for part in parts[1:]:
        if isinstance(value, Mapping):
            if part not in value:
                missing_path = ".".join([*resolved_path, part])
                raise DominoConfigError(
                    f"Workflow step '{step_name}' references missing context key "
                    f"'ctx.{missing_path}'."
                )
            value = value[part]
        elif isinstance(value, (list, tuple)) and part.isdecimal():
            index = int(part)
            try:
                value = value[index]
            except IndexError as exc:
                missing_path = ".".join([*resolved_path, part])
                raise DominoConfigError(
                    f"Workflow step '{step_name}' references missing context index "
                    f"'ctx.{missing_path}'."
                ) from exc
        else:
            try:
                value = getattr(value, part)
            except AttributeError as exc:
                missing_path = ".".join([*resolved_path, part])
                raise DominoConfigError(
                    f"Workflow step '{step_name}' references missing context "
                    f"attribute 'ctx.{missing_path}'."
                ) from exc
        resolved_path.append(part)

    return value


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
