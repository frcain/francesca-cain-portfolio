"""Tests for the education text-analysis scripts.

The shared helpers they import (tokenizer, word counts, topic fitting) are
tested in test_textanalysis.py.

All text here is synthetic and made up for testing. No real student data.
"""

import pandas as pd
import pytest

import add_ids_to_factor_csvs
import analyze_responses
import apply_topic_labels
import combine_f21_csvs
import driver
import make_auto_topics_and_bins
import make_wordcounts_and_hists
import prepare_coding_template
import textanalysis

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


# ---------- scripts use the shared package ----------

def test_scripts_use_shared_helpers():
    # One copy of each helper, imported by every script that needs it.
    assert driver.combine_factor_frames is textanalysis.combine_factor_frames
    assert driver.attach_ids is textanalysis.attach_ids
    assert combine_f21_csvs.combine_factor_frames is textanalysis.combine_factor_frames
    assert add_ids_to_factor_csvs.attach_ids is textanalysis.attach_ids
    assert analyze_responses.simple_tokenize is textanalysis.simple_tokenize
    assert prepare_coding_template.LABEL_COLS is textanalysis.LABEL_COLS


def test_simple_tokenize_keeps_stopwords():
    # analyze_responses intentionally does not remove stopwords.
    tokens = analyze_responses.simple_tokenize("The safe and cheap")
    assert tokens == ["the", "safe", "and", "cheap"]


# ---------- cohort detection ----------

def test_detect_years_on_temp_files(tmp_path):
    for name in ["f21_global.csv", "s22_cultural_factors.csv", "s22_social.csv", "readme.csv"]:
        (tmp_path / name).write_text("made up response\n")
    (tmp_path / "f23_ignored.txt").write_text("not a csv\n")
    assert driver.detect_years(tmp_path) == ["f21", "s22"]


def test_factor_files_for_year_uses_either_pattern(tmp_path):
    (tmp_path / "f21_public_health.csv").write_text("a\n")
    (tmp_path / "f21_global_factors.csv").write_text("b\n")
    found = driver.factor_files_for_year(tmp_path, "f21")
    assert set(found) == {"public_health", "global"}
    assert found["global"].name == "f21_global_factors.csv"


# ---------- combining and ids ----------

def test_combine_one_year_reads_dedupes_and_adds_ids(tmp_path):
    (tmp_path / "f21_global.csv").write_text(
        "global supply chains\n\nglobal supply chains\nshipping cost\n"
    )
    (tmp_path / "f21_economic.csv").write_text("global supply chains\n")
    combined = driver.combine_one_year(tmp_path, "f21")

    assert list(combined.columns) == ["id", "response_text", "factor", "year"]
    assert list(combined["id"]) == [0, 1, 2]
    # same text under two factors is kept; exact duplicate within a factor is dropped
    assert sorted(combined["factor"]) == ["economic", "global", "global"]
    assert set(combined["year"]) == {"f21"}


def test_combine_one_year_with_no_files_raises(tmp_path):
    with pytest.raises(ValueError):
        driver.combine_one_year(tmp_path, "f21")


def test_attach_ids_matches_on_factor_and_text():
    combined = driver.combine_factor_frames(
        {
            "global": pd.DataFrame({"response_text": ["alpha text", "beta text"]}),
            "social": pd.DataFrame({"response_text": ["alpha text"]}),
        },
        "s22",
    )
    responses = pd.DataFrame({"response_text": ["beta text", "alpha text"]})
    out = driver.attach_ids(responses, "global", combined)
    assert list(out["id"]) == [0, 1]
    assert list(out["response_text"]) == ["alpha text", "beta text"]


def test_cleaning_combine_matches_original_file_names():
    files = combine_f21_csvs.factor_files("s22")
    assert list(files) == [
        "s22_public_health.csv",
        "s22_public_safety.csv",
        "s22_public_welfare.csv",
        "s22_global_factors.csv",
        "s22_cultural_factors.csv",
        "s22_social_factors.csv",
        "s22_environmental_factors.csv",
        "s22_economic_factors.csv",
    ]
    assert add_ids_to_factor_csvs.factor_files("s22") == files


def test_cleaning_scripts_read_and_combine_temp_files(tmp_path):
    (tmp_path / "s22_global_factors.csv").write_text("made up one\n\nmade up one\nmade up two\n")
    df = textanalysis.read_one_col_csv(
        tmp_path / "s22_global_factors.csv", **textanalysis.CLEANING_CSV_OPTIONS
    )
    combined = combine_f21_csvs.combine_factor_frames({"global": df})
    assert list(combined.columns) == ["id", "response_text", "factor"]
    assert list(combined["response_text"]) == ["made up one", "made up two"]


def test_cleaning_combine_and_attach_ids_round_trip():
    frames = {
        "global": pd.DataFrame({"response_text": ["one idea", "one idea", "two idea"]}),
        "social": pd.DataFrame({"response_text": ["three idea"]}),
    }
    combined = combine_f21_csvs.combine_factor_frames(frames)
    assert list(combined["id"]) == [0, 1, 2]

    lookup = combined[["id", "factor", "response_text"]]
    out = add_ids_to_factor_csvs.attach_ids(frames["global"], "global", lookup)
    assert list(out["id"]) == [0, 0, 1]


def test_combine_all_cohorts_adds_global_id_first():
    a = pd.DataFrame({"id": [0, 1], "response_text": ["x", "y"]})
    b = pd.DataFrame({"id": [0], "response_text": ["z"]})
    out = driver.combine_all_cohorts([a, b])
    assert list(out.columns)[0] == "global_id"
    assert list(out["global_id"]) == [0, 1, 2]


# ---------- word counts ----------

def test_analyze_word_counts_keep_stopwords():
    c = analyze_responses.count_words_in_responses(["The safe device", "the cost"])
    assert c["the"] == 2
    assert c["safe"] == 1


def test_word_counts_by_group():
    df = pd.DataFrame({
        "cohort": ["f21", "f21", "s22"],
        "response_text": ["safe device", "safe cost", "cost"],
    })
    result = analyze_responses.word_counts_by_group(df, "cohort", "response_text")
    assert result["f21"]["safe"] == 2
    assert result["s22"]["cost"] == 1
    assert "safe" not in result["s22"]


# ---------- topic modeling ----------

def test_analyze_fit_topics_returns_word_lists():
    topics, doc_topic = analyze_responses.fit_topics_for_group(SYNTHETIC_TEXTS, 2, 3)
    assert len(topics) == 2
    assert all(isinstance(t["top_words"], list) and len(t["top_words"]) == 3 for t in topics)
    assert len(doc_topic) == len(SYNTHETIC_TEXTS)
    assert analyze_responses.fit_topics_for_group([], 2, 3) == ([], [])


def test_assign_themes_by_cohort_labels_every_row():
    df = pd.DataFrame({
        "cohort": ["f21"] * 4 + ["s22"] * 4,
        "response_text": SYNTHETIC_TEXTS,
        "major": ["bme"] * 8,
    })
    topics_df, labeled = analyze_responses.assign_themes_by_cohort(
        df, "cohort", "response_text", n_topics=2, n_top_words=3
    )
    assert len(topics_df) == 4  # 2 themes x 2 cohorts
    assert labeled["auto_theme"].notna().all()
    assert labeled.loc[0, "auto_theme"].startswith("f21_topic_")
    assert labeled.loc[7, "auto_theme"].startswith("s22_topic_")
    assert "auto_theme" not in df.columns  # input is not modified
    counts = analyze_responses.theme_counts(labeled, "major")
    assert counts["n_responses"].sum() == 8


# ---------- labels and templates ----------

def test_extract_topic_int():
    assert apply_topic_labels.extract_topic_int(3) == 3
    assert apply_topic_labels.extract_topic_int(2.0) == 2
    assert apply_topic_labels.extract_topic_int(" 4 ") == 4
    assert apply_topic_labels.extract_topic_int("cultural_topic_5") == 5
    assert apply_topic_labels.extract_topic_int("no number") is None
    assert apply_topic_labels.extract_topic_int(float("nan")) is None


def test_label_topic_uses_mapping_then_default():
    mapping = apply_topic_labels.mapping_from_frame(pd.DataFrame({
        "group": ["cultural", "cultural"],
        "topic_id": ["cultural_topic_1", "bad"],
        "theme_label": ["community adoption", "ignored"],
    }))
    assert mapping == {("cultural", 1): "community adoption"}
    assert apply_topic_labels.label_topic("cultural_topic_1", "cultural", mapping) == (
        "community adoption"
    )
    assert apply_topic_labels.label_topic("cultural_topic_2", "cultural", mapping) == (
        "cultural_topic_2"
    )
    assert apply_topic_labels.label_topic("custom", "cultural", mapping) == "custom"


def test_mapping_from_frame_requires_columns():
    with pytest.raises(ValueError):
        apply_topic_labels.mapping_from_frame(pd.DataFrame({"group": ["x"]}))


def test_coding_templates_have_zeroed_label_columns():
    combined = driver.combine_factor_frames(
        {"global": pd.DataFrame({"response_text": ["made up one", "made up two"]})}, "f21"
    )
    template = driver.make_coding_template(combined)
    assert list(template.columns[:4]) == ["id", "year", "factor", "response_text"]
    assert (template[textanalysis.LABEL_COLS] == 0).all().all()

    raw = pd.DataFrame({"response_text": ["made up one", "made up two"]}, index=[5, 9])
    t2 = prepare_coding_template.make_coding_template(raw)
    assert list(t2["id"]) == [0, 1]
    assert list(t2.columns) == ["id", "response_text"] + prepare_coding_template.LABEL_COLS


def test_driver_end_to_end_on_temp_files(tmp_path, capsys):
    for factor, texts in [("global", SYNTHETIC_TEXTS[:4]), ("economic", SYNTHETIC_TEXTS[4:])]:
        (tmp_path / f"f21_{factor}.csv").write_text("\n".join(texts) + "\n")
    driver.main(["--base-dir", str(tmp_path), "--n-topics", "2", "--top-words", "3"])

    assert (tmp_path / "f21_combined_all_factors.csv").exists()
    assert (tmp_path / "f21_global_with_ids.csv").exists()
    assert (tmp_path / "f21_coded_template.csv").exists()
    for group in ["overall_f21", "global", "economic"]:
        assert (tmp_path / "wordcounts_and_hists_f21" / group / "word_counts.csv").exists()
        assert (tmp_path / "auto_topics_and_bins_f21" / group / "auto_topics.csv").exists()
    all_years = pd.read_csv(tmp_path / "all_years_combined_all_factors.csv")
    assert list(all_years.columns) == ["global_id", "id", "response_text", "factor", "year"]
    assert len(all_years) == 8
    assert "with 8 rows" in capsys.readouterr().out


def test_default_cohorts_match_previous_behavior():
    assert apply_topic_labels.parse_args([]).cohort == "f21"
    assert combine_f21_csvs.parse_args([]).cohort == "s22"
    assert make_auto_topics_and_bins.parse_args([]).cohort == "s22"
    assert make_wordcounts_and_hists.parse_args([]).cohort == "s22"
    args = driver.parse_args([])
    assert (args.n_topics, args.top_words, args.hist_top_n) == (6, 15, 30)
