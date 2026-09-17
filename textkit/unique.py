"""Unique words utilities."""

import re


def _normalize_text(text):
    """Normalize text: lowercase and extract words (alphanumeric sequences)."""
    text = text.lower()
    words = re.findall(r'\b\w+\b', text)
    return words


def unique_words(text):
    """Return a set of unique words (case-insensitive, no punctuation)."""
    words = _normalize_text(text)
    return set(words)
