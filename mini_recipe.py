"""Исполнитель шагов рецепта (упрощённый).

Поддерживает шаги:
  - action: set   (key, value) — записать в state
  - action: shell (command)   — выполнить, stdout -> state[last_output]
  - action: log   (message)   — записать в state[log] (список)
  - action: repeat (times, step) — выполнить вложенный шаг times раз, {{i}} -> номер итерации
"""
import subprocess


def run_step(step, state):
    action = step.get("action")
    if action == "set":
        state[step["key"]] = step["value"]
    elif action == "shell":
        r = subprocess.run(step["command"], shell=True, capture_output=True,
                           text=True, timeout=60)
        state["last_output"] = r.stdout.strip()
        if r.returncode != 0:
            raise RuntimeError(f"shell exit {r.returncode}: {r.stderr[:100]}")
    elif action == "log":
        state.setdefault("log", []).append(step["message"])
    elif action == "repeat":
        times = step.get("times", 0)
        inner_step = step["step"]
        for i in range(times):
            rendered = _render_step(inner_step, i, state)
            run_step(rendered, state)
    else:
        raise ValueError(f"unknown action {action}")
    return state


def _render_step(step, i, state):
    """Отрендерить значения шага, подставив {{i}} и переменные из state."""
    import re
    rendered = {}
    for k, v in step.items():
        if isinstance(v, str):
            v = re.sub(r"{{i}}", str(i), v)
            v = re.sub(r"{{(\w+)}}", lambda m: str(state.get(m.group(1), m.group(0))), v)
        rendered[k] = v
    return rendered


def run_recipe(steps, state=None):
    state = state if state is not None else {}
    for step in steps:
        run_step(step, state)
    return state
