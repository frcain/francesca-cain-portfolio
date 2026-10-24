"""Build a blank manual-coding template from the raw response export.

Reads bme_capstone_responses.csv, assigns each response a stable id, and
writes bme_capstone_coded_template.csv with one 0/1 column per ABET factor
for human coders to fill in.

Usage:
    python3 prepare_coding_template.py [--input bme_capstone_responses.csv]
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

# LABEL_COLS is imported so callers can still use prepare_coding_template.LABEL_COLS.
from textanalysis import LABEL_COLS, add_label_columns  # noqa: E402,F401

RAW_CSV = "bme_capstone_responses.csv"       # export from Google Sheets as CSV
OUT_CSV = "bme_capstone_coded_template.csv"  # human coders fill this in

TEXT_COL = "response_text"

# LABEL_COLS (one 0/1 column per ABET factor) comes from the shared
# textanalysis package, so this template matches the one driver.py writes.


def make_coding_template(df: pd.DataFrame, text_col: str = TEXT_COL) -> pd.DataFrame:
    """Return id, text, and a 0 column for each ABET factor."""
    # make a stable id
    df = df.reset_index(drop=True)
    df["id"] = df.index.astype(int)

    # keep only the id and response text
    out = df[["id", text_col]].copy()

    # initialize labels to 0
    return add_label_columns(out)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build a blank manual-coding template.")
    p.add_argument("--input", default=RAW_CSV, help=f"Raw responses CSV (default: {RAW_CSV}).")
    p.add_argument("--output", default=OUT_CSV, help=f"Template CSV (default: {OUT_CSV}).")
    p.add_argument("--text-col", default=TEXT_COL, help=f"Text column (default: {TEXT_COL}).")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    out = make_coding_template(pd.read_csv(args.input), args.text_col)
    out.to_csv(args.output, index=False)
    print(f"Wrote {args.output} with {len(out)} rows.")


if __name__ == "__main__":
    main()
