from __future__ import annotations

import hashlib
import importlib
import importlib.util
from collections.abc import Mapping
from pathlib import Path
from types import ModuleType
from typing import Any

from domino.exceptions import DominoLoadError


def resolve_callable(spec: str, ctx: Mapping[str, Any]) -> Any:
    if spec.startswith("ctx:"):
        return load_context_callable(spec, ctx)
    return load_callable(spec)


def load_context_callable(spec: str, ctx: Mapping[str, Any]) -> Any:
    if ":" not in spec:
        raise DominoLoadError(
            f"Callable spec '{spec}' must use 'ctx:object.method' format."
        )

    namespace, target_name = spec.split(":", 1)
    if namespace != "ctx" or not target_name:
        raise DominoLoadError(
            f"Callable spec '{spec}' must use 'ctx:object.method' format."
        )

    target_parts = target_name.split(".")
    if any(not part for part in target_parts):
        raise DominoLoadError(
            f"Callable spec '{spec}' must use 'ctx:object.method' format."
        )

    root_name = target_parts[0]
    if root_name not in ctx:
        raise DominoLoadError(
            f"Callable spec '{spec}' references missing context key '{root_name}'."
        )

    target: Any = ctx[root_name]
    resolved_parts = [root_name]
    for part in target_parts[1:]:
        try:
            target = getattr(target, part)
        except AttributeError as exc:
            missing_target = ".".join([*resolved_parts, part])
            raise DominoLoadError(
                f"Callable spec '{spec}' references missing context target "
                f"'{missing_target}'."
            ) from exc
        resolved_parts.append(part)

    if not callable(target):
        raise DominoLoadError(
            f"Callable spec '{spec}' resolved target is not callable."
        )

    return target


def load_callable(spec: str) -> Any:
    if ":" not in spec:
        raise DominoLoadError(f"Callable spec '{spec}' must use 'module:func' format.")

    module_name, target_name = spec.split(":", 1)
    if not module_name or not target_name:
        raise DominoLoadError(f"Callable spec '{spec}' must use 'module:func' format.")

    module = _load_module(module_name, spec)
    target = _resolve_target(module, target_name, spec)

    if not callable(target):
        raise DominoLoadError(
            f"Callable spec '{spec}' resolved target is not callable."
        )

    return target


def _resolve_target(module: ModuleType, target_name: str, spec: str) -> Any:
    target: Any = module
    resolved_parts: list[str] = []

    for part in target_name.split("."):
        if not part:
            raise DominoLoadError(
                f"Callable spec '{spec}' must use 'module:func' format."
            )
        try:
            target = getattr(target, part)
        except AttributeError as exc:
            missing_target = ".".join([*resolved_parts, part])
            raise DominoLoadError(
                f"Callable spec '{spec}' references missing function '{missing_target}'."
            ) from exc
        resolved_parts.append(part)

    return target


def _load_module(module_name: str, spec: str) -> ModuleType:
    path = Path(module_name)
    if not path.is_absolute():
        path = Path.cwd() / path

    if path.exists() and path.suffix == ".py":
        return _load_module_from_path(path, spec)

    try:
        return importlib.import_module(module_name)
    except Exception as exc:
        raise DominoLoadError(
            f"Could not import module for callable spec '{spec}'."
        ) from exc


def _load_module_from_path(path: Path, spec: str) -> ModuleType:
    resolved_path = path.resolve()
    digest = hashlib.sha1(str(resolved_path).encode("utf-8")).hexdigest()[:12]
    synthetic_name = f"_domino_loaded_{resolved_path.stem}_{digest}"
    module_spec = importlib.util.spec_from_file_location(synthetic_name, resolved_path)
    if module_spec is None or module_spec.loader is None:
        raise DominoLoadError(f"Could not load module from callable spec '{spec}'.")

    module = importlib.util.module_from_spec(module_spec)
    try:
        module_spec.loader.exec_module(module)
    except Exception as exc:
        raise DominoLoadError(
            f"Could not execute module for callable spec '{spec}'."
        ) from exc
    return module
