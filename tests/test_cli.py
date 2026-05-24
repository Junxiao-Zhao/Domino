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
    assert "hello Ada" in completed.stdout
