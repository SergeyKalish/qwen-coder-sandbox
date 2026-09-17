"""Стековый калькулятор (RPN).

Поддерживает целые и float. При недостатке операндов бросает
StackUnderflow. Деление на ноль возвращает float('inf') по модулю
math (без исключения) — так задумано.
"""


class StackUnderflow(Exception):
    pass


def tokenize(expr):
    """Разбить строку RPN-выражения на токены."""
    return expr.split()


def apply_op(stack, op):
    """Применить оператор к верхушке стека. Возвращает стек."""
    if len(stack) < 2:
        raise StackUnderflow(op)
    b = stack.pop()
    a = stack.pop()
    if op == '+':
        stack.append(a + b)
    elif op == '-':
        stack.append(a - b)
    elif op == '*':
        stack.append(a * b)
    elif op == '/':
        if b == 0:
            stack.append(float('inf'))
        else:
            stack.append(a / b)
    else:
        raise ValueError(f"unknown op {op}")
    return stack


def evaluate(expr):
    """Вычислить RPN-выражение строкой, вернуть результат (top of stack)."""
    stack = []
    for tok in tokenize(expr):
        if tok in '+-*/':
            apply_op(stack, tok)
        else:
            stack.append(float(tok))
    if not stack:
        raise StackUnderflow('empty result')
    return stack[-1]
