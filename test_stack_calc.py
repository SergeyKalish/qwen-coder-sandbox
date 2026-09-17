"""Тесты для стекового калькулятора stack_calc.py."""

import pytest
from stack_calc import tokenize, apply_op, evaluate, StackUnderflow


class TestTokenize:
    """Тесты для функции tokenize."""

    def test_simple_expression(self):
        """Токенизация простого выражения."""
        assert tokenize("3 4 +") == ["3", "4", "+"]

    def test_empty_string(self):
        """Токенизация пустой строки."""
        assert tokenize("") == []


class TestApplyOp:
    """Тесты для функции apply_op."""

    def test_addition(self):
        """Сложение двух чисел."""
        stack = [3, 5]
        result = apply_op(stack, '+')
        assert result == [8]

    def test_subtraction(self):
        """Вычитание двух чисел."""
        stack = [10, 3]
        result = apply_op(stack, '-')
        assert result == [7]

    def test_multiplication(self):
        """Умножение двух чисел."""
        stack = [4, 5]
        result = apply_op(stack, '*')
        assert result == [20]

    def test_division(self):
        """Деление двух чисел."""
        stack = [10, 2]
        result = apply_op(stack, '/')
        assert result == [5.0]

    def test_division_by_zero(self):
        """Деление на ноль возвращает float('inf')."""
        stack = [10, 0]
        result = apply_op(stack, '/')
        assert result == [float('inf')]

    def test_underflow(self):
        """Недостаточно операндов вызывает StackUnderflow."""
        stack = [5]
        with pytest.raises(StackUnderflow):
            apply_op(stack, '+')

    def test_sequence_of_operations(self):
        """Последовательность операций в одном стеке."""
        stack = [2, 3]
        apply_op(stack, '+')  # [5]
        stack.append(4)       # [5, 4]
        apply_op(stack, '*')  # [20]
        assert stack == [20]


class TestEvaluate:
    """Тесты для функции evaluate."""

    def test_simple_addition(self):
        """Простое сложение: 3 4 +."""
        assert evaluate("3 4 +") == 7.0

    def test_complex_expression(self):
        """Сложное выражение: 5 1 2 + 4 * + 3 -."""
        # 5 ((1 + 2) * 4) + 3 - = 5 + 12 - 3 = 14
        assert evaluate("5 1 2 + 4 * + 3 -") == 14.0

    def test_division_result(self):
        """Деление с нецелым результатом."""
        assert evaluate("5 2 /") == 2.5

    def test_division_by_zero(self):
        """Деление на ноль возвращает inf."""
        assert evaluate("10 0 /") == float('inf')

    def test_underflow_empty_stack(self):
        """Пустое выражение вызывает StackUnderflow."""
        with pytest.raises(StackUnderflow):
            evaluate("")

    def test_underflow_single_operand(self):
        """Один операнд без операции - нормальное поведение."""
        assert evaluate("5") == 5.0

    def test_sequence_of_operations(self):
        """Последовательность операций: 2 3 + 4 *."""
        # (2 + 3) * 4 = 20
        assert evaluate("2 3 + 4 *") == 20.0

    def test_negative_numbers(self):
        """Отрицательные числа."""
        assert evaluate("-5 3 +") == -2.0

    def test_float_numbers(self):
        """Числа с плавающей точкой."""
        assert evaluate("2.5 3.5 +") == 6.0
