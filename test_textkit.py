"""Tests for textkit package."""

from textkit import word_count, most_common_words, unique_words


def test_word_count_empty():
    """Test word_count with empty string."""
    assert word_count("") == 0, "Empty string should have 0 words"


def test_word_count_single():
    """Test word_count with single word."""
    assert word_count("hello") == 1, "Single word should return 1"


def test_word_count_multiple():
    """Test word_count with multiple words."""
    assert word_count("hello world foo bar") == 4, "Should count 4 words"


def test_word_count_with_punctuation():
    """Test word_count ignores punctuation."""
    assert word_count("Hello, world! How are you?") == 5, "Punctuation should be ignored"


def test_word_count_repeats():
    """Test word_count counts repeated words."""
    assert word_count("hello hello hello") == 3, "Repeated words should be counted"


def test_most_common_empty():
    """Test most_common_words with empty string."""
    assert most_common_words("") == [], "Empty string should return empty list"


def test_most_common_case_insensitive():
    """Test most_common_words is case-insensitive."""
    result = most_common_words("Hello HELLO hello World", n=2)
    assert result[0] == ("hello", 3), "Should be case-insensitive"


def test_most_common_with_punctuation():
    """Test most_common_words ignores punctuation."""
    result = most_common_words("Hello, hello! Hello?", n=1)
    assert result[0] == ("hello", 3), "Punctuation should be ignored"


def test_unique_empty():
    """Test unique_words with empty string."""
    assert unique_words("") == set(), "Empty string should return empty set"


def test_unique_case_insensitive():
    """Test unique_words is case-insensitive."""
    result = unique_words("Hello hello HELLO")
    assert result == {"hello"}, "Should be case-insensitive"


def test_unique_with_punctuation():
    """Test unique_words ignores punctuation."""
    result = unique_words("Hello, world! Hello.")
    assert result == {"hello", "world"}, "Punctuation should be ignored"


def test_unique_repeats():
    """Test unique_words with repeated words."""
    result = unique_words("cat dog cat bird dog")
    assert result == {"cat", "dog", "bird"}, "Should return unique words only"


if __name__ == "__main__":
    # Run all tests
    test_word_count_empty()
    print("✓ test_word_count_empty passed")
    
    test_word_count_single()
    print("✓ test_word_count_single passed")
    
    test_word_count_multiple()
    print("✓ test_word_count_multiple passed")
    
    test_word_count_with_punctuation()
    print("✓ test_word_count_with_punctuation passed")
    
    test_word_count_repeats()
    print("✓ test_word_count_repeats passed")
    
    test_most_common_empty()
    print("✓ test_most_common_empty passed")
    
    test_most_common_case_insensitive()
    print("✓ test_most_common_case_insensitive passed")
    
    test_most_common_with_punctuation()
    print("✓ test_most_common_with_punctuation passed")
    
    test_unique_empty()
    print("✓ test_unique_empty passed")
    
    test_unique_case_insensitive()
    print("✓ test_unique_case_insensitive passed")
    
    test_unique_with_punctuation()
    print("✓ test_unique_with_punctuation passed")
    
    test_unique_repeats()
    print("✓ test_unique_repeats passed")
    
    print("\n✅ All 13 tests passed!")
