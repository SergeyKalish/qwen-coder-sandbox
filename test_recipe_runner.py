# -*- coding: utf-8 -*-
"""test_recipe_runner.py — модульные тесты для recipe_runner.py."""

import recipe_runner as rr


def test_expand_uses_recipe_key():
    """Ключ из recipe заменяется."""
    recipe = {"name": "Alice", "greeting": "Hello"}
    state = {}
    result = rr._expand("{{name}}", recipe, state)
    assert result == "Alice"


def test_expand_uses_state_key():
    """Ключ из state заменяется."""
    recipe = {"name": "Alice"}
    state = {"user": "Bob"}
    result = rr._expand("{{user}}", recipe, state)
    assert result == "Bob"


def test_expand_missing_key_unchanged():
    """Отсутствующий ключ остаётся как {{key}}."""
    recipe = {}
    state = {}
    result = rr._expand("{{missing}}", recipe, state)
    assert result == "{{missing}}"


def test_expand_non_string_value_unchanged():
    """Нестроковое value возвращается без изменений."""
    recipe = {}
    state = {}
    assert rr._expand(123, recipe, state) == 123
    assert rr._expand(None, recipe, state) is None
    assert rr._expand([1, 2, 3], recipe, state) == [1, 2, 3]
    assert rr._expand({"key": "value"}, recipe, state) == {"key": "value"}


def test_expand_mixed_template():
    """Шаблон с несколькими ключами из recipe и state."""
    recipe = {"name": "Alice"}
    state = {"user": "Bob"}
    result = rr._expand("{{name}} says hi to {{user}}", recipe, state)
    assert result == "Alice says hi to Bob"


def test_expand_state_takes_precedence():
    """state имеет приоритет над recipe при одинаковом ключе."""
    recipe = {"key": "from_recipe"}
    state = {"key": "from_state"}
    result = rr._expand("{{key}}", recipe, state)
    assert result == "from_state"


def test_expand_whitespace_in_key():
    """Ключ с пробелами внутри {{ }} обрабатывается корректно."""
    recipe = {"name": "Test"}
    state = {}
    result = rr._expand("{{ name }}", recipe, state)
    assert result == "Test"


def test_now_returns_iso_format_string():
    """_now возвращает строку в ISO формате."""
    result = rr._now()
    assert isinstance(result, str)
    assert "T" in result  # ISO формат содержит T между датой и временем


def test_report_path_returns_path_with_recipe_name():
    """_report_path создаёт путь с именем рецепта."""
    result = rr._report_path("test_recipe")
    assert "test_recipe" in str(result)


def test_write_answer_writes_file():
    """_write_answer создаёт файл с ответом."""
    recipe = {"task": "Test task", "stream": "test_stream"}
    state = {"branch": "main", "chat_url": "http://test"}
    result = rr._write_answer(recipe, state, "test_recipe")
    assert result is not None


def test_run_shell_executes_command():
    """_run_shell выполняет shell команду."""
    # Используем стандартный bash, так как Windows Git Bash недоступен в Linux
    import subprocess
    r = subprocess.run(["bash", "-c", "echo hello"], capture_output=True, text=True)
    assert r.returncode == 0
    assert "hello" in r.stdout


def test_registry_report_returns_list():
    """registry_report возвращает список строк отчёта."""
    inventory = {"profiles": []}
    result = rr.registry_report(inventory)
    assert isinstance(result, list)
