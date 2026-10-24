"""Shared pytest setup: make each project's scripts importable from the repo root.

The projects are folders of standalone scripts (not installed packages), so
their directories are added to sys.path here, along with the repository root
for the shared textanalysis package. Matplotlib is forced to the
non-interactive Agg backend so tests run without a display.
"""

import os
import sys
from pathlib import Path

os.environ.setdefault("MPLBACKEND", "Agg")

REPO_ROOT = Path(__file__).resolve().parents[1]

for sub in [
    "",
    "braillemate",
    "engineering-education-text-analysis",
    "engineering-education-text-analysis/cleaning_scripts",
    "force-sensing-tether/desktop",
]:
    path = str(REPO_ROOT / sub)
    if path not in sys.path:
        sys.path.insert(0, path)
