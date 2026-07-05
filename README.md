# domino

`domino` is a lightweight Hydra-based serial workflow orchestration library.

## Install

```bash
pip install .
```

## Run

```bash
domino --config-path examples/conf --config-name config
python -m domino --config-path examples/conf --config-name config
```

## Config

```yaml
work_dir: ""

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

Callable specs support two forms:

- `module:target`: load an importable module or `.py` file path with
  `load_callable`; the `target` side can be a callable attribute name or a
  dotted attribute path such as `client:pro.trade_cal`.
- `ctx:object.method`: resolve `object` from the runtime `ctx`, then follow the
  dotted attribute path to a callable with `load_context_callable`.

Workflow execution should call `resolve_callable`, which dispatches to the
normal module/file loader or the runtime-ctx loader based on the spec.

Step function parameters are resolved from step `kwargs` first, then `ctx`.
All step `kwargs` are passed through to the function; `ctx` only fills missing
signature parameters.
Parameters missing from both step `kwargs` and `ctx` are omitted.
If a step declares a parameter named `ctx`, `domino` passes the whole context unless
the step explicitly sets `kwargs.ctx`.

Step `kwargs` values written as `${ctx.some_key}` are resolved at the start of
each step against the current runtime `ctx`, so later steps can reference values
stored by earlier steps.
