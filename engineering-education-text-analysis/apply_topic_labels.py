"""Replace auto-generated NMF topic ids with human-readable theme labels.

Reads topic_label_map.csv (columns: group, topic_id, theme_label) and, for
each group folder under auto_topics_and_bins_<cohort>/ (default cohort: f21),
writes responses_with_named_themes.csv with a theme_label column. Topics
without a mapping keep the default "<group>_topic_<id>" name. If the map file
is missing, an empty template is created.

Usage:
    python3 apply_topic_labels.py [--cohort f21] [--map topic_label_map.csv]
"""

import argparse
import os
import re

import pandas as pd

# (group, topic_id) -> theme_label
LabelMap = dict[tuple[str, int], str]

MAP_PATH = "topic_label_map.csv"
DEFAULT_COHORT = "f21"
OUT_NAME = "responses_with_named_themes.csv"
MAP_COLUMNS = ["group", "topic_id", "theme_label"]


def extract_topic_int(x: object) -> int | None:
    """Return an int topic id if possible, else None."""
    if pd.isna(x):
        return None
    # numeric types
    if isinstance(x, (int,)):
        return int(x)
    if isinstance(x, (float,)):
        return int(x)
    # strings
    if isinstance(x, str):
        s = x.strip()
        if s.isdigit():
            return int(s)
        m = re.search(r"(\d+)$", s)  # grab trailing digits: cultural_topic_5 -> 5
        if m:
            return int(m.group(1))
    return None


def mapping_from_frame(mapping: pd.DataFrame) -> LabelMap:
    """Build {(group, topic_id): theme_label} from a map table; skip rows without an id."""
    needed = set(MAP_COLUMNS)
    if not needed.issubset(set(mapping.columns)):
        raise ValueError(
            f"Label map must have columns {sorted(needed)}. Got {mapping.columns.tolist()}"
        )

    m: LabelMap = {}
    for _, r in mapping.iterrows():
        grp = str(r["group"])
        tid = extract_topic_int(r["topic_id"])
        if tid is None:
            continue
        m[(grp, tid)] = str(r["theme_label"])
    return m


def label_topic(val: object, group: str, mapping: LabelMap) -> str:
    """Theme label for one auto_bin / topic_id value within a group."""
    tid = extract_topic_int(val)
    if tid is None:
        # already a string label like "cultural_topic_5" or something custom
        return str(val)
    return mapping.get((group, tid), f"{group}_topic_{tid}")


def load_mapping(map_path: str = MAP_PATH) -> LabelMap:
    """Load {(group, topic_id): theme_label}; create an empty map file if missing."""
    # If missing/empty, create a template and return empty mapping
    try:
        mapping = pd.read_csv(map_path)
    except (FileNotFoundError, pd.errors.EmptyDataError):
        mapping = pd.DataFrame(columns=MAP_COLUMNS)
        mapping.to_csv(map_path, index=False)
        print(f"⚠️ created empty {map_path} (add rows to label topics)")
        return {}

    return mapping_from_frame(mapping)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Apply human-readable labels to NMF topics.")
    p.add_argument("--cohort", default=DEFAULT_COHORT,
                   help=f"Cohort prefix; reads auto_topics_and_bins_<cohort>/ "
                        f"(default: {DEFAULT_COHORT}).")
    p.add_argument("--in-dir", default=None,
                   help="Override the input folder (default: auto_topics_and_bins_<cohort>).")
    p.add_argument("--map", dest="map_path", default=MAP_PATH,
                   help=f"Label map CSV (default: {MAP_PATH}).")
    p.add_argument("--out-name", default=OUT_NAME,
                   help=f"Output file name in each group folder (default: {OUT_NAME}).")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    in_dir = args.in_dir or f"auto_topics_and_bins_{args.cohort}"
    m = load_mapping(args.map_path)

    for group in sorted(os.listdir(in_dir)):
        group_path = os.path.join(in_dir, group)
        if not os.path.isdir(group_path):
            continue

        in_csv = os.path.join(group_path, "responses_with_auto_bins.csv")
        if not os.path.exists(in_csv):
            continue

        df = pd.read_csv(in_csv)

        if "auto_bin" in df.columns:
            bin_col = "auto_bin"
        elif "topic_id" in df.columns:
            bin_col = "topic_id"
        else:
            raise ValueError(
                f"{in_csv} missing 'auto_bin' or 'topic_id'. Columns: {df.columns.tolist()}"
            )

        df["theme_label"] = df[bin_col].apply(lambda val: label_topic(val, group, m))

        out_csv = os.path.join(group_path, args.out_name)
        df.to_csv(out_csv, index=False)
        print(f"✅ wrote {out_csv}")


if __name__ == "__main__":
    main()
