import os
import subprocess
import sys
import textwrap
from pathlib import Path


def test_python_m_domino_runs_hydra_config(tmp_path):
    conf_dir = tmp_path / "conf"
    conf_dir.mkdir()
    (tmp_path / "steps.py").write_text(
        textwrap.dedent(
            """
            def hello(name, **kwargs):
                print(f"hello {name}")
                return name
            """
        ),
        encoding="utf-8",
    )
    (conf_dir / "config.yaml").write_text(
        textwrap.dedent(
            """
            ctx:
              name: Ada
            workflow:
              greet:
                callable: "steps.py:hello"
                kwargs: {}
                return_key: null
            """
        ),
        encoding="utf-8",
    )
    env = {
        **os.environ,
        "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src"),
    }

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "domino",
            "--config-path",
            "conf",
            "--config-name",
            "config",
        ],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert "ctx:" in completed.stdout
    assert "name: Ada" in completed.stdout
    assert "workflow:" in completed.stdout
    assert "hello Ada" in completed.stdout


def test_python_m_domino_prints_unresolved_runtime_ctx_references(tmp_path):
    conf_dir = tmp_path / "conf"
    conf_dir.mkdir()
    (tmp_path / "steps.py").write_text(
        textwrap.dedent(
            """
            def make_name(**kwargs):
                return "Ada"

            def hello(value, **kwargs):
                print(f"hello {value}")
                return value
            """
        ),
        encoding="utf-8",
    )
    (conf_dir / "config.yaml").write_text(
        textwrap.dedent(
            """
            ctx: {}
            workflow:
              make_name:
                callable: "steps.py:make_name"
                kwargs: {}
                return_key: name
              greet:
                callable: "steps.py:hello"
                kwargs:
                  value: ${ctx.name}
                return_key: null
            """
        ),
        encoding="utf-8",
    )
    env = {
        **os.environ,
        "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src"),
    }

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "domino",
            "--config-path",
            "conf",
            "--config-name",
            "config",
        ],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert "${ctx.name}" in completed.stdout
    assert "hello Ada" in completed.stdout
