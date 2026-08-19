"""
prep_psych_descriptive.py — Psychology Subdiscipline Descriptive Analysis (Option A)
=====================================================================================
Filters to rows labelled Psychology (under Social and Behavioral Sciences) and
produces landscape outputs for 2020–2025 (and full labelled span):

  - Counts / proportions per psychology_subdiscipline
  - Year × subdiscipline shares (2020–2025)
  - Schema distribution per subdiscipline (top-N)
  - Median combined_word_count by subdiscipline
"""
from __future__ import annotations

import pathlib
import logging

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns

logger = logging.getLogger(__name__)

PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
TABLES_DIR = PROJECT_ROOT / "reports" / "tables" / "landscape"
FIGURES_DIR = PROJECT_ROOT / "reports" / "figures" / "landscape"

sns.set_theme(style="whitegrid", palette="muted", font_scale=1.1)


def _psych_mask(df: pd.DataFrame) -> pd.Series:
    return (
        (df.get("subject_l1", pd.Series("", index=df.index)) == "Social and Behavioral Sciences")
        & (df.get("subject_l2", pd.Series("", index=df.index)) == "Psychology")
    )


# ── Subdiscipline counts (overall) ──────────────────────────────────

def subdiscipline_counts(df: pd.DataFrame) -> pd.DataFrame:
    """Counts and proportions per psychology_subdiscipline for all years."""
    psych = df[_psych_mask(df)].copy()
    if psych.empty:
        logger.warning("No Psychology rows found.")
        return pd.DataFrame()

    psych["_sub"] = psych["psychology_subdiscipline"].fillna("(unspecified)")
    counts = psych["_sub"].value_counts().reset_index()
    counts.columns = ["psychology_subdiscipline", "count"]
    counts["proportion"] = (counts["count"] / counts["count"].sum()).round(6)
    counts.to_csv(TABLES_DIR / "psych_subdiscipline_counts.csv", index=False)

    fig, ax = plt.subplots(figsize=(10, max(4, len(counts) * 0.35)))
    ax.barh(counts["psychology_subdiscipline"][::-1], counts["count"][::-1], color="#4C72B0")
    ax.set_xlabel("Count")
    ax.set_title("Psychology Subdiscipline Counts (all labelled years)")
    plt.tight_layout()
    fig.savefig(FIGURES_DIR / "psych_subdiscipline_counts.png", dpi=200)
    plt.close(fig)

    logger.info("Saved psych_subdiscipline_counts.csv + figure (%d Psychology rows)", len(psych))
    return counts


# ── Year × subdiscipline shares (2020–2025) ──────────────────────────

def yearly_subdiscipline_shares(
    df: pd.DataFrame,
    year_min: int = 2020,
    year_max: int = 2025,
) -> pd.DataFrame:
    """Year × subdiscipline share table and heatmap."""
    psych = df[_psych_mask(df)].copy()
    if psych.empty:
        logger.warning("No Psychology rows found for yearly shares.")
        return pd.DataFrame()

    psych["_sub"] = psych["psychology_subdiscipline"].fillna("(unspecified)")
    scope = psych[
        (psych["year_created"] >= year_min) & (psych["year_created"] <= year_max)
    ]
    if scope.empty:
        logger.warning("No Psychology rows in %d–%d.", year_min, year_max)
        return pd.DataFrame()

    pivot = (
        scope.groupby(["year_created", "_sub"])
        .size()
        .unstack(fill_value=0)
    )
    # Row-normalise to shares
    shares = pivot.div(pivot.sum(axis=1), axis=0).round(4)
    shares.index.name = "year_created"
    shares.reset_index().to_csv(TABLES_DIR / "psych_yearly_subdiscipline_shares.csv", index=False)
    pivot.reset_index().to_csv(TABLES_DIR / "psych_yearly_subdiscipline_counts.csv", index=False)

    # Heatmap of shares
    fig, ax = plt.subplots(figsize=(max(10, len(shares.columns) * 0.9), 6))
    sns.heatmap(
        shares.T,
        annot=True, fmt=".2f", cmap="Blues",
        ax=ax, cbar_kws={"label": "Share"},
    )
    ax.set_title(f"Psychology Subdiscipline Shares by Year ({year_min}–{year_max})")
    ax.set_xlabel("Year")
    ax.set_ylabel("Subdiscipline")
    plt.tight_layout()
    fig.savefig(FIGURES_DIR / "psych_yearly_subdiscipline_shares.png", dpi=200)
    plt.close(fig)

    logger.info(
        "Saved psych_yearly_subdiscipline_shares.csv + figure (%d–%d).", year_min, year_max
    )
    return shares


# ── Schema distribution per subdiscipline ───────────────────────────

def schema_by_subdiscipline(df: pd.DataFrame, top_n: int = 10) -> pd.DataFrame:
    """Top-N schemas per psychology_subdiscipline."""
    psych = df[_psych_mask(df)].copy()
    if psych.empty:
        return pd.DataFrame()

    psych["_sub"] = psych["psychology_subdiscipline"].fillna("(unspecified)")
    schema_col = "registration_supplement"
    if schema_col not in psych.columns:
        logger.warning("Column '%s' not found.", schema_col)
        return pd.DataFrame()

    rows = []
    for sub, grp in psych.groupby("_sub"):
        top = grp[schema_col].fillna("(unknown)").value_counts().head(top_n)
        for schema, cnt in top.items():
            rows.append({"subdiscipline": sub, "schema": schema, "count": cnt})

    result = pd.DataFrame(rows)
    result.to_csv(TABLES_DIR / "psych_schema_by_subdiscipline.csv", index=False)
    logger.info("Saved psych_schema_by_subdiscipline.csv")
    return result


# ── Median word count by subdiscipline ──────────────────────────────

def wordcount_by_subdiscipline(df: pd.DataFrame) -> pd.DataFrame:
    """Median combined_word_count by psychology_subdiscipline."""
    psych = df[_psych_mask(df)].copy()
    if psych.empty:
        return pd.DataFrame()

    if "combined_word_count" not in psych.columns:
        logger.warning("'combined_word_count' column not found — skipping word count analysis.")
        return pd.DataFrame()

    psych["_sub"] = psych["psychology_subdiscipline"].fillna("(unspecified)")
    result = (
        psych.groupby("_sub")["combined_word_count"]
        .agg(["median", "mean", "count"])
        .reset_index()
        .rename(columns={"_sub": "psychology_subdiscipline", "median": "median_wc", "mean": "mean_wc", "count": "n"})
    )
    result["mean_wc"] = result["mean_wc"].round(1)
    result.to_csv(TABLES_DIR / "psych_wordcount_by_subdiscipline.csv", index=False)
    logger.info("Saved psych_wordcount_by_subdiscipline.csv")
    return result


# ── Orchestrator ─────────────────────────────────────────────────────

def run(df: pd.DataFrame) -> dict:
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)

    results = {}
    results["counts"] = subdiscipline_counts(df)
    results["yearly_shares"] = yearly_subdiscipline_shares(df)
    results["schema"] = schema_by_subdiscipline(df)
    results["wordcount"] = wordcount_by_subdiscipline(df)
    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-8s  %(message)s")
    CLEAN_PATH = PROJECT_ROOT / "data" / "processed" / "preregistrations_clean.parquet"
    df = pd.read_parquet(CLEAN_PATH)
    run(df)
