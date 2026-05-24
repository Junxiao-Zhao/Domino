---
name: domino-orchestrator
description: Use when a project should use the domino Python library as a lightweight Hydra-configured serial workflow orchestrator, including creating workflow YAML configs, writing Python step functions, wiring ctx data flow, loading functions with module:func specs, and running workflows with domino or python -m domino.
---

# Domino Orchestrator

Use `domino` when a project needs a simple serial workflow runner configured by
Hydra-compatible YAML. Prefer it for ordered data jobs, scripts, ETL-like
pipelines, research workflows, or project automation where a shared context
dictionary is enough.

Do not use `domino` for DAG scheduling, parallel execution, retries, async
execution, persistent state, or distributed orchestration unless those features
are added explicitly.

## Setup In A Project

Install `domino` in the target project environment:

```bash
python -m pip install git+https://github.com/Junxiao-Zhao/Domino
```

If using a local checkout of this repository:

```bash
python -m pip install -e /path/to/domino
```

Use this project layout unless the target project already has conventions:

```text
conf/workflow/
  my_workflow.yaml
workflow_steps/
  steps.py
```

Run workflows from the target project root:

```bash
domino --config-path conf/workflow --config-name my_workflow
python -m domino --config-path conf/workflow --config-name my_workflow
```

Hydra overrides can follow the known flags:

```bash
domino --config-path conf/workflow --config-name my_workflow ++ctx.trade_date=20260524
```

## Config Pattern

Create a YAML config with `ctx` and ordered `workflow` sections:

```yaml
work_dir: /tmp/project-work

ctx:
  work_dir: ${work_dir}
  trade_date: 20260524

workflow:
  load_data:
    callable: "workflow_steps/steps.py:load_data"
    kwargs: {}
    return_key: data

  transform:
    callable: "workflow_steps/steps.py:transform"
    kwargs:
      mode: fast
    return_key: transformed

  save:
    callable: "workflow_steps/steps.py:save"
    kwargs: {}
    return_key: null
```

Workflow steps execute in YAML declaration order.

Each step supports:

- `callable`: required `module:func_name` string.
- `kwargs`: optional explicit keyword arguments.
- `return_key`: optional key, list of keys, or null.

The `module` part can be an importable Python module or a `.py` file path.
Relative file paths are resolved from the current working directory.

## Step Function Pattern

Define step functions as plain Python functions. Domino builds call arguments
from explicit step `kwargs` first, then fills missing signature parameters from
`ctx`.

Recommended pattern:

```python
def load_data(work_dir, trade_date, **kwargs):
    return {"work_dir": work_dir, "trade_date": trade_date}


def transform(data, mode="default", **kwargs):
    return {"data": data, "mode": mode}


def save(transformed, ctx, **kwargs):
    print(ctx["work_dir"], transformed)
```

Always consider adding `**kwargs` to workflow step functions. Domino passes all
explicit step `kwargs` through unchanged, including keys not declared in the
function signature. A `**kwargs` fallback prevents unrelated config keys from
raising `TypeError` when configs are shared or evolve.

Argument resolution:

1. Start with all explicit step `kwargs`.
2. If a declared parameter is missing and named `ctx`, pass the whole context.
3. If a declared parameter is missing and exists in `ctx`, use `ctx[name]`.
4. Otherwise omit the parameter from the call.

Use Python default parameters for optional inputs.

## Return Values

Domino writes non-`None` return values back into `ctx`.

- `return_key: null`: store the result under the workflow step name.
- `return_key: some_key`: store the result under `ctx["some_key"]`.
- `return_key: [a, b]`: require the result to be a sequence of the same length,
  then store each item under the matching key.
- Return `None` to store nothing.

Example:

```yaml
workflow:
  split:
    callable: "workflow_steps/steps.py:split"
    kwargs: {}
    return_key: [left, right]
```

```python
def split(value, **kwargs):
    return [value[:1], value[1:]]
```

## Verification

Before handing off a target project workflow, run:

```bash
domino --config-path conf/workflow --config-name my_workflow
```

If the target project uses tests, add at least one smoke test that runs the
workflow or calls the step functions with representative `ctx` values.

Common failures:

- `DominoLoadError`: the `callable` module path, module name, or function name is
  wrong, or the target is not callable.
- `DominoConfigError`: workflow config shape or `return_key` handling is invalid.
- `TypeError`: a step function received explicit `kwargs` it does not accept; add
  `**kwargs` or remove the extra config key.
