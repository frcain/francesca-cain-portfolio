"""Cohort prefixes ("f21", "s22") and per-factor input file names."""

from __future__ import annotations

import re
from collections.abc import Iterable

COHORT_PREFIX_RE = re.compile(r"^([fs]\d{2})_")

# File name (after the "<cohort>_" prefix) -> factor label, as used by the
# cleaning scripts.
FILE_SUFFIXES = {
    "public_health.csv": "public_health",
    "public_safety.csv": "public_safety",
    "public_welfare.csv": "public_welfare",
    "global_factors.csv": "global",
    "cultural_factors.csv": "cultural",
    "social_factors.csv": "social",
    "environmental_factors.csv": "environmental",
    "economic_factors.csv": "economic",
}


def cohort_from_filename(name: str) -> str | None:
    """Return the cohort prefix ("f21", "s22", ...) of a file name, or None."""
    m = COHORT_PREFIX_RE.match(name.lower())
    return m.group(1) if m else None


def cohorts_from_filenames(names: Iterable[str]) -> list[str]:
    """Sorted unique cohort prefixes found in a list of file names."""
    years = set()
    for name in names:
        cohort = cohort_from_filename(name)
        if cohort:
            years.add(cohort)
    return sorted(years)


def factor_files(cohort: str) -> dict[str, str]:
    """Map each input file name for a cohort to its factor, e.g. s22_global_factors.csv."""
    return {f"{cohort}_{suffix}": factor for suffix, factor in FILE_SUFFIXES.items()}
