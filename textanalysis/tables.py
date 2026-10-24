"""Reading, combining, and labeling tables of responses (pandas)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pandas as pd

# One 0/1 column per ABET factor in the manual-coding templates.
LABEL_COLS = [
    "public_health_safety_welfare",
    "global",
    "cultural",
    "social",
    "environmental",
    "economic",
]

# read_csv options the cleaning scripts use: skip malformed lines instead of failing.
CLEANING_CSV_OPTIONS: dict[str, Any] = {"encoding": "utf-8", "on_bad_lines": "skip"}


def read_one_col_csv(path: str | Path, **read_csv_options: Any) -> pd.DataFrame:
    """Read a headerless one-column CSV of responses, dropping blank rows.

    Extra keyword arguments go to pandas.read_csv. driver.py passes
    engine="python"; the cleaning scripts pass CLEANING_CSV_OPTIONS, matching
    what each script originally did.
    """
    df = pd.read_csv(path, header=None, names=["response_text"], **read_csv_options)
    df["response_text"] = df["response_text"].fillna("").astype(str).str.strip()
    return df[df["response_text"] != ""].copy()


def combine_factor_frames(
    frames: dict[str, pd.DataFrame], year: str | None = None
) -> pd.DataFrame:
    """Stack {factor: responses}, drop exact duplicates, and add an id column first.

    With a year, a year column is added and duplicates are judged on
    (response_text, factor, year), as in driver.py. Without one, duplicates are
    judged on (response_text, factor), as in the cleaning scripts.
    """
    parts = []
    for factor, df in frames.items():
        df = df.copy()
        df["factor"] = factor
        if year is not None:
            df["year"] = year
        parts.append(df)

    subset = ["response_text", "factor"] + (["year"] if year is not None else [])
    combined = pd.concat(parts, ignore_index=True)
    combined = combined.drop_duplicates(subset=subset).reset_index(drop=True)
    combined.insert(0, "id", range(len(combined)))
    return combined


def attach_ids(responses: pd.DataFrame, factor: str, lookup: pd.DataFrame) -> pd.DataFrame:
    """Look up each response's id by (factor, response_text); return id, response_text.

    lookup needs id, factor, and response_text columns (a combined table works).
    Rows with no match get a missing id.
    """
    df = responses.copy()
    df["factor"] = factor

    merged = df.merge(
        lookup[["id", "factor", "response_text"]],
        on=["factor", "response_text"],
        how="left",
        validate="many_to_one",
    )
    return merged[["id", "response_text"]].sort_values("id")


def iter_groups(df: pd.DataFrame, cohort: str) -> Iterator[tuple[str, pd.DataFrame]]:
    """Yield (name, rows): all rows as "overall_<cohort>", then one group per factor."""
    yield f"overall_{cohort}", df
    for factor in sorted(df["factor"].dropna().unique()):
        yield factor, df[df["factor"] == factor].copy()


def add_label_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Add a 0 column for each ABET factor in LABEL_COLS (modifies and returns df)."""
    for c in LABEL_COLS:
        df[c] = 0
    return df
