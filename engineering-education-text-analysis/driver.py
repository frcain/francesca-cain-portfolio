"""Run the full factor pipeline for every cohort found in the working directory.

For each cohort prefix (e.g. f21 or s22) with per-factor CSVs such as
f21_public_health.csv, this script:
  1. combines the factor files into one table with response ids,
  2. writes each source file back out with its ids,
  3. saves word counts and top-word histograms (overall and per factor),
  4. fits TF-IDF + NMF topics and assigns each response to a topic,
  5. writes a blank manual-coding template.
It then concatenates all cohorts into all_years_combined_all_factors.csv.

The text helpers (tokenize, cohort detection, combining, word counts, topic
fitting) come from the shared textanalysis package at the repository root.
This file keeps the cohort-level steps and the code that reads and writes
files, so the logic can be tested without real data.

Usage (from the folder containing the CSVs):
    python3 driver.py [--base-dir .] [--n-topics 6] [--top-words 15] [--hist-top-n 30]
"""

import argparse
import sys
from pathlib import Path

import pandas as pd

# Put the repository root on the import path so the shared textanalysis package
# is found when this file is run directly (pip install -e . also works).
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from textanalysis import (  # noqa: E402
    add_label_columns,
    attach_ids,
    cohorts_from_filenames,
    combine_factor_frames,
    iter_groups,
    read_one_col_csv,
)
from textanalysis.outputs import save_topic_bins, save_word_counts  # noqa: E402

# =========================
# CONFIG (defaults; each can be overridden on the command line)
# =========================
BASE_DIR = Path(".")
TOP_N_WORDS_HIST = 30
N_TOPICS = 6
N_TOP_WORDS = 15

FACTOR_FILE_PATTERNS = {
    "public_health": [
        "{year}_public_health.csv",
        "{year}_public_health_factors.csv",
    ],
    "public_safety": [
        "{year}_public_safety.csv",
        "{year}_public_safety_factors.csv",
    ],
    "public_welfare": [
        "{year}_public_welfare.csv",
        "{year}_public_welfare_factors.csv",
    ],
    "global": [
        "{year}_global.csv",
        "{year}_global_factors.csv",
    ],
    "cultural": [
        "{year}_cultural.csv",
        "{year}_cultural_factors.csv",
    ],
    "social": [
        "{year}_social.csv",
        "{year}_social_factors.csv",
    ],
    "environmental": [
        "{year}_environmental.csv",
        "{year}_environmental_factors.csv",
    ],
    "economic": [
        "{year}_economic.csv",
        "{year}_economic_factors.csv",
    ],
}

# Tokenizing, stopwords, cohort detection, combining, word counts, and topic
# fitting live in the shared textanalysis package (repository root).


# =========================
# PURE HELPERS (no file I/O)
# =========================
def make_coding_template(df: pd.DataFrame) -> pd.DataFrame:
    """Manual-coding template: id, year, factor, text, plus a 0 column per ABET factor."""
    out = df[["id", "year", "factor", "response_text"]].copy()
    return add_label_columns(out)


def combine_all_cohorts(parts: list[pd.DataFrame]) -> pd.DataFrame:
    """Concatenate cohort tables and put a running global_id first."""
    all_years = pd.concat(parts, ignore_index=True).reset_index(drop=True)
    all_years["global_id"] = range(len(all_years))
    cols = ["global_id"] + [c for c in all_years.columns if c != "global_id"]
    return all_years[cols]


# =========================
# FILE I/O
# =========================
# Responses are read with the shared read_one_col_csv using pandas' python
# engine, as this script always has.
def find_existing_file(base_dir: Path, year: str, patterns: list[str]) -> Path | None:
    """Return the first file matching one of the name patterns, or None."""
    for pattern in patterns:
        p = base_dir / pattern.format(year=year)
        if p.exists():
            return p
    return None


def detect_years(base_dir: Path) -> list[str]:
    """Find cohort prefixes like "f21" or "s22" from CSV file names in base_dir."""
    return cohorts_from_filenames(p.name for p in base_dir.glob("*.csv"))


def factor_files_for_year(base_dir: Path, year: str) -> dict[str, Path]:
    """Map each factor to its CSV for this cohort (factors without a file are skipped)."""
    found = {}
    for factor, patterns in FACTOR_FILE_PATTERNS.items():
        p = find_existing_file(base_dir, year, patterns)
        if p is not None:
            found[factor] = p
    return found


def combine_one_year(base_dir: Path, year: str) -> pd.DataFrame:
    """Read all factor CSVs for a cohort and combine them (see combine_factor_frames)."""
    files = factor_files_for_year(base_dir, year)
    if not files:
        raise ValueError(f"No factor CSVs found for {year}")

    frames = {factor: read_one_col_csv(path, engine="python") for factor, path in files.items()}
    return combine_factor_frames(frames, year)


def add_ids_back_to_source_files(base_dir: Path, year: str, combined_df: pd.DataFrame) -> None:
    """Write <source>_with_ids.csv for each factor file using ids from the combined table."""
    files = factor_files_for_year(base_dir, year)

    for factor, path in files.items():
        out = attach_ids(read_one_col_csv(path, engine="python"), factor, combined_df)
        out_path = base_dir / f"{path.stem}_with_ids.csv"
        out.to_csv(out_path, index=False)
        print(f"  wrote {out_path.name}")


def run_wordcounts_and_hists(
    df: pd.DataFrame, outdir: Path, year_label: str, top_n: int = TOP_N_WORDS_HIST
) -> None:
    """Save word counts and histograms for the whole cohort and for each factor."""
    outdir.mkdir(parents=True, exist_ok=True)

    for name, sub in iter_groups(df, year_label):
        save_word_counts(sub, outdir / name, name, top_n)


def run_auto_topics_and_bins(
    df: pd.DataFrame,
    outdir: Path,
    year_label: str,
    n_topics: int = N_TOPICS,
    n_top_words: int = N_TOP_WORDS,
) -> None:
    """Fit topics and save per-response topic bins, overall and per factor."""
    outdir.mkdir(parents=True, exist_ok=True)

    for name, sub in iter_groups(df, year_label):
        save_topic_bins(sub, outdir / name, name, n_topics, n_top_words)


def run_one_year(base_dir: Path, year: str, args: argparse.Namespace) -> pd.DataFrame:
    """Run every pipeline step for one cohort and return its combined table."""
    print(f"\n=== {year} ===")

    combined = combine_one_year(base_dir, year)

    combined_csv = base_dir / f"{year}_combined_all_factors.csv"
    combined.to_csv(combined_csv, index=False)
    print(f"wrote {combined_csv.name}")

    add_ids_back_to_source_files(base_dir, year, combined)

    wc_dir = base_dir / f"wordcounts_and_hists_{year}"
    run_wordcounts_and_hists(combined, wc_dir, year, args.hist_top_n)

    topic_dir = base_dir / f"auto_topics_and_bins_{year}"
    run_auto_topics_and_bins(combined, topic_dir, year, args.n_topics, args.top_words)

    coding_csv = base_dir / f"{year}_coded_template.csv"
    make_coding_template(combined).to_csv(coding_csv, index=False)
    print(f"wrote {coding_csv.name}")

    return combined


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run the factor pipeline for every cohort.")
    p.add_argument("--base-dir", type=Path, default=BASE_DIR,
                   help="Folder with the <cohort>_<factor>.csv files; outputs go here too "
                        "(default: current folder).")
    p.add_argument("--n-topics", type=int, default=N_TOPICS,
                   help=f"NMF topics per group (default: {N_TOPICS}).")
    p.add_argument("--top-words", type=int, default=N_TOP_WORDS,
                   help=f"Top words saved per topic (default: {N_TOP_WORDS}).")
    p.add_argument("--hist-top-n", type=int, default=TOP_N_WORDS_HIST,
                   help=f"Words shown in each histogram (default: {TOP_N_WORDS_HIST}).")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    base_dir = args.base_dir

    years = detect_years(base_dir)
    if not years:
        raise RuntimeError(
            "No year-prefixed CSVs found, e.g. f21_public_health.csv or f22_cultural_factors.csv"
        )

    all_parts = []
    for year in years:
        try:
            combined = run_one_year(base_dir, year, args)
            all_parts.append(combined)
        except Exception as e:
            print(f"skipping {year}: {e}")

    if not all_parts:
        raise RuntimeError("No years were processed successfully.")

    all_years = combine_all_cohorts(all_parts)

    out_all = base_dir / "all_years_combined_all_factors.csv"
    all_years.to_csv(out_all, index=False)
    print(f"\nwrote {out_all.name} with {len(all_years)} rows")


if __name__ == "__main__":
    main()
