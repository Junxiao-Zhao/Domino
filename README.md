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

Step function parameters are resolved from step `kwargs` first, then `ctx`.
All step `kwargs` are passed through to the function; `ctx` only fills missing
signature parameters.
Parameters missing from both step `kwargs` and `ctx` are omitted.
If a step declares a parameter named `ctx`, `domino` passes the whole context unless
the step explicitly sets `kwargs.ctx`.
