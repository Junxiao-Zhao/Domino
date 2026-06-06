# Agent Instructions

This repository implements `domino`, a lightweight serial workflow orchestration
library driven by Hydra-compatible configuration.

These instructions apply to the whole repository.

## What Domino Does

`domino` runs a configured workflow step by step. Each step names a Python
callable with `module:target`, resolves that callable's arguments from a
shared context, executes the callable once, and stores any return value back
into the context. The target may be a function name or a dotted attribute path.

The project is intentionally small. Keep changes focused on:

- context argument binding
- return-value storage
- dynamic callable loading
- serial workflow execution
- CLI/module entrypoints
- examples, tests, and package metadata

Do not add parallel execution, DAG scheduling, retries, persistence, async
execution, or plugin systems unless the user explicitly asks for them.

## Install And Verify

Use these commands from the repository root:

```bash
python -m pip install -e .
pytest -q
```

The package exposes both entrypoints:

```bash
domino --config-path examples/conf --config-name config
python -m domino --config-path examples/conf --config-name config
```

If dependencies are already installed, tests can run without reinstalling:

```bash
pytest -q
```

## Workflow Config Shape

A minimal config looks like this:

```yaml
work_dir: /tmp/domino

ctx:
  work_dir: ${work_dir}

workflow:
  func1:
    callable: "examples/steps.py:make_base"
    kwargs: {}
    return_key: null
  func2:
    callable: "examples/steps.py:split_base"
    kwargs: {}
    return_key: ["base", "length"]
```

`workflow` is executed in declaration order. Each step supports:

- `callable`: required string in `module:target` form; `target` may be dotted
- `kwargs`: optional mapping; values here override values from `ctx`
- `return_key`: optional string, list of strings, or null

## Step Function Rules

For each configured step, `domino.context.build_step_kwargs` inspects the
callable signature and builds keyword arguments.

Resolution order:

1. Use the explicit step `kwargs` value when present.
2. Preserve all explicit step `kwargs`, even keys that are not declared in the
   callable signature.
3. If the parameter name is `ctx`, pass the whole context mapping.
4. Otherwise use the value from `ctx` when present.
5. Otherwise omit the parameter from the call.

Variadic `*args` and `**kwargs` parameters are ignored by automatic binding.
Because all explicit step `kwargs` are passed through unchanged, prefer defining
workflow step functions with a `**kwargs` fallback when they may be called from
shared or evolving configs. This prevents unrelated explicit config keys from
causing `TypeError`.

Examples:

```python
def step_a(work_dir, **kwargs):
    return f"{work_dir}/result"


def step_b(ctx, **kwargs):
    return list(ctx)


def step_c(value, missing=None, **kwargs):
    assert missing is None
    return value
```

## Return Value Rules

Return values are written with `domino.context.store_result`.

- If the function returns `None`, nothing is stored.
- If `return_key` is null, the result is stored under the workflow step name.
- If `return_key` is a string, the whole result is stored under that key.
- If `return_key` is a list, the function must return a sequence of the same
  length. Sequence items are stored under the matching keys.

Invalid return-key combinations should raise `DominoConfigError`.

## Callable Loading Rules

Use `domino.loader.load_callable` for dynamic loading.

The callable spec must be `module:target`.

- If `module` resolves to an existing `.py` file path, load it from the
  filesystem.
- Relative `.py` paths are resolved against the current working directory.
- Otherwise, import `module` with `importlib.import_module`.
- The `target` side may be a single callable attribute or a dotted attribute
  path such as `api.fetch`.
- The resolved target must exist and be callable.

Loading failures should raise `DominoLoadError` with the original spec in the
message.

## CLI Rules

Keep `src/domino/cli.py` as the single CLI entrypoint. `pyproject.toml` maps the
`domino` console script to `domino.cli:main`, and `src/domino/__main__.py` calls
the same function for `python -m domino`.

Do not replace the CLI with a direct `@hydra.main` wrapper. In this package
layout, `@hydra.main` resolves relative `--config-path` values as package
modules, which breaks the expected cwd-relative command:

```bash
domino --config-path conf --config-name config
```

The current CLI intentionally parses Hydra-style flags with `argparse`, resolves
`--config-path` against `Path.cwd()`, and loads the config with Hydra Compose.
This preserves the user-facing Hydra-style command while keeping path behavior
predictable.

Hydra overrides after the known flags should be passed through to
`hydra.compose`.

## Testing Guidance

When changing context binding or return storage, run:

```bash
pytest tests/test_context.py -q
```

When changing callable loading, run:

```bash
pytest tests/test_loader.py -q
```

When changing workflow execution, run:

```bash
pytest tests/test_runner.py -q
```

When changing CLI behavior, run:

```bash
pytest tests/test_cli.py -q
domino --config-path examples/conf --config-name config
python -m domino --config-path examples/conf --config-name config
```

Before handoff, run:

```bash
pytest -q
```

## Style And Scope

- Prefer small, direct functions over framework-heavy abstractions.
- Keep source in `src/domino/`.
- Keep tests in `tests/`.
- Keep runnable examples in `examples/`.
- Use standard-library APIs unless the existing dependencies already cover the
  need.
- Keep error messages specific enough to identify the workflow step or callable
  spec that failed.
- Avoid committing generated files such as `__pycache__/`, `.pytest_cache/`,
  `*.egg-info/`, `build/`, and `dist/`.
