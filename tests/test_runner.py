import textwrap

import pytest
from omegaconf import OmegaConf

from domino.exceptions import DominoConfigError, DominoExecutionError
from domino.runner import run


def write_steps(tmp_path):
    steps = tmp_path / "steps.py"
    steps.write_text(
        textwrap.dedent(
            """
            def make_base(work_dir, **kwargs):
                return f"{work_dir}/base"

            def split_value(func1, **kwargs):
                return func1, len(func1)

            def consume(value, size, missing=None, **kwargs):
                return {"value": value, "size": size, "missing": missing}

            def fail():
                raise RuntimeError("boom")
            """
        ),
        encoding="utf-8",
    )
    return steps


def test_run_executes_workflow_in_order_and_returns_final_ctx(tmp_path, monkeypatch):
    steps = write_steps(tmp_path)
    monkeypatch.chdir(tmp_path)
    cfg = OmegaConf.create(
        {
            "work_dir": "/tmp/work",
            "ctx": {"work_dir": "/tmp/work"},
            "workflow": {
                "func1": {
                    "callable": f"{steps.name}:make_base",
                    "kwargs": {},
                    "return_key": None,
                },
                "func2": {
                    "callable": f"{steps.name}:split_value",
                    "kwargs": {},
                    "return_key": ["value", "size"],
                },
                "func3": {
                    "callable": f"{steps.name}:consume",
                    "kwargs": {"size": 999},
                    "return_key": "result",
                },
            },
        }
    )

    ctx = run(cfg)

    assert ctx["work_dir"] == "/tmp/work"
    assert ctx["func1"] == "/tmp/work/base"
    assert ctx["value"] == "/tmp/work/base"
    assert ctx["size"] == len("/tmp/work/base")
    assert ctx["result"] == {
        "value": "/tmp/work/base",
        "size": 999,
        "missing": None,
    }


def test_run_requires_workflow_mapping():
    with pytest.raises(DominoConfigError, match="workflow"):
        run(OmegaConf.create({"ctx": {}}))


def test_run_wraps_step_execution_errors(tmp_path, monkeypatch):
    steps = write_steps(tmp_path)
    monkeypatch.chdir(tmp_path)
    cfg = OmegaConf.create(
        {
            "ctx": {},
            "workflow": {
                "bad": {
                    "callable": f"{steps.name}:fail",
                    "kwargs": {},
                    "return_key": None,
                }
            },
        }
    )

    with pytest.raises(DominoExecutionError, match="bad") as exc_info:
        run(cfg)

    assert isinstance(exc_info.value.__cause__, RuntimeError)
