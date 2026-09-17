def fib(n):
    """Возвращает n-е число Фибоначчи (0-indexed: fib(0)=0, fib(1)=1, ...)"""
    if n < 0:
        raise ValueError("n должен быть неотрицательным целым числом")
    if n == 0:
        return 0
    if n == 1:
        return 1
    a, b = 0, 1
    for _ in range(2, n + 1):
        a, b = b, a + b
    return b


# Простые тесты
if __name__ == "__main__":
    assert fib(0) == 0, "fib(0) должно быть 0"
    assert fib(1) == 1, "fib(1) должно быть 1"
    assert fib(2) == 1, "fib(2) должно быть 1"
    assert fib(3) == 2, "fib(3) должно быть 2"
    assert fib(4) == 3, "fib(4) должно быть 3"
    assert fib(5) == 5, "fib(5) должно быть 5"
    assert fib(10) == 55, "fib(10) должно быть 55"
    print("Все тесты пройдены!")
