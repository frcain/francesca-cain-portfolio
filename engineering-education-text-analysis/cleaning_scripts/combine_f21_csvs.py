"""Combine the per-factor response CSVs into one table with an id column.

Each input file has one response per row and no header. Output is
<cohort>_combined_all_factors.csv with columns id, response_text, factor.

The file name says f21 for historical reasons; the cohort is set with
--cohort and defaults to s22, which is what this script has always read.

Usage:
    python3 combine_f21_csvs.py [--cohort s22] [--folder ../original_responses]
"""

import argparse
import sys
from pathlib import Path

# Put the repository root on the import path so the shared textanalysis package
# is found when this file is run directly (pip install -e . also works).
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from textanalysis import (  # noqa: E402
    CLEANING_CSV_OPTIONS,
    combine_factor_frames,
    factor_files,
    read_one_col_csv,
)

FOLDER = Path("../original_responses")  # folder with the original factor CSVs
DEFAULT_COHORT = "s22"

# The input file names (FILE_SUFFIXES / factor_files), the CSV reader, and
# combine_factor_frames come from the shared textanalysis package. Files are
# one response per row with no header; exact duplicates (same response_text
# and factor) are dropped before ids are added.


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Combine per-factor response CSVs for one cohort.")
    p.add_argument("--cohort", default=DEFAULT_COHORT,
                   help=f"Cohort prefix of the input files (default: {DEFAULT_COHORT}).")
    p.add_argument("--folder", type=Path, default=FOLDER,
                   help=f"Folder with the original factor CSVs (default: {FOLDER}).")
    p.add_argument("--out", default=None,
                   help="Output CSV (default: <cohort>_combined_all_factors.csv).")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    out = args.out or f"{args.cohort}_combined_all_factors.csv"

    frames = {}
    for fname, factor in factor_files(args.cohort).items():
        frames[factor] = read_one_col_csv(args.folder / fname, **CLEANING_CSV_OPTIONS)

    combined = combine_factor_frames(frames)

    combined.to_csv(out, index=False)
    print(f"Wrote {out} with {len(combined)} rows.")


if __name__ == "__main__":
    main()
