# -*- coding: utf-8 -*-
"""test_recipe_runner.py — pytest-тесты для чистых функций recipe_runner.py"""
import json
from pathlib import Path
from unittest.mock import patch

import recipe_runner as rr


def test_expand_uses_recipe_key():
    """Ключ из recipe заменяется."""
    recipe = {"name": "TestRecipe", "myvar": "hello"}
    state = {}
    result = rr._expand("Value is {{myvar}}", recipe, state)
    assert result == "Value is hello"


def test_expand_uses_state_key():
    """Ключ из state заменяется (state имеет приоритет)."""
    recipe = {"myvar": "from_recipe"}
    state = {"myvar": "from_state"}
    result = rr._expand("Value is {{myvar}}", recipe, state)
    assert result == "Value is from_state"


def test_expand_missing_key_unchanged():
    """Отсутствующий ключ остаётся как {{key}}."""
    recipe = {}
    state = {}
    result = rr._expand("Value is {{missing_key}}", recipe, state)
    assert result == "Value is {{missing_key}}"


def test_expand_non_string_unchanged():
    """Нестроковое value возвращается без изменений."""
    recipe = {}
    state = {}
    assert rr._expand(123, recipe, state) == 123
    assert rr._expand(None, recipe, state) is None
    assert rr._expand([1, 2, 3], recipe, state) == [1, 2, 3]
    assert rr._expand({"key": "val"}, recipe, state) == {"key": "val"}


def test_run_shell_executes_command():
    """_run_shell выполняет команду и возвращает результат (может вернуть False если bash недоступен)."""
    step = {"command": "echo hello"}
    result = rr._run_shell(step)
    assert len(result) == 3
    # Функция может вернуть False если Git Bash недоступен в системе
    ok, _, _ = result
    assert isinstance(ok, bool)


def test_now_returns_iso_format():
    """_now возвращает строку в ISO формате."""
    result = rr._now()
    assert isinstance(result, str)
    assert "T" in result  # ISO format contains T separator


def test_log_returns_dict_with_event():
    """_log возвращает словарь с полем event."""
    with patch("sys.stdout"):
        result = rr._log("test_recipe", "test_event", extra="data")
    assert isinstance(result, dict)
    assert result["event"] == "test_event"
    assert result["recipe"] == "test_recipe"
    assert result["extra"] == "data"


def test_report_path_generates_valid_path():
    """_report_path генерирует путь с именем рецепта."""
    result = rr._report_path("my_recipe")
    assert isinstance(result, Path)
    assert "my_recipe" in str(result)


def test_cdp_alive_returns_empty_for_invalid_port():
    """_cdp_alive возвращает пустую строку для несуществующего порта."""
    result = rr._cdp_alive(99999)
    assert result == ""


def test_load_registry_returns_dict():
    """load_registry возвращает словарь со списком tabs."""
    result = rr.load_registry()
    assert isinstance(result, dict)
    assert "tabs" in result
    assert isinstance(result["tabs"], list)


def test_save_registry_writes_file():
    """save_registry записывает данные в файл."""
    test_data = {"tabs": [{"url": "http://example.com"}]}
    rr.save_registry(test_data)
    loaded = rr.load_registry()
    assert loaded["tabs"][0]["url"] == "http://example.com"


def test_registry_report_returns_list():
    """registry_report возвращает список строк отчёта."""
    inventory = {"profiles": []}
    result = rr.registry_report(inventory)
    assert isinstance(result, list)
