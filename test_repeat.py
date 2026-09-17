"""Тесты для шага repeat."""
import pytest
from mini_recipe import run_step, run_recipe


def test_repeat_basic():
    """repeat выполняет вложенный шаг times раз."""
    state = {}
    step = {
        "action": "repeat",
        "times": 3,
        "step": {
            "action": "set",
            "key": "counter",
            "value": "x"
        }
    }
    run_step(step, state)
    assert state["counter"] == "x"


def test_repeat_i_substitution():
    """{{i}} подставляется как номер итерации (0-based)."""
    state = {}
    step = {
        "action": "repeat",
        "times": 3,
        "step": {
            "action": "log",
            "message": "iteration {{i}}"
        }
    }
    run_step(step, state)
    assert state["log"] == ["iteration 0", "iteration 1", "iteration 2"]


def test_repeat_times_zero():
    """times=0 → ни одного исполнения."""
    state = {"existing": "value"}
    step = {
        "action": "repeat",
        "times": 0,
        "step": {
            "action": "set",
            "key": "should_not_exist",
            "value": "bad"
        }
    }
    run_step(step, state)
    assert "should_not_exist" not in state
    assert state["existing"] == "value"


def test_repeat_set_with_i():
    """repeat с set и использованием {{i}} в значении."""
    state = {}
    step = {
        "action": "repeat",
        "times": 4,
        "step": {
            "action": "set",
            "key": "idx",
            "value": "{{i}}"
        }
    }
    run_step(step, state)
    # Последнее значение будет 3
    assert state["idx"] == "3"


def test_repeat_accumulate():
    """repeat может накапливать значения через log."""
    state = {}
    step = {
        "action": "repeat",
        "times": 5,
        "step": {
            "action": "log",
            "message": "{{i}}"
        }
    }
    run_step(step, state)
    assert state["log"] == ["0", "1", "2", "3", "4"]


def test_run_recipe_with_repeat():
    """repeat работает внутри run_recipe."""
    steps = [
        {
            "action": "repeat",
            "times": 2,
            "step": {
                "action": "log",
                "message": "loop {{i}}"
            }
        },
        {
            "action": "set",
            "key": "done",
            "value": "yes"
        }
    ]
    state = run_recipe(steps)
    assert state["log"] == ["loop 0", "loop 1"]
    assert state["done"] == "yes"
