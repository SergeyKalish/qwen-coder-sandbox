from temp_converter import c_to_f, f_to_c, c_to_k


def test_c_to_f_freezing():
    """Точка замерзания воды: 0°C = 32°F"""
    assert c_to_f(0) == 32.0, "0°C должен быть 32°F"


def test_c_to_f_boiling():
    """Точка кипения воды: 100°C = 212°F"""
    assert c_to_f(100) == 212.0, "100°C должен быть 212°F"


def test_f_to_c_freezing():
    """Точка замерзания воды: 32°F = 0°C"""
    assert f_to_c(32) == 0.0, "32°F должен быть 0°C"


def test_f_to_c_boiling():
    """Точка кипения воды: 212°F = 100°C"""
    assert f_to_c(212) == 100.0, "212°F должен быть 100°C"


def test_c_to_k_absolute_zero():
    """Абсолютный ноль: -273.15°C = 0K"""
    assert c_to_k(-273.15) == 0.0, "-273.15°C должен быть 0K"


def test_c_to_k_freezing():
    """Точка замерзания воды: 0°C = 273.15K"""
    assert c_to_k(0) == 273.15, "0°C должен быть 273.15K"


def test_c_to_k_boiling():
    """Точка кипения воды: 100°C = 373.15K"""
    assert c_to_k(100) == 373.15, "100°C должен быть 373.15K"


def test_c_to_k_below_absolute_zero():
    """Температура ниже абсолютного нуля должна выбрасывать ValueError"""
    try:
        c_to_k(-274)
        assert False, "Должен быть выброшен ValueError"
    except ValueError:
        pass  # Ожидаемое поведение


if __name__ == "__main__":
    test_c_to_f_freezing()
    test_c_to_f_boiling()
    test_f_to_c_freezing()
    test_f_to_c_boiling()
    test_c_to_k_absolute_zero()
    test_c_to_k_freezing()
    test_c_to_k_boiling()
    test_c_to_k_below_absolute_zero()
    print("Все тесты пройдены!")
