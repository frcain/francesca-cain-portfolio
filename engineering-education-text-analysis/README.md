# Engineering Education Text Analysis

Research code from my role as Lead Researcher with Carnegie Mellon's College of Engineering (Office of the Associate Dean). The project analyzes de-identified biomedical engineering capstone reflections to understand how students engage with ABET Student Outcomes 2 and 4, including public health, safety, welfare, ethics, and global, cultural, social, environmental, and economic considerations.

**Data is not included.** The student responses are confidential, so this repository contains code only. The tests use made-up sentences.

## Project structure

- `driver.py`: Runs the full pipeline on every cohort it finds (cohorts are detected from file prefixes such as `f21_` and `s22_`): combining per-factor CSVs with response ids, word frequency analysis, TF-IDF vectorization, and NMF topic modeling to surface themes for each design factor.
- `analyze_responses.py`: Word counts and themes by cohort, plus theme counts by major and project type, from a single responses CSV.
- `apply_topic_labels.py`: Maps NMF topics to human-readable theme labels from `topic_label_map.csv`.
- `cleaning_scripts/`: Earlier single-cohort versions of the pipeline steps: combine per-factor CSVs (`combine_f21_csvs.py`; the name is historical and the default cohort is `s22`), attach response ids, build coding templates, word counts and histograms, and topic bins.

Helpers that several scripts need (tokenizer and stopword list, cohort detection, reading and combining the per-factor CSVs, attaching ids, word counts, TF-IDF and NMF topic fitting, and writing word counts, histograms, and topic bins) live in the shared `textanalysis` package at the repository root, so there is one copy of each. The scripts keep their own command-line interfaces, file names, and cohort-level steps. `analyze_responses.py` uses `textanalysis.simple_tokenize`, which keeps stopwords, as in the original analysis; `driver.py` and the cleaning scripts count words and fit topics with `textanalysis.tokenize`, which removes them.

## Install

From the repository root: `pip install -e ".[dev]"` (installs pandas, scikit-learn, matplotlib, and the `textanalysis` package). Each script also adds the repository root to its import path, so it runs directly without installing.

## Run

Run from the folder that holds the CSVs (the scripts can live anywhere; give their path). With no arguments each script uses its original file names and settings.

```bash
python3 driver.py                       # all cohorts found in the current folder
python3 driver.py --base-dir data --n-topics 8 --top-words 10
python3 analyze_responses.py --input bme_capstone_responses.csv
python3 apply_topic_labels.py --cohort f21

cd cleaning_scripts
python3 combine_f21_csvs.py --cohort s22 --folder ../original_responses
python3 add_ids_to_factor_csvs.py --cohort s22
python3 make_wordcounts_and_hists.py --cohort s22
python3 make_auto_topics_and_bins.py --cohort s22
python3 prepare_coding_template.py
```

Use `--help` on any script for the full list of options.

## Tests

From the repository root:

```bash
python3 -m pytest -q tests/test_textanalysis.py tests/test_education_pipeline.py
mypy textanalysis
```

`test_textanalysis.py` covers the shared helpers: tokenizers, word counts, cohort detection, reading and combining CSVs, id matching, and a small TF-IDF and NMF run on eight synthetic sentences. `test_education_pipeline.py` covers the script-level steps (cohort detection on temporary files, templates, topic labeling, per-cohort themes) and runs `driver.py` end to end on temporary files.

## Methods

Python, pandas, scikit-learn (`TfidfVectorizer`, `NMF`), matplotlib.
