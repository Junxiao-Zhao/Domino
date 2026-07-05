---
name: domino-orchestrator
description: Use when a project should use the domino Python library as a lightweight Hydra-configured serial workflow orchestrator, including creating workflow YAML configs, writing Python step functions, wiring ctx data flow, loading callables with module:target specs, and running workflows with domino or python -m domino.
---

# Domino Orchestrator

Use `domino` when a project needs a simple serial workflow runner configured by
Hydra-compatible YAML. Prefer it for ordered data jobs, scripts, ETL-like
pipelines, research workflows, or project automation where a shared context
dictionary is enough.

Do not use `domino` for DAG scheduling, parallel execution, retries, async
execution, persistent state, or distributed orchestration unless those features
are added explicitly.

## Design Philosophy

Domino is a lightweight serial workflow orchestrator. Its job is to make workflow
structure explicit, readable, and configurable. A good Domino workflow shows the
ordered operational steps in YAML, while Python provides reusable unit behavior.

Core principle:

> Workflow structure belongs in config. Reusable unit behavior belongs in Python.

### Prefer Direct Callables

Use the real callable whenever Domino can load it.

Good:

```yaml
callable: "package.module:function"
callable: "package.client:api.method"
callable: "ctx:client.fetch"
```

Avoid wrapping a callable only to rename it, forward kwargs, adapt a dotted
method, or preserve an old import path.

A wrapper is justified only when it adds real behavior: validation,
transformation, error handling, persistence, or a reusable policy that cannot be
expressed cleanly through kwargs.

### Keep Step Functions Atomic

A Domino step should represent one conceptual operation at the workflow level.

Good examples:

- Fetch source data.
- Build an output path.
- Write raw data.
- Merge records.
- Validate a gap.
- Write a manifest.
- Summarize a result.

Avoid a single Python function that internally performs a whole workflow such as
fetch -> transform -> merge -> validate -> persist.

### Use Kwargs For Variation

If two workflow steps differ only by parameters, keep the same callable and pass
different kwargs.

Common examples include date ranges, entity ids, field lists, provider options,
calendar policies, output labels, and storage partitions.

Do not create separate wrapper functions or config files for differences that
are only arguments.

### Prefer One Config For One Workflow Shape

If two runnable jobs have the same ordered steps and differ only by runtime
values, they should usually share one config.

Use config overrides for runtime differences. Split configs only when workflow
shape, ownership boundary, or operational intent is genuinely different.

### Make Component Workflows Self-Contained

A runnable config should contain the complete `ctx` and complete ordered workflow
needed to run that component.

Avoid generic entrypoints that depend on many overrides or hidden composition
layers when the project has clear components. Generic entrypoints are acceptable
for small one-off projects, but they should not become an indirection layer over
real workflows.

### Keep Policies Reusable, Not Source-Specific

When a workflow needs a reusable policy, model the policy directly.

Good:

```yaml
callable: "quality:warn_if_gap"
kwargs:
  expected_dates: "calendar_provider:expected_dates"
```

Avoid separate policy functions for each data source unless the behavior is
genuinely different. Prefer passing policy inputs or provider callables through
kwargs.

### Be Explicit With Third-Party APIs

Some third-party callables expose generic signatures such as `**kwargs`, so
Domino cannot infer parameters from `ctx`.

In that case, pass required arguments explicitly in YAML. Do not wrap the
third-party API only to create a nicer signature.

### Avoid Compatibility Wrappers By Default

Compatibility wrappers preserve old boundaries and make future refactors harder.

Use them only when maintaining a stable public API is more important than
clarity. In internal or early-stage projects, update configs and imports
directly.

### Test Architecture, Not Only Behavior

If a project has repeatedly drifted toward hidden workflows or wrapper layers,
add regression tests that scan active configs and source files for forbidden
patterns.

Useful architecture tests may guard against:

- Generic workflow entrypoints returning after removal.
- Local callable loaders duplicating Domino.
- Wrapper callables replacing direct callables.
- Split configs that differ only by kwargs.
- Monolithic sync or run functions hiding workflows.

### Decision Checklist

Before adding a Domino step, function, or config, ask:

- Can Domino call the real function directly?
- Is this function hiding multiple workflow steps?
- Is the difference only kwargs?
- Does this config have the same workflow shape as an existing config?
- Is this wrapper adding behavior, or only forwarding?
- Would a future reader understand the workflow from YAML alone?
- Should a regression test prevent this pattern from returning?

If the answers point to direct callable + kwargs + explicit YAML, prefer that
path.

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

- `callable`: required `module:target` or `ctx:object.method` string; normal
  `target` values may be dotted attribute paths.
- `kwargs`: optional explicit keyword arguments.
- `return_key`: optional key, list of keys, or null.

For `module:target`, the `module` part can be an importable Python module or a
`.py` file path. Relative file paths are resolved from the current working
directory. The `target` part can be a single callable attribute or a dotted
attribute path. Domino loads this form with `load_callable`.

For `ctx:object.method`, Domino reads `object` from the current runtime `ctx`,
then resolves the remaining dotted path with attribute access until it reaches a
callable. Domino loads this form with `load_context_callable`. Workflow runners
should use `resolve_callable` so the loader can dispatch between normal
module/file callables and runtime-ctx callables.

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

If an explicit step `kwargs` value is written as `${ctx.some_key}`, Domino
resolves it at the start of that step against the current runtime `ctx`. This is
runtime resolution, so a step can reference values stored into `ctx` by earlier
steps.

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

- `DominoLoadError`: the `callable` module path, module name, target path is
  wrong, or the target is not callable.
- `DominoConfigError`: workflow config shape or `return_key` handling is invalid.
- `TypeError`: a step function received explicit `kwargs` it does not accept; add
  `**kwargs` or remove the extra config key.

Do not commit `docs/plans`. Treat plan files as coordination artifacts outside
the deliverable history.
