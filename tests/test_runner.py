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

            class Client:
                def fetch(self, value, **kwargs):
                    return f"client:{value}"

            def make_client(**kwargs):
                return Client()

            def make_name(**kwargs):
                return "Ada"

            def make_other_name(**kwargs):
                return "Bob"

            def make_literal(**kwargs):
                return "${literal}"

            def make_pair(**kwargs):
                return ("left", "right")

            def echo(value, **kwargs):
                return value

            def fail():
                raise RuntimeError("boom")
            """
        ),
        encoding="utf-8",
    )
    return steps


def test_run_executes_workflow_in_order_and_returns_final_ctx(
    tmp_path, monkeypatch, capsys
):
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
    assert capsys.readouterr().out.splitlines() == [
        "Start running step func1...",
        "Finish step func1.",
        "Start running step func2...",
        "Finish step func2.",
        "Start running step func3...",
        "Finish step func3.",
    ]


def test_run_requires_workflow_mapping():
    with pytest.raises(DominoConfigError, match="workflow"):
        run(OmegaConf.create({"ctx": {}}))


def test_run_resolves_step_kwargs_with_runtime_ctx(tmp_path, monkeypatch):
    steps = write_steps(tmp_path)
    monkeypatch.chdir(tmp_path)
    cfg = OmegaConf.create(
        {
            "ctx": {},
            "workflow": {
                "make_name": {
                    "callable": f"{steps.name}:make_name",
                    "kwargs": {},
                    "return_key": "name",
                },
                "consume": {
                    "callable": f"{steps.name}:consume",
                    "kwargs": {"value": "${ctx.name}", "size": 3},
                    "return_key": "result",
                },
            },
        }
    )

    ctx = run(cfg)

    assert ctx["result"]["value"] == "Ada"
    assert ctx["result"]["size"] == 3


def test_run_resolves_indirect_step_kwargs_with_runtime_ctx(tmp_path, monkeypatch):
    steps = write_steps(tmp_path)
    monkeypatch.chdir(tmp_path)
    cfg = OmegaConf.create(
        {
            "ctx": {},
            "name_ref": "${ctx.name}",
            "workflow": {
                "make_name": {
                    "callable": f"{steps.name}:make_name",
                    "kwargs": {},
                    "return_key": "name",
                },
                "consume": {
                    "callable": f"{steps.name}:consume",
                    "kwargs": {"value": "${name_ref}", "size": 3},
                    "return_key": "result",
                },
            },
        }
    )

    ctx = run(cfg)

    assert ctx["result"]["value"] == "Ada"
    assert ctx["result"]["size"] == 3


def test_run_reuses_indirect_ctx_reference_with_latest_runtime_ctx(
    tmp_path, monkeypatch
):
    steps = write_steps(tmp_path)
    monkeypatch.chdir(tmp_path)
    cfg = OmegaConf.create(
        {
            "ctx": {},
            "name_ref": "${ctx.name}",
            "workflow": {
                "make_name": {
                    "callable": f"{steps.name}:make_name",
                    "kwargs": {},
                    "return_key": "name",
                },
                "first": {
                    "callable": f"{steps.name}:consume",
                    "kwargs": {"value": "${name_ref}", "size": 3},
                    "return_key": "first_result",
                },
                "make_other_name": {
                    "callable": f"{steps.name}:make_other_name",
                    "kwargs": {},
                    "return_key": "name",
                },
                "second": {
                    "callable": f"{steps.name}:consume",
                    "kwargs": {"value": "${name_ref}", "size": 3},
                    "return_key": "second_result",
                },
            },
        }
    )

    ctx = run(cfg)

    assert ctx["first_result"]["value"] == "Ada"
    assert ctx["second_result"]["value"] == "Bob"


def test_run_calls_method_from_runtime_ctx(tmp_path, monkeypatch):
    steps = write_steps(tmp_path)
    monkeypatch.chdir(tmp_path)
    cfg = OmegaConf.create(
        {
            "ctx": {},
            "workflow": {
                "client": {
                    "callable": f"{steps.name}:make_client",
                    "kwargs": {},
                    "return_key": "client",
                },
                "name": {
                    "callable": f"{steps.name}:make_name",
                    "kwargs": {},
                    "return_key": "name",
                },
                "fetch": {
                    "callable": "ctx:client.fetch",
                    "kwargs": {"value": "${ctx.name}"},
                    "return_key": "fetched",
                },
            },
        }
    )

    ctx = run(cfg)

    assert ctx["fetched"] == "client:Ada"


def test_run_keeps_runtime_ctx_string_values_opaque(tmp_path, monkeypatch):
    steps = write_steps(tmp_path)
    monkeypatch.chdir(tmp_path)
    cfg = OmegaConf.create(
        {
            "ctx": {},
            "workflow": {
                "make_literal": {
                    "callable": f"{steps.name}:make_literal",
                    "kwargs": {},
                    "return_key": "token",
                },
                "echo": {
                    "callable": f"{steps.name}:echo",
                    "kwargs": {"value": "${ctx.token}"},
                    "return_key": "echoed",
                },
            },
        }
    )

    ctx = run(cfg)

    assert ctx["token"] == "${literal}"
    assert ctx["echoed"] == "${literal}"


def test_run_keeps_runtime_ctx_tuple_values_opaque(tmp_path, monkeypatch):
    steps = write_steps(tmp_path)
    monkeypatch.chdir(tmp_path)
    cfg = OmegaConf.create(
        {
            "ctx": {},
            "workflow": {
                "make_pair": {
                    "callable": f"{steps.name}:make_pair",
                    "kwargs": {},
                    "return_key": "pair",
                },
                "echo": {
                    "callable": f"{steps.name}:echo",
                    "kwargs": {"value": "${ctx.pair}"},
                    "return_key": "echoed",
                },
            },
        }
    )

    ctx = run(cfg)

    assert ctx["pair"] == ("left", "right")
    assert ctx["echoed"] == ("left", "right")
    assert isinstance(ctx["echoed"], tuple)


def test_run_preserves_escaped_ctx_interpolation_literals(tmp_path, monkeypatch):
    steps = write_steps(tmp_path)
    monkeypatch.chdir(tmp_path)
    cfg = OmegaConf.create(
        {
            "ctx": {},
            "workflow": {
                "echo": {
                    "callable": f"{steps.name}:echo",
                    "kwargs": {"value": r"\${ctx.name}"},
                    "return_key": "echoed",
                },
            },
        }
    )

    ctx = run(cfg)

    assert ctx["echoed"] == "${ctx.name}"


def test_run_preserves_escaped_indirect_ctx_interpolation_literals(
    tmp_path, monkeypatch
):
    steps = write_steps(tmp_path)
    monkeypatch.chdir(tmp_path)
    cfg = OmegaConf.create(
        {
            "ctx": {},
            "name_ref": r"\${ctx.name}",
            "workflow": {
                "echo": {
                    "callable": f"{steps.name}:echo",
                    "kwargs": {"value": "${name_ref}"},
                    "return_key": "echoed",
                },
            },
        }
    )

    ctx = run(cfg)

    assert ctx["echoed"] == "${ctx.name}"


def test_run_passes_runtime_ctx_object_values_through_kwargs(tmp_path, monkeypatch):
    steps = write_steps(tmp_path)
    monkeypatch.chdir(tmp_path)
    cfg = OmegaConf.create(
        {
            "ctx": {},
            "workflow": {
                "client": {
                    "callable": f"{steps.name}:make_client",
                    "kwargs": {},
                    "return_key": "client",
                },
                "echo": {
                    "callable": f"{steps.name}:echo",
                    "kwargs": {"value": "${ctx.client}"},
                    "return_key": "echoed",
                },
            },
        }
    )

    ctx = run(cfg)

    assert ctx["echoed"] is ctx["client"]


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
