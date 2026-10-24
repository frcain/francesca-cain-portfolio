"""Write a copy of each original factor CSV with its response id attached.

Ids come from <cohort>_combined_all_factors.csv (made by combine_f21_csvs.py),
matched on (factor, response_text). Output files are <name>_with_ids.csv next
to the originals. The cohort defaults to s22.

Usage:
    python3 add_ids_to_factor_csvs.py [--cohort s22] [--folder ../original_responses]
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

from textanalysis import (  # noqa: E402
    CLEANING_CSV_OPTIONS,
    attach_ids,
    factor_files,
    read_one_col_csv,
)

FOLDER = Path("../original_responses")
DEFAULT_COHORT = "s22"

# The input file names (FILE_SUFFIXES / factor_files), the CSV reader, and
# attach_ids come from the shared textanalysis package.


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Attach combined-table ids to each factor CSV.")
    p.add_argument("--cohort", default=DEFAULT_COHORT,
                   help=f"Cohort prefix of the input files (default: {DEFAULT_COHORT}).")
    p.add_argument("--folder", type=Path, default=FOLDER,
                   help=f"Folder with the original factor CSVs (default: {FOLDER}).")
    p.add_argument("--combined", type=Path, default=None,
                   help="Combined CSV with ids (default: <cohort>_combined_all_factors.csv).")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    combined_path = args.combined or Path(f"{args.cohort}_combined_all_factors.csv")

    comb = pd.read_csv(combined_path)
    comb["response_text"] = comb["response_text"].astype(str).str.strip()

    # build lookup: (factor, response_text) -> id
    lookup = comb[["id", "factor", "response_text"]].copy()

    for fname, factor in factor_files(args.cohort).items():
        p = args.folder / fname
        merged = attach_ids(read_one_col_csv(p, **CLEANING_CSV_OPTIONS), factor, lookup)

        missing = merged["id"].isna().sum()
        if missing:
            print(
                f"WARNING {fname}: {missing} rows could not be matched to combined file "
                "(spacing/quotes differences)."
            )

        out_path = args.folder / f"{p.stem}_with_ids.csv"
        merged.to_csv(out_path, index=False)
        print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
