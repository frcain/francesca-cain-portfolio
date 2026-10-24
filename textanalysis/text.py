"""Tokenizers, the stopword list, and word counts."""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Callable, Iterable

# A tokenizer turns one response into a list of words.
Tokenizer = Callable[[object], list[str]]

STOPWORDS = {
    "the", "and", "for", "that", "with", "this", "was", "were", "are", "our", "their",
    "they", "them", "from", "have", "has", "had", "not", "but", "can", "could", "would",
    "should", "into", "also", "about", "more", "most", "less", "very", "much", "many",
    "some", "any", "each", "been", "being", "because", "between", "during", "through",
    "within", "will", "may", "might", "than", "then", "when", "where", "while", "what",
    "who", "why", "how", "your", "you", "we", "us", "it", "its", "in", "on", "at", "to",
    "of", "as", "an", "a", "is", "be", "by", "or", "if",
}

WORD_RE = re.compile(r"[a-z']+")  # words with letters and apostrophes


def simple_tokenize(text: object) -> list[str]:
    """Lowercase and keep words of length >= 3. Stopwords are kept.

    Non-strings are converted with str() first (so NaN becomes "nan").
    analyze_responses.py uses this tokenizer, as in the original analysis.
    """
    if not isinstance(text, str):
        text = str(text)
    return [t for t in WORD_RE.findall(text.lower()) if len(t) >= 3]


def tokenize(text: object) -> list[str]:
    """Like simple_tokenize, but also drops words in STOPWORDS."""
    return [t for t in simple_tokenize(text) if t not in STOPWORDS]


def word_counts(texts: Iterable[object], tokenizer: Tokenizer = tokenize) -> Counter[str]:
    """Count tokens across all texts."""
    c: Counter[str] = Counter()
    for t in texts:
        for w in tokenizer(t):
            c[w] += 1
    return c
