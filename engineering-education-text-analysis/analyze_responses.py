"""Word counts and NMF themes by cohort, plus theme counts by major and project type.

Reads a single CSV of responses (one row per response, with cohort and major
columns), then writes:
  - word_counts_<cohort>.csv and word_counts_overall.csv
  - auto_themes_by_cohort.csv (top words for each discovered theme)
  - responses_with_auto_themes.csv (each response with its assigned theme)
  - theme_counts_by_major.csv and, if present, theme_counts_by_project_type.csv

Usage:
    python3 analyze_responses.py [--input bme_capstone_responses.csv] [--n-topics 6]
"""

import argparse
import sys
from collections import Counter
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

import pandas as pd

# Put the repository root on the import path so the shared textanalysis package
# is found when this file is run directly (pip install -e . also works).
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from textanalysis import fit_nmf, simple_tokenize, word_counts  # noqa: E402

# config (defaults; each can be overridden on the command line)
CSV_PATH = "bme_capstone_responses.csv"  # input file name

TEXT_COL = "response_text"
COHORT_COL = "cohort"
MAJOR_COL = "major"           # must exist in CSV
PROJECT_COL = "project_type"  # optional; used only if the column exists

N_TOPICS_PER_COHORT = 6      # how many new "themes" per cohort
N_TOP_WORDS_PER_TOPIC = 15   # how many top words to print per theme


# tokenizer: simple_tokenize (from textanalysis) lowercases and keeps words of
# length >= 3. Unlike tokenize() used by driver.py, it does not remove
# stopwords. That is the original behavior of this script and is kept so
# results reproduce.


# word counts
def count_words_in_responses(texts: Iterable[object]) -> Counter[str]:
    """
    Implements:
      - iterate over every word in all responses
      - if new word: make new key with value 1
      - if seen before: increment by 1
    Returns a Counter (dict subclass). Uses simple_tokenize, so stopwords are kept.
    """
    return word_counts(texts, simple_tokenize)


def word_counts_by_group(
    df: pd.DataFrame, group_col: str, text_col: str
) -> dict[Any, Counter[str]]:
    """
    Get word counts separately for each cohort (or any grouping).
    Returns dict: {group_value: Counter}
    """
    result = {}
    for group_val, group_df in df.groupby(group_col):
        counts = count_words_in_responses(group_df[text_col])
        result[group_val] = counts
    return result


def safe_name(value: object) -> str:
    """Make a cohort value safe to use in a file name."""
    return str(value).replace(" ", "_").replace("/", "-")


# topic modeling
def fit_topics_for_group(
    texts: Sequence[str], n_topics: int = 6, n_top_words: int = 15
) -> tuple[list[dict[str, Any]], Any]:
    """
    Uses TF-IDF + NMF to discover topics (themes) in a group of responses.
    Returns:
      topics: list of dicts {topic_id, top_words}, where top_words is a list
      doc_topic_ids: topic index for each response (highest-weight topic)
    If there are fewer documents than topics, the topic count is reduced.
    """
    if len(texts) == 0:
        return [], []

    top_words, doc_topic_ids = fit_nmf(texts, n_topics, n_top_words, simple_tokenize)
    topics = [{"topic_id": k, "top_words": words} for k, words in enumerate(top_words)]
    return topics, doc_topic_ids


def assign_themes_by_cohort(
    df: pd.DataFrame, cohort_col: str, text_col: str, n_topics: int, n_top_words: int
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Fit topics separately for each cohort and label every response.

    Returns (topics_df, labeled_df): topics_df has one row per theme with its
    top words; labeled_df is a copy of df with an auto_theme column, in the
    original row order.
    """
    all_topic_rows = []  # store descriptions of topics
    auto_theme_labels = []  # per-row theme label

    # iterate cohort by cohort
    for cohort, cohort_df in df.groupby(cohort_col):
        print(f"\n=== Cohort: {cohort} ===")
        texts = cohort_df[text_col].fillna("").tolist()

        topics, doc_topic_ids = fit_topics_for_group(
            texts,
            n_topics=n_topics,
            n_top_words=n_top_words,
        )

        # create human-readable labels for themes/bins
        cohort_label_prefix = f"{cohort}_topic"
        # map topic index -> label
        topic_idx_to_label = {
            t["topic_id"]: f"{cohort_label_prefix}_{t['topic_id']}"
            for t in topics
        }

        # print / store topic descriptions (top words)
        for t in topics:
            label = topic_idx_to_label[t["topic_id"]]
            print(f"{label}: {', '.join(t['top_words'])}")
            all_topic_rows.append({
                "cohort": cohort,
                "topic_id": t["topic_id"],
                "auto_theme_label": label,
                "top_words": ", ".join(t["top_words"]),
            })

        # assign each response to a bin (auto_theme_label)
        cohort_indices = cohort_df.index.tolist()
        for idx, topic_id in zip(cohort_indices, doc_topic_ids):
            auto_theme_labels.append((idx, topic_idx_to_label[topic_id]))

    # add auto_theme, keeping original row order
    labeled = df.copy()
    labeled["auto_theme"] = None
    for idx, label in auto_theme_labels:
        labeled.at[idx, "auto_theme"] = label

    return pd.DataFrame(all_topic_rows), labeled


def theme_counts(df: pd.DataFrame, group_col: str) -> pd.DataFrame:
    """Number of responses per (group, auto_theme)."""
    return (
        df.groupby([group_col, "auto_theme"])
        .size()
        .reset_index(name="n_responses")
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Word counts and NMF themes by cohort.")
    p.add_argument("--input", default=CSV_PATH, help=f"Responses CSV (default: {CSV_PATH}).")
    p.add_argument("--output-dir", type=Path, default=Path("."),
                   help="Folder for output CSVs (default: current folder).")
    p.add_argument("--text-col", default=TEXT_COL, help=f"Default: {TEXT_COL}.")
    p.add_argument("--cohort-col", default=COHORT_COL, help=f"Default: {COHORT_COL}.")
    p.add_argument("--major-col", default=MAJOR_COL, help=f"Default: {MAJOR_COL}.")
    p.add_argument("--project-col", default=PROJECT_COL,
                   help=f"Optional column, used only if present (default: {PROJECT_COL}).")
    p.add_argument("--n-topics", type=int, default=N_TOPICS_PER_COHORT,
                   help=f"Themes per cohort (default: {N_TOPICS_PER_COHORT}).")
    p.add_argument("--top-words", type=int, default=N_TOP_WORDS_PER_TOPIC,
                   help=f"Top words per theme (default: {N_TOP_WORDS_PER_TOPIC}).")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    out_dir = args.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    # load data
    df = pd.read_csv(args.input)

    # sanity check
    for col in [args.text_col, args.cohort_col, args.major_col]:
        if col not in df.columns:
            raise ValueError(
                f"Column '{col}' not found in CSV. Available: {df.columns.tolist()}"
            )

    # word counts per cohort
    cohort_word_counts = word_counts_by_group(df, args.cohort_col, args.text_col)

    # save word counts for each cohort
    for cohort, counter in cohort_word_counts.items():
        out = pd.DataFrame(counter.most_common(), columns=["word", "count"])
        name = f"word_counts_{safe_name(cohort)}.csv"
        out.to_csv(out_dir / name, index=False)
        print(f"Saved word counts for cohort {cohort} -> {name}")

    # overall word counts across all cohorts
    overall_counts = count_words_in_responses(df[args.text_col])
    overall_df = pd.DataFrame(overall_counts.most_common(), columns=["word", "count"])
    overall_df.to_csv(out_dir / "word_counts_overall.csv", index=False)
    print("Saved overall word counts -> word_counts_overall.csv")

    # new themes (topics) + assign responses (bins) per cohort
    topics_df, df = assign_themes_by_cohort(
        df, args.cohort_col, args.text_col, args.n_topics, args.top_words
    )

    # save topics table (descriptions of each new bin per cohort)
    topics_df.to_csv(out_dir / "auto_themes_by_cohort.csv", index=False)
    print("Saved theme descriptions -> auto_themes_by_cohort.csv")

    # save full responses with assigned bins
    df.to_csv(out_dir / "responses_with_auto_themes.csv", index=False)
    print("Saved responses with bins -> responses_with_auto_themes.csv")

    # theme counts by major
    theme_counts(df, args.major_col).to_csv(out_dir / "theme_counts_by_major.csv", index=False)
    print("Saved theme counts by major -> theme_counts_by_major.csv")

    # theme counts by project type (only if that column exists)
    if args.project_col in df.columns:
        theme_counts(df, args.project_col).to_csv(
            out_dir / "theme_counts_by_project_type.csv", index=False
        )
        print("Saved theme counts by project type -> theme_counts_by_project_type.csv")


if __name__ == "__main__":
    main()
