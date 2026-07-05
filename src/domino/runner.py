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

    step_state: dict[str, Any] = {"step_name": None}
    runtime_cfg, resolver_name = _runtime_config(config, ctx, step_state)
    try:
        for step_name, raw_step in workflow.items():
            print(f"Start running step {step_name}...")
            if not isinstance(raw_step, Mapping):
                raise DominoConfigError(
                    f"Workflow step '{step_name}' must be a mapping."
                )

            step_state["step_name"] = step_name
            step = _resolve_step(runtime_cfg, step_name)

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
                    f"Workflow step '{step_name}' failed while executing "
                    f"'{callable_spec}'."
                ) from exc

            store_result(ctx, str(step_name), result, step.get("return_key"))
            print(f"Finish step {step_name}.")
    finally:
        OmegaConf.clear_resolver(resolver_name)

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


def _runtime_config(
    config: Mapping[str, Any],
    ctx: Mapping[str, Any],
    step_state: Mapping[str, Any],
) -> tuple[Any, str]:
    resolver_name = f"_domino_ctx_{id(ctx)}"

    def resolve_ctx_reference(path: str) -> Any:
        step_name = step_state["step_name"]
        return _select_ctx_value(ctx, path, step_name)

    OmegaConf.register_new_resolver(
        resolver_name,
        resolve_ctx_reference,
        replace=True,
        use_cache=False,
    )
    try:
        runtime_config = _rewrite_ctx_interpolations(config, resolver_name)
        runtime_cfg = OmegaConf.create(runtime_config, flags={"allow_objects": True})
    except Exception:
        OmegaConf.clear_resolver(resolver_name)
        raise

    return runtime_cfg, resolver_name


def _resolve_step(runtime_cfg: Any, step_name: Any) -> dict[str, Any]:
    resolved_step = OmegaConf.to_container(
        runtime_cfg["workflow"][step_name],
        resolve=True,
    )
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
