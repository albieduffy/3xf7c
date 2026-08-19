"""
load.py — Data Ingestion & Normalization
=========================================
Reads the raw JSONL dump of OSF preregistrations, flattens nested
fields, and persists a clean one-row-per-registration parquet file
plus optional exploded tables for tags and subjects.
"""
from __future__ import annotations

import json
import pathlib
import logging

import pandas as pd
import numpy as np
from tqdm import tqdm

logger = logging.getLogger(__name__)

# ── Paths ────────────────────────────────────────────────────────────
PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
RAW_PATH = PROJECT_ROOT / "data" / "raw" / "preregistrations-2025.jsonl"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"


# ── Helpers ──────────────────────────────────────────────────────────

def _safe_get(d: dict, *keys, default=None):
    """Safely navigate a nested dict."""
    for k in keys:
        if isinstance(d, dict):
            d = d.get(k, default)
        else:
            return default
    return d


def _flatten_record(rec: dict) -> dict:
    """
    Turn one raw JSONL record into a flat dict suitable for a DataFrame row.
    """
    attrs = rec.get("attributes", {})
    rels = rec.get("relationships", {})

    # --- Core identifiers ---
    row = {
        "id": rec.get("id"),
        "type": rec.get("type"),
    }

    # --- Attribute scalars ---
    scalar_fields = [
        "title", "description", "category", "custom_citation",
        "date_created", "date_modified", "date_registered", "date_withdrawn",
        "registration", "preprint", "fork", "collection",
        "public", "reviews_state", "article_doi",
        "pending_embargo_approval", "pending_embargo_termination_approval",
        "embargoed", "pending_registration_approval", "archiving",
        "pending_withdrawal", "withdrawn",
        "has_project", "has_data", "has_analytic_code",
        "has_materials", "has_papers", "has_supplements",
        "registration_supplement",  # ← schema / template name
        "revision_state",
        "embargo_end_date", "withdrawal_justification",
    ]
    for f in scalar_fields:
        row[f] = attrs.get(f)

    # --- Tags ---
    row["tags"] = attrs.get("tags") or []
    row["tag_count"] = len(row["tags"])

    # --- License / copyright holders (proxy for contributors) ---
    license_info = attrs.get("node_license", {}) or {}
    copyright_holders = license_info.get("copyright_holders", []) or []
    row["copyright_holders"] = copyright_holders
    row["copyright_holder_count"] = len(copyright_holders)
    row["license_year"] = license_info.get("year", "")

    # --- Subjects ---
    # subjects_raw is a list-of-paths; each path is a list of {id, text} nodes
    # ordered from root (L1) to leaf (L2, L3, …).
    subjects_raw = attrs.get("subjects") or []
    subject_texts = []
    if subjects_raw:
        for path in subjects_raw:
            for node in (path if isinstance(path, list) else []):
                subject_texts.append(node.get("text", ""))
    row["subjects"] = subject_texts
    row["subject_count"] = len(subject_texts)

    # --- Hierarchy extraction (Option C) ---
    # Select preferred path: prefer SBS → Psychology (max depth), else first path.
    chosen_path: list[str] = []
    if subjects_raw:
        sbs_psych_paths = []
        sbs_paths = []
        for path in subjects_raw:
            if not isinstance(path, list):
                continue
            texts = [n.get("text", "") for n in path]
            if len(texts) >= 1 and texts[0] == "Social and Behavioral Sciences":
                if len(texts) >= 2 and texts[1] == "Psychology":
                    sbs_psych_paths.append(texts)
                else:
                    sbs_paths.append(texts)
        if sbs_psych_paths:
            # Prefer deepest; ties broken by API order
            chosen_path = max(sbs_psych_paths, key=len)
        elif sbs_paths:
            chosen_path = max(sbs_paths, key=len)
        else:
            # Fall back to first path
            first = subjects_raw[0]
            if isinstance(first, list):
                chosen_path = [n.get("text", "") for n in first]

    row["subject_l1"] = chosen_path[0] if len(chosen_path) > 0 else None
    row["subject_l2"] = chosen_path[1] if len(chosen_path) > 1 else None
    row["subject_l3"] = chosen_path[2] if len(chosen_path) > 2 else None
    row["psychology_subdiscipline"] = (
        chosen_path[2]
        if (
            len(chosen_path) >= 3
            and chosen_path[0] == "Social and Behavioral Sciences"
            and chosen_path[1] == "Psychology"
        )
        else None
    )
    row["primary_subject_path"] = " > ".join(chosen_path) if chosen_path else None
    # Backward-compatible: primary_subject = L1 of chosen path
    row["primary_subject"] = chosen_path[0] if chosen_path else None

    # --- Registration schema id ---
    row["registration_schema_id"] = _safe_get(
        rels, "registration_schema", "data", "id"
    )

    # --- Registered by (user id) ---
    row["registered_by_user_id"] = _safe_get(
        rels, "registered_by", "data", "id"
    )

    # --- Registered from (project / node id) ---
    row["registered_from_node_id"] = _safe_get(
        rels, "registered_from", "data", "id"
    )

    # --- Registration responses (flat text answers) ---
    responses = attrs.get("registration_responses", {}) or {}
    # Concatenate all non-empty string values for an aggregate text field
    response_texts = []
    for key, val in responses.items():
        if isinstance(val, str) and val.strip():
            response_texts.append(val.strip())
        elif isinstance(val, list):
            for item in val:
                if isinstance(item, str) and item.strip():
                    response_texts.append(item.strip())
    row["registration_responses_text"] = "\n".join(response_texts)
    row["registration_response_count"] = len(response_texts)

    # --- Provider ---
    row["provider_id"] = _safe_get(rels, "provider", "data", "id")

    return row


# ── Main loader ──────────────────────────────────────────────────────

def load_raw(path: pathlib.Path = RAW_PATH,
             nrows: int | None = None) -> pd.DataFrame:
    """
    Stream-read the JSONL file, flatten each record, return a DataFrame.

    Parameters
    ----------
    path : pathlib.Path
        Path to the raw JSONL file.
    nrows : int | None
        If given, only read the first *nrows* lines (useful for dev/debug).

    Returns
    -------
    pd.DataFrame
    """
    records = []
    logger.info("Loading raw JSONL from %s …", path)

    with open(path, "r", encoding="utf-8") as fh:
        for i, line in enumerate(tqdm(fh, desc="Reading JSONL", unit=" records")):
            if nrows is not None and i >= nrows:
                break
            try:
                rec = json.loads(line)
                records.append(_flatten_record(rec))
            except json.JSONDecodeError:
                logger.warning("Skipping malformed JSON at line %d", i + 1)

    df = pd.DataFrame(records)
    logger.info("Loaded %d records with %d columns.", len(df), len(df.columns))
    return df


def normalize_dtypes(df: pd.DataFrame) -> pd.DataFrame:
    """Cast columns to proper dtypes after loading."""
    date_cols = ["date_created", "date_modified", "date_registered",
                 "date_withdrawn", "embargo_end_date"]
    for col in date_cols:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce", utc=True)

    bool_cols = [
        "registration", "preprint", "fork", "collection", "public",
        "pending_embargo_approval", "pending_embargo_termination_approval",
        "embargoed", "pending_registration_approval", "archiving",
        "pending_withdrawal", "withdrawn",
        "has_project", "has_data", "has_analytic_code",
        "has_materials", "has_papers", "has_supplements",
    ]
    for col in bool_cols:
        if col in df.columns:
            df[col] = df[col].astype("boolean")

    return df


def add_derived_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Add useful derived columns."""
    if "date_created" in df.columns:
        df["year_created"] = df["date_created"].dt.year.astype("Int64")
        df["month_created"] = df["date_created"].dt.to_period("M").astype(str)

    if "title" in df.columns:
        df["title_length"] = df["title"].fillna("").str.len()
        df["title_word_count"] = df["title"].fillna("").str.split().str.len()

    if "description" in df.columns:
        df["description_length"] = df["description"].fillna("").str.len()
        df["description_word_count"] = (
            df["description"].fillna("").str.split().str.len()
        )

    if "registration_responses_text" in df.columns:
        df["responses_length"] = (
            df["registration_responses_text"].fillna("").str.len()
        )
        df["responses_word_count"] = (
            df["registration_responses_text"].fillna("").str.split().str.len()
        )

    return df


def build_tags_table(df: pd.DataFrame) -> pd.DataFrame:
    """Explode tags into a long-form table (id, tag)."""
    tags_df = df[["id", "tags"]].explode("tags").dropna(subset=["tags"])
    tags_df = tags_df.rename(columns={"tags": "tag"})
    return tags_df.reset_index(drop=True)


def build_subjects_table(df: pd.DataFrame) -> pd.DataFrame:
    """Explode subjects into a long-form table (id, subject)."""
    subj_df = df[["id", "subjects"]].explode("subjects").dropna(subset=["subjects"])
    subj_df = subj_df.rename(columns={"subjects": "subject"})
    return subj_df.reset_index(drop=True)


# ── Orchestrator ─────────────────────────────────────────────────────

def run(nrows: int | None = None) -> pd.DataFrame:
    """
    Full load pipeline: read → normalize → derive → save parquet.
    Returns the primary DataFrame.
    """
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    df = load_raw(nrows=nrows)
    df = normalize_dtypes(df)
    df = add_derived_columns(df)

    # Save primary table
    out_path = PROCESSED_DIR / "preregistrations.parquet"
    # Drop list columns for parquet (store separately)
    df_save = df.drop(columns=["tags", "subjects", "copyright_holders"], errors="ignore")
    df_save.to_parquet(out_path, index=False, engine="pyarrow")
    logger.info("Saved primary table → %s (%d rows)", out_path, len(df_save))

    # Save exploded tables
    tags_df = build_tags_table(df)
    tags_path = PROCESSED_DIR / "tags.parquet"
    tags_df.to_parquet(tags_path, index=False, engine="pyarrow")
    logger.info("Saved tags table → %s (%d rows)", tags_path, len(tags_df))

    subjects_df = build_subjects_table(df)
    subj_path = PROCESSED_DIR / "subjects.parquet"
    subjects_df.to_parquet(subj_path, index=False, engine="pyarrow")
    logger.info("Saved subjects table → %s (%d rows)", subj_path, len(subjects_df))

    return df


# ── CLI entry point ──────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
    )
    run()
