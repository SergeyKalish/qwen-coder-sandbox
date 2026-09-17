"""Исполнитель шагов рецепта (упрощённый).

Поддерживает шаги:
  - action: set   (key, value) — записать в state
  - action: shell (command)   — выполнить, stdout -> state[last_output]
  - action: log   (message)   — записать в state[log] (список)
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
    else:
        raise ValueError(f"unknown action {action}")
    return state


def run_recipe(steps, state=None):
    state = state if state is not None else {}
    for step in steps:
        run_step(step, state)
    return state
