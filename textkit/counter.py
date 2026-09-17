"""Word counting utilities."""

import re
from collections import Counter


def _normalize_text(text):
    """Normalize text: lowercase and extract words (alphanumeric sequences)."""
    text = text.lower()
    words = re.findall(r'\b\w+\b', text)
    return words


def word_count(text):
    """Return the number of words in the text."""
    words = _normalize_text(text)
    return len(words)


def most_common_words(text, n=3):
    """Return the top n most common words (case-insensitive, no punctuation)."""
    words = _normalize_text(text)
    counter = Counter(words)
    return counter.most_common(n)
