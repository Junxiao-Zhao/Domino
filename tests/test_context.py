import pytest

from domino.context import build_step_kwargs, store_result
from domino.exceptions import DominoConfigError


def sample(a, b, c, *, d):
    return a, b, c, d


def with_variadic(a, *args, **kwargs):
    return a


def with_ctx(ctx):
    return ctx


def test_build_step_kwargs_prefers_config_kwargs_over_ctx():
    ctx = {"a": "ctx-a", "b": "ctx-b", "d": "ctx-d"}
    kwargs = {"b": "kw-b", "c": "kw-c"}

    assert build_step_kwargs(sample, ctx, kwargs) == {
        "a": "ctx-a",
        "b": "kw-b",
        "c": "kw-c",
        "d": "ctx-d",
    }


def test_build_step_kwargs_uses_none_for_missing_values():
    assert build_step_kwargs(sample, {}, {}) == {
        "a": None,
        "b": None,
        "c": None,
        "d": None,
    }


def test_build_step_kwargs_ignores_variadic_parameters():
    assert build_step_kwargs(with_variadic, {"a": 1, "args": 2}, {"kwargs": 3}) == {
        "a": 1
    }


def test_build_step_kwargs_passes_full_context_for_ctx_parameter():
    ctx = {"a": 1}

    assert build_step_kwargs(with_ctx, ctx, {}) == {"ctx": ctx}


def test_build_step_kwargs_allows_explicit_kwargs_to_override_ctx_parameter():
    ctx = {"a": 1}
    explicit_ctx = {"override": True}

    assert build_step_kwargs(with_ctx, ctx, {"ctx": explicit_ctx}) == {
        "ctx": explicit_ctx
    }


def test_store_result_skips_none():
    ctx = {}

    store_result(ctx, "step", None, None)

    assert ctx == {}


def test_store_result_uses_step_name_when_return_key_missing():
    ctx = {}

    store_result(ctx, "step", 123, None)

    assert ctx == {"step": 123}


def test_store_result_uses_string_return_key():
    ctx = {}

    store_result(ctx, "step", 123, "answer")

    assert ctx == {"answer": 123}


def test_store_result_splits_tuple_across_return_key_list():
    ctx = {}

    store_result(ctx, "step", ("left", "right"), ["a", "b"])

    assert ctx == {"a": "left", "b": "right"}


def test_store_result_rejects_list_key_for_non_tuple_result():
    with pytest.raises(DominoConfigError, match="must return a tuple"):
        store_result({}, "step", ["not", "tuple"], ["a", "b"])


def test_store_result_rejects_list_key_length_mismatch():
    with pytest.raises(DominoConfigError, match="length"):
        store_result({}, "step", ("only",), ["a", "b"])
