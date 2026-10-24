"""Write word counts, histograms, and topic bins for a group of responses.

matplotlib is imported inside save_hist, so importing this module does not
need a display.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import pandas as pd

from textanalysis.text import word_counts
from textanalysis.topics import fit_topics, topic_bin_labels


def save_hist(counter: Counter[str], out_png: Path, title: str, top_n: int = 30) -> None:
    """Save a bar chart of the top_n most common words (nothing is saved if empty)."""
    import matplotlib.pyplot as plt

    items = counter.most_common(top_n)
    if not items:
        return

    words, counts = zip(*items)
    plt.figure(figsize=(12, 6))
    plt.bar(words, counts)
    plt.xticks(rotation=60, ha="right")
    plt.title(title)
    plt.tight_layout()
    plt.savefig(out_png, dpi=200)
    plt.close()


def save_word_counts(df: pd.DataFrame, run_dir: Path, name: str, top_n: int = 30) -> None:
    """Write run_dir/word_counts.csv and run_dir/top_words_hist.png for one group."""
    run_dir.mkdir(parents=True, exist_ok=True)

    texts = df["response_text"].fillna("").astype(str).tolist()
    c = word_counts(texts)

    pd.DataFrame(c.most_common(), columns=["word", "count"]).to_csv(
        run_dir / "word_counts.csv", index=False
    )
    save_hist(c, run_dir / "top_words_hist.png", f"{name}: Top {top_n} words", top_n)


def save_topic_bins(
    df: pd.DataFrame, run_dir: Path, name: str, n_topics: int = 6, n_top_words: int = 15
) -> None:
    """Write run_dir/auto_topics.csv and run_dir/responses_with_auto_bins.csv for one group."""
    run_dir.mkdir(parents=True, exist_ok=True)

    texts = df["response_text"].fillna("").astype(str).tolist()
    topics, doc_topic = fit_topics(texts, n_topics, n_top_words)

    pd.DataFrame(topics).to_csv(run_dir / "auto_topics.csv", index=False)

    out = df.copy()
    out["auto_bin"] = topic_bin_labels(name, doc_topic)
    out.to_csv(run_dir / "responses_with_auto_bins.csv", index=False)
