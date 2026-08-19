"""
prep_standardize.py — Dataset Standardization for Preparatory Analysis
======================================================================
Section 2 of the preparatory plan:
  • Select fields relevant to back-labeling
  • Create a combined text column for classification
  • Save preregistrations_clean.parquet
"""
from __future__ import annotations

import pathlib
import logging

import pandas as pd

logger = logging.getLogger(__name__)

PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
PARQUET_PATH = PROCESSED_DIR / "preregistrations.parquet"
CLEAN_PATH = PROCESSED_DIR / "preregistrations_clean.parquet"

KEEP_COLUMNS = [
    "id",
    "date_created",
    "date_modified",
    "registration_supplement",
    "primary_subject",
    "subject_count",
    "tag_count",
    "copyright_holder_count",
    "title",
    "description",
    "registration_responses_text",
    "year_created",
    "month_created",
    "title_word_count",
    "description_word_count",
    "responses_word_count",
    # Option C hierarchy columns
    "subject_l1",
    "subject_l2",
    "subject_l3",
    "psychology_subdiscipline",
    "primary_subject_path",
]


def standardize(df: pd.DataFrame) -> pd.DataFrame:
    """Select relevant columns and build a combined text field."""
    existing = [c for c in KEEP_COLUMNS if c in df.columns]
    out = df[existing].copy()

    out["combined_text"] = (
        df["title"].fillna("")
        + " "
        + df["description"].fillna("")
        + " "
        + df["registration_responses_text"].fillna("")
    ).str.strip()

    out["combined_word_count"] = (
        out["combined_text"].str.split().str.len().fillna(0).astype(int)
    )

    out["has_subject"] = out["primary_subject"].notna() & (
        out["primary_subject"].str.strip() != ""
    )

    logger.info(
        "Standardized dataset: %d rows, %d columns. "
        "Label coverage: %.1f%%",
        len(out),
        len(out.columns),
        out["has_subject"].mean() * 100,
    )
    return out


def run() -> pd.DataFrame:
    """Load existing parquet, standardize, save clean version, return df."""
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    logger.info("Reading %s …", PARQUET_PATH)
    df = pd.read_parquet(PARQUET_PATH)

    # Re-derive date columns that may have been dropped
    if "year_created" not in df.columns and "date_created" in df.columns:
        df["date_created"] = pd.to_datetime(df["date_created"], errors="coerce", utc=True)
        df["year_created"] = df["date_created"].dt.year.astype("Int64")
        df["month_created"] = df["date_created"].dt.to_period("M").astype(str)

    for col, src in [
        ("title_word_count", "title"),
        ("description_word_count", "description"),
        ("responses_word_count", "registration_responses_text"),
    ]:
        if col not in df.columns and src in df.columns:
            df[col] = df[src].fillna("").str.split().str.len()

    out = standardize(df)
    out.to_parquet(CLEAN_PATH, index=False, engine="pyarrow")
    logger.info("Saved → %s", CLEAN_PATH)
    return out


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
    )
    run()
