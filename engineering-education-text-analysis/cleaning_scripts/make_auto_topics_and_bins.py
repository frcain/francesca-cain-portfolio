"""Fit TF-IDF + NMF topics on the combined responses and bin each response.

Runs once on all responses and once per factor. For each run, writes
auto_topics.csv (top words per topic) and responses_with_auto_bins.csv
(each response with its highest-weight topic) under
auto_topics_and_bins_<cohort>/. The cohort defaults to s22.

Usage:
    python3 make_auto_topics_and_bins.py [--cohort s22] [--n-topics 6] [--top-words 15]
"""

import argparse
import sys
from pathlib import Path

import pandas as pd

# Put the repository root on the import path so the shared textanalysis package
# is found when this file is run directly (pip install -e . also works).
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from textanalysis import iter_groups  # noqa: E402
from textanalysis.outputs import save_topic_bins  # noqa: E402

DEFAULT_COHORT = "s22"

N_TOPICS = 6
N_TOP_WORDS = 15

# The tokenizer, stopwords, and TF-IDF + NMF fitting come from the shared
# textanalysis package (the same code driver.py uses).


def run_group(df: pd.DataFrame, name: str, outdir: Path,
              n_topics: int = N_TOPICS, n_top_words: int = N_TOP_WORDS) -> None:
    """Fit topics for one group of responses and save the results to outdir/name."""
    save_topic_bins(df, outdir / name, name, n_topics, n_top_words)
    print(f"✅ {name}: wrote auto_topics.csv + responses_with_auto_bins.csv")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Fit NMF topics overall and per factor.")
    p.add_argument("--cohort", default=DEFAULT_COHORT,
                   help=f"Cohort prefix (default: {DEFAULT_COHORT}).")
    p.add_argument("--combined", type=Path, default=None,
                   help="Combined CSV (default: <cohort>_combined_all_factors.csv).")
    p.add_argument("--outdir", type=Path, default=None,
                   help="Output folder (default: auto_topics_and_bins_<cohort>).")
    p.add_argument("--n-topics", type=int, default=N_TOPICS,
                   help=f"NMF topics per group (default: {N_TOPICS}).")
    p.add_argument("--top-words", type=int, default=N_TOP_WORDS,
                   help=f"Top words saved per topic (default: {N_TOP_WORDS}).")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    combined_csv = args.combined or Path(f"{args.cohort}_combined_all_factors.csv")
    outdir = args.outdir or Path(f"auto_topics_and_bins_{args.cohort}")

    df = pd.read_csv(combined_csv)
    df["response_text"] = df["response_text"].astype(str).str.strip()

    # all responses first, then each factor
    for name, sub in iter_groups(df, args.cohort):
        run_group(sub, name, outdir, args.n_topics, args.top_words)


if __name__ == "__main__":
    main()
