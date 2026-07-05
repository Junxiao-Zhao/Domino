import textwrap
from pathlib import Path

import pytest

from domino.exceptions import DominoLoadError
from domino.loader import load_callable, load_context_callable, resolve_callable


class Client:
    value = "not-callable"

    def fetch(self, suffix=""):
        return f"fetched{suffix}"


def test_load_callable_from_importable_module():
    func = load_callable("math:sqrt")

    assert func(9) == 3


def test_load_callable_from_dotted_importable_target():
    func = load_callable("pathlib:Path.cwd")

    assert func() == Path.cwd()


def test_load_callable_from_python_file_path(tmp_path, monkeypatch):
    module_path = tmp_path / "steps.py"
    module_path.write_text(
        textwrap.dedent(
            """
            def make_value():
                return 42

            class api:
                @staticmethod
                def make_value():
                    return 84
            """
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    func = load_callable("steps.py:make_value")

    assert func() == 42


def test_load_callable_from_dotted_python_file_path(tmp_path, monkeypatch):
    module_path = tmp_path / "steps.py"
    module_path.write_text(
        textwrap.dedent(
            """
            class api:
                @staticmethod
                def make_value():
                    return 42
            """
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    func = load_callable("steps.py:api.make_value")

    assert func() == 42


def test_load_callable_requires_colon():
    with pytest.raises(DominoLoadError, match="module:func"):
        load_callable("math.sqrt")


def test_load_callable_rejects_missing_function():
    with pytest.raises(DominoLoadError, match="missing"):
        load_callable("math:missing")


def test_load_callable_rejects_missing_dotted_function():
    with pytest.raises(DominoLoadError, match="Path.missing"):
        load_callable("pathlib:Path.missing")


def test_load_callable_rejects_empty_dotted_target_segment():
    with pytest.raises(DominoLoadError, match="module:func"):
        load_callable("pathlib:Path..cwd")


def test_load_callable_rejects_non_callable():
    with pytest.raises(DominoLoadError, match="not callable"):
        load_callable("math:pi")


def test_load_context_callable_resolves_ctx_instance_method():
    func = load_context_callable("ctx:client.fetch", {"client": Client()})

    assert func("!") == "fetched!"


def test_resolve_callable_uses_context_callable_path():
    func = resolve_callable("ctx:client.fetch", {"client": Client()})

    assert func("?") == "fetched?"


def test_resolve_callable_preserves_module_loading():
    func = resolve_callable("math:sqrt", {})

    assert func(9) == 3


def test_load_context_callable_rejects_missing_context_key():
    with pytest.raises(DominoLoadError, match="client"):
        load_context_callable("ctx:client.fetch", {})


def test_load_context_callable_rejects_missing_attribute():
    with pytest.raises(DominoLoadError, match="missing"):
        load_context_callable("ctx:client.missing", {"client": Client()})


def test_load_context_callable_rejects_empty_dotted_segment():
    with pytest.raises(DominoLoadError, match="ctx:client..fetch"):
        load_context_callable("ctx:client..fetch", {"client": Client()})


def test_load_context_callable_rejects_non_callable_target():
    with pytest.raises(DominoLoadError, match="not callable"):
        load_context_callable("ctx:client.value", {"client": Client()})
