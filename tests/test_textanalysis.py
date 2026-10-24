"""Tests for the shared textanalysis package.

All text here is synthetic and made up for testing. No real student data.
"""

import subprocess
import sys
from collections import Counter
from pathlib import Path

import pandas as pd
import pytest

import textanalysis as ta
from textanalysis import outputs

SYNTHETIC_TEXTS = [
    "patients need safe affordable devices",
    "affordable devices help patients in rural clinics",
    "safety testing protects patients from device failure",
    "recycled materials reduce environmental waste",
    "environmental impact of plastic waste and packaging",
    "manufacturing cost and economic access for hospitals",
    "cultural values shape how communities adopt devices",
    "global supply chains affect device cost",
]


# ---------- text ----------

def test_tokenize_lowercases_and_drops_stopwords_and_short_words():
    assert ta.tokenize("The Patients and an IV are SAFE") == ["patients", "safe"]


def test_tokenize_handles_non_strings():
    assert ta.tokenize(12345) == []
    assert ta.tokenize(float("nan")) == ["nan"]


def test_tokenize_keeps_apostrophes():
    assert ta.tokenize("patient's device") == ["patient's", "device"]


def test_simple_tokenize_keeps_stopwords():
    assert ta.simple_tokenize("The safe and cheap") == ["the", "safe", "and", "cheap"]


def test_stopword_list_is_unchanged():
    # Guards against accidental edits; the list is part of the original method.
    assert len(ta.STOPWORDS) == 73
    assert {"the", "and", "because", "if"} <= ta.STOPWORDS


def test_word_counts_default_and_custom_tokenizer():
    texts = ["safe devices", "Safe and affordable devices", "devices"]
    c = ta.word_counts(texts)
    assert c == Counter({"devices": 3, "safe": 2, "affordable": 1})
    assert ta.word_counts(texts, ta.simple_tokenize)["and"] == 1


# ---------- cohorts ----------

def test_cohort_from_filename():
    assert ta.cohort_from_filename("f21_public_health.csv") == "f21"
    assert ta.cohort_from_filename("S22_global_factors.csv") == "s22"
    assert ta.cohort_from_filename("notes.csv") is None
    assert ta.cohort_from_filename("x21_global.csv") is None


def test_cohorts_from_filenames_sorted_unique():
    names = ["s22_a.csv", "f21_b.csv", "s22_c.csv", "readme.csv"]
    assert ta.cohorts_from_filenames(names) == ["f21", "s22"]


def test_factor_files_names_and_order():
    files = ta.factor_files("f21")
    assert list(files)[0] == "f21_public_health.csv"
    assert files["f21_global_factors.csv"] == "global"
    assert len(files) == 8


# ---------- tables ----------

def test_read_one_col_csv_drops_blank_rows(tmp_path):
    path = tmp_path / "f21_global.csv"
    path.write_text("  first idea \n\nsecond idea\n")
    df = ta.read_one_col_csv(path, engine="python")
    assert list(df["response_text"]) == ["first idea", "second idea"]


def test_combine_factor_frames_with_and_without_year():
    frames = {
        "global": pd.DataFrame({"response_text": ["same", "same", "other"]}),
        "social": pd.DataFrame({"response_text": ["same"]}),
    }
    with_year = ta.combine_factor_frames(frames, "f21")
    assert list(with_year.columns) == ["id", "response_text", "factor", "year"]
    assert list(with_year["id"]) == [0, 1, 2]

    no_year = ta.combine_factor_frames(frames)
    assert list(no_year.columns) == ["id", "response_text", "factor"]
    assert list(no_year["factor"]) == ["global", "global", "social"]
    assert "year" not in frames["global"].columns  # inputs are not modified


def test_attach_ids_missing_match_gets_nan():
    lookup = pd.DataFrame({"id": [0], "factor": ["global"], "response_text": ["known"]})
    out = ta.attach_ids(pd.DataFrame({"response_text": ["known", "new"]}), "global", lookup)
    assert out["id"].iloc[0] == 0
    assert out["id"].isna().iloc[1]


def test_iter_groups_overall_then_sorted_factors():
    df = pd.DataFrame({"factor": ["social", "global", "social"], "response_text": list("abc")})
    groups = list(ta.iter_groups(df, "s22"))
    assert [name for name, _ in groups] == ["overall_s22", "global", "social"]
    assert len(groups[2][1]) == 2


def test_add_label_columns():
    out = ta.add_label_columns(pd.DataFrame({"id": [0, 1]}))
    assert list(out.columns) == ["id"] + ta.LABEL_COLS
    assert (out[ta.LABEL_COLS] == 0).all().all()


# ---------- topics ----------

def test_fit_topics_shapes():
    topics, doc_topic = ta.fit_topics(SYNTHETIC_TEXTS, n_topics=3, n_top_words=4)
    assert [t["topic_id"] for t in topics] == [0, 1, 2]
    assert all(len(t["top_words"].split(", ")) == 4 for t in topics)
    assert len(doc_topic) == len(SYNTHETIC_TEXTS)
    assert set(doc_topic) <= {0, 1, 2}


def test_fit_topics_caps_topics_at_document_count():
    topics, doc_topic = ta.fit_topics(SYNTHETIC_TEXTS[:2], n_topics=6, n_top_words=3)
    assert len(topics) == 2
    assert len(doc_topic) == 2


def test_fit_topics_is_deterministic():
    first = ta.fit_topics(SYNTHETIC_TEXTS, 3, 5)
    second = ta.fit_topics(SYNTHETIC_TEXTS, 3, 5)
    assert first[0] == second[0]
    assert list(first[1]) == list(second[1])


def test_fit_nmf_matches_fit_topics_and_accepts_tokenizer():
    words, doc_topic = ta.fit_nmf(SYNTHETIC_TEXTS, 3, 5)
    topics, doc_topic2 = ta.fit_topics(SYNTHETIC_TEXTS, 3, 5)
    assert [", ".join(w) for w in words] == [t["top_words"] for t in topics]
    assert list(doc_topic) == list(doc_topic2)

    words_simple, _ = ta.fit_nmf(SYNTHETIC_TEXTS, 2, 50, ta.simple_tokenize)
    assert any("and" in w for w in words_simple)  # stopwords kept with simple_tokenize


def test_topic_bin_labels():
    assert ta.topic_bin_labels("cultural", [0, 2]) == ["cultural_topic_0", "cultural_topic_2"]
    assert ta.topic_bin_labels("cultural", []) == []


# ---------- outputs ----------

def test_save_word_counts_and_topic_bins(tmp_path):
    df = pd.DataFrame({"factor": ["global"] * 8, "response_text": SYNTHETIC_TEXTS})
    outputs.save_word_counts(df, tmp_path / "wc", "global", top_n=5)
    counts = pd.read_csv(tmp_path / "wc" / "word_counts.csv")
    assert list(counts.columns) == ["word", "count"]
    # "patients" and "devices" both appear 3 times; the first one seen comes first.
    assert counts.iloc[0].to_dict() == {"word": "patients", "count": 3}
    assert (tmp_path / "wc" / "top_words_hist.png").exists()

    outputs.save_topic_bins(df, tmp_path / "tb", "global", n_topics=2, n_top_words=3)
    topics = pd.read_csv(tmp_path / "tb" / "auto_topics.csv")
    assert list(topics.columns) == ["topic_id", "top_words"]
    bins = pd.read_csv(tmp_path / "tb" / "responses_with_auto_bins.csv")
    assert list(bins.columns) == ["factor", "response_text", "auto_bin"]
    assert bins["auto_bin"].str.startswith("global_topic_").all()


def test_save_hist_skips_empty_counter(tmp_path):
    outputs.save_hist(Counter(), tmp_path / "empty.png", "empty")
    assert not (tmp_path / "empty.png").exists()


@pytest.mark.parametrize("module", ["textanalysis", "textanalysis.outputs"])
def test_import_does_not_load_matplotlib(module):
    code = f"import sys, {module}; print('matplotlib' in sys.modules)"
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True,
        cwd=str(Path(__file__).resolve().parents[1]),
    )
    assert result.stdout.strip() == "False"
