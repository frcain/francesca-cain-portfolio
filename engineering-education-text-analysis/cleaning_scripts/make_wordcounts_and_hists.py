"""Save word counts and top-word histograms for the combined responses.

Runs once on all responses and once per factor, writing word_counts.csv and
top_words_hist.png for each under wordcounts_and_hists_<cohort>/. The cohort
defaults to s22.

Usage:
    python3 make_wordcounts_and_hists.py [--cohort s22] [--top-n 30]
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
from textanalysis.outputs import save_word_counts  # noqa: E402

# -------- config (defaults; each can be overridden on the command line) --------
DEFAULT_COHORT = "s22"
TOP_N = 30  # histogram top words

# The tokenizer, stopwords, word counts, and histogram code come from the
# shared textanalysis package (the same code driver.py uses).


def run_group(df: pd.DataFrame, name: str, outdir: Path, top_n: int = TOP_N) -> None:
    """Save word counts and a histogram for one group of responses."""
    run_dir = outdir / name
    save_word_counts(df, run_dir, name, top_n)
    print(f"✅ {name}: {len(df)} rows -> {run_dir}")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Word counts and histograms overall and per factor.")
    p.add_argument("--cohort", default=DEFAULT_COHORT,
                   help=f"Cohort prefix (default: {DEFAULT_COHORT}).")
    p.add_argument("--combined", type=Path, default=None,
                   help="Combined CSV (default: <cohort>_combined_all_factors.csv).")
    p.add_argument("--outdir", type=Path, default=None,
                   help="Output folder (default: wordcounts_and_hists_<cohort>).")
    p.add_argument("--top-n", type=int, default=TOP_N,
                   help=f"Words shown in each histogram (default: {TOP_N}).")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    combined_csv = args.combined or Path(f"{args.cohort}_combined_all_factors.csv")
    outdir = args.outdir or Path(f"wordcounts_and_hists_{args.cohort}")
    outdir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(combined_csv)
    if "response_text" not in df.columns or "factor" not in df.columns:
        raise ValueError(
            "Combined CSV must have columns response_text and factor. "
            f"Found: {df.columns.tolist()}"
        )

    df["response_text"] = df["response_text"].astype(str).str.strip()

    # 1) overall, then 2) each factor
    for name, sub in iter_groups(df, args.cohort):
        run_group(sub, name, outdir, args.top_n)


if __name__ == "__main__":
    main()
