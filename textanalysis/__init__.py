"""Shared helpers for the engineering education text-analysis scripts.

The scripts in engineering-education-text-analysis/ used to each carry their
own copy of these functions. They now import them from here so there is one
version of the tokenizer, stopword list, cohort detection, CSV helpers, word
counts, and TF-IDF + NMF topic fitting.

Modules:
    text     tokenizers, stopwords, word counts
    cohorts  cohort prefixes ("f21", "s22") and per-factor file names
    tables   reading, combining, and labeling response tables (pandas)
    topics   TF-IDF + NMF topic fitting (scikit-learn)
    outputs  writing word counts, histograms, and topic bins to disk (matplotlib)

`outputs` is not imported here, so importing the package does not load
matplotlib.
"""

from textanalysis.cohorts import (
    COHORT_PREFIX_RE,
    FILE_SUFFIXES,
    cohort_from_filename,
    cohorts_from_filenames,
    factor_files,
)
from textanalysis.tables import (
    CLEANING_CSV_OPTIONS,
    LABEL_COLS,
    add_label_columns,
    attach_ids,
    combine_factor_frames,
    iter_groups,
    read_one_col_csv,
)
from textanalysis.text import STOPWORDS, simple_tokenize, tokenize, word_counts
from textanalysis.topics import fit_nmf, fit_topics, topic_bin_labels

__all__ = [
    "CLEANING_CSV_OPTIONS",
    "COHORT_PREFIX_RE",
    "FILE_SUFFIXES",
    "LABEL_COLS",
    "STOPWORDS",
    "add_label_columns",
    "attach_ids",
    "cohort_from_filename",
    "cohorts_from_filenames",
    "combine_factor_frames",
    "factor_files",
    "fit_nmf",
    "fit_topics",
    "iter_groups",
    "read_one_col_csv",
    "simple_tokenize",
    "tokenize",
    "topic_bin_labels",
    "word_counts",
]
