import textwrap

import pytest

from domino.exceptions import DominoLoadError
from domino.loader import load_callable


def test_load_callable_from_importable_module():
    func = load_callable("math:sqrt")

    assert func(9) == 3


def test_load_callable_from_python_file_path(tmp_path, monkeypatch):
    module_path = tmp_path / "steps.py"
    module_path.write_text(
        textwrap.dedent(
            """
            def make_value():
                return 42
            """
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    func = load_callable("steps.py:make_value")

    assert func() == 42


def test_load_callable_requires_colon():
    with pytest.raises(DominoLoadError, match="module:func"):
        load_callable("math.sqrt")


def test_load_callable_rejects_missing_function():
    with pytest.raises(DominoLoadError, match="missing"):
        load_callable("math:missing")


def test_load_callable_rejects_non_callable():
    with pytest.raises(DominoLoadError, match="not callable"):
        load_callable("math:pi")
