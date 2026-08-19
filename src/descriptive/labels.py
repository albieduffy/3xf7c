"""
prep_labels.py — Label Diagnostics & Missingness Analysis
==========================================================
Sections 3–4 of the preparatory plan:
  • Label coverage
  • Subject distribution + Shannon entropy
  • Rare class detection
  • Missingness by year, schema, and text length
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
TABLES_DIR = PROJECT_ROOT / "reports" / "tables" / "labels"
FIGURES_DIR = PROJECT_ROOT / "reports" / "figures" / "labels"
LANDSCAPE_TABLES = PROJECT_ROOT / "reports" / "tables" / "landscape"
LANDSCAPE_FIGURES = PROJECT_ROOT / "reports" / "figures" / "landscape"

sns.set_theme(style="whitegrid", palette="muted", font_scale=1.1)


def _labeled_mask(df: pd.DataFrame) -> pd.Series:
    return df["primary_subject"].notna() & (df["primary_subject"].str.strip() != "")


# ── 3.1  Label coverage ─────────────────────────────────────────────

def label_coverage(df: pd.DataFrame) -> pd.DataFrame:
    total = len(df)
    labeled = _labeled_mask(df).sum()
    missing = total - labeled

    stats = pd.DataFrame([{
        "total_records": total,
        "labeled": int(labeled),
        "missing": int(missing),
        "label_coverage": round(labeled / total, 4),
        "missing_rate": round(missing / total, 4),
    }])
    stats.to_csv(TABLES_DIR / "label_coverage.csv", index=False)
    logger.info(
        "Label coverage: %d / %d (%.1f%%)",
        labeled, total, labeled / total * 100,
    )
    return stats


# ── 3.2  Subject distribution ───────────────────────────────────────

def subject_distribution(df: pd.DataFrame) -> tuple[pd.DataFrame, float]:
    """Returns (counts_df, shannon_entropy)."""
    labeled = df.loc[_labeled_mask(df), "primary_subject"]
    counts = labeled.value_counts().reset_index()
    counts.columns = ["subject", "count"]
    counts["proportion"] = (counts["count"] / counts["count"].sum()).round(6)
    counts["cumulative"] = counts["proportion"].cumsum().round(6)

    # Shannon entropy
    p = counts["proportion"].values
    entropy = float(-np.sum(p * np.log2(p + 1e-12)))
    logger.info(
        "Subject distribution: %d unique subjects, Shannon entropy = %.3f",
        len(counts), entropy,
    )

    counts.to_csv(TABLES_DIR / "subject_distribution.csv", index=False)

    # Save entropy alongside label-level summary
    entropy_df = pd.DataFrame([{
        "n_unique_subjects": len(counts),
        "shannon_entropy_bits": round(entropy, 4),
        "max_entropy_bits": round(np.log2(len(counts)), 4),
    }])
    entropy_df.to_csv(TABLES_DIR / "subject_entropy.csv", index=False)

    # Bar plot (top 30)
    top = counts.head(30)
    fig, ax = plt.subplots(figsize=(12, max(6, len(top) * 0.35)))
    ax.barh(top["subject"][::-1], top["count"][::-1], color="#4C72B0")
    ax.set_xlabel("Count")
    ax.set_title(f"Top {len(top)} Primary Subjects  (H = {entropy:.2f} bits)")
    plt.tight_layout()
    fig.savefig(FIGURES_DIR / "subject_frequency.png", dpi=200)
    plt.close(fig)

    logger.info("Saved subject_distribution.csv, subject_entropy.csv + subject_frequency.png")
    return counts, entropy


# ── 3.3  Rare class detection ───────────────────────────────────────

def rare_class_detection(df: pd.DataFrame) -> pd.DataFrame:
    labeled = df.loc[_labeled_mask(df), "primary_subject"]
    counts = labeled.value_counts().reset_index()
    counts.columns = ["subject", "count"]

    rows = []
    for threshold in [100, 500]:
        rare = counts[counts["count"] < threshold]
        rows.append({
            "threshold": f"< {threshold}",
            "n_rare_subjects": len(rare),
            "total_records_in_rare": int(rare["count"].sum()),
            "pct_of_labeled": round(rare["count"].sum() / labeled.shape[0] * 100, 2),
            "subjects": ", ".join(rare["subject"].head(20).tolist())
            + ("…" if len(rare) > 20 else ""),
        })

    result = pd.DataFrame(rows)
    result.to_csv(TABLES_DIR / "rare_subjects.csv", index=False)
    logger.info("Saved rare_subjects.csv")
    return result


# ── 4.1  Missingness by year ────────────────────────────────────────

def missingness_by_year(df: pd.DataFrame) -> pd.DataFrame:
    records = []
    for year, grp in df.groupby("year_created"):
        n = len(grp)
        missing = (~_labeled_mask(grp)).sum()
        records.append({
            "year": year,
            "n": n,
            "missing": int(missing),
            "missing_rate": round(missing / n, 4),
        })

    result = pd.DataFrame(records).sort_values("year")
    result.to_csv(TABLES_DIR / "missing_by_year.csv", index=False)

    # Plot
    fig, ax = plt.subplots(figsize=(12, 5))
    ax.bar(
        result["year"].astype(str),
        result["missing_rate"] * 100,
        color="#DD8452",
    )
    ax.set_xlabel("Year")
    ax.set_ylabel("% Missing Subject Label")
    ax.set_title("Subject Label Missingness by Year")
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    fig.savefig(FIGURES_DIR / "missing_subject_by_year.png", dpi=200)
    plt.close(fig)

    logger.info("Saved missing_by_year.csv + missing_subject_by_year.png")
    return result


# ── 4.2  Missingness by schema ──────────────────────────────────────

def missingness_by_schema(df: pd.DataFrame) -> pd.DataFrame:
    col = "registration_supplement"
    if col not in df.columns:
        logger.warning("Column '%s' not found — skipping.", col)
        return pd.DataFrame()

    records = []
    for schema, grp in df.groupby(df[col].fillna("(unknown)")):
        n = len(grp)
        missing = (~_labeled_mask(grp)).sum()
        records.append({
            "schema": schema,
            "n": n,
            "missing": int(missing),
            "missing_rate": round(missing / n, 4),
        })

    result = (
        pd.DataFrame(records)
        .sort_values("n", ascending=False)
    )
    result.to_csv(TABLES_DIR / "missing_by_schema.csv", index=False)
    logger.info("Saved missing_by_schema.csv")
    return result


# ── 4.3  Missingness vs text length ─────────────────────────────────

def missingness_vs_text_length(df: pd.DataFrame) -> pd.DataFrame:
    mask = _labeled_mask(df)
    labeled = df[mask]
    unlabeled = df[~mask]

    text_cols = [
        ("title_word_count", "title"),
        ("description_word_count", "description"),
        ("responses_word_count", "responses"),
        ("combined_word_count", "combined"),
    ]

    rows = []
    for col, label in text_cols:
        if col not in df.columns:
            continue
        rows.append({
            "text_field": label,
            "labeled_median_wc": labeled[col].median(),
            "unlabeled_median_wc": unlabeled[col].median(),
            "labeled_mean_wc": round(labeled[col].mean(), 1),
            "unlabeled_mean_wc": round(unlabeled[col].mean(), 1),
            "labeled_pct_empty": round((labeled[col] == 0).mean() * 100, 2),
            "unlabeled_pct_empty": round((unlabeled[col] == 0).mean() * 100, 2),
        })

    result = pd.DataFrame(rows)
    result.to_csv(TABLES_DIR / "text_length_missingness_comparison.csv", index=False)
    logger.info("Saved text_length_missingness_comparison.csv")
    return result



# ── Option C: Hierarchy label diagnostics ────────────────────────────

def sbs_l2_distribution(df: pd.DataFrame) -> pd.DataFrame:
    """Distribution of subject_l2 conditional on subject_l1 == 'Social and Behavioral Sciences'."""
    if "subject_l1" not in df.columns or "subject_l2" not in df.columns:
        logger.warning("Hierarchy columns not found — skipping sbs_l2_distribution.")
        return pd.DataFrame()

    sbs = df[df["subject_l1"] == "Social and Behavioral Sciences"]
    counts = sbs["subject_l2"].value_counts(dropna=False).reset_index()
    counts.columns = ["subject_l2", "count"]
    counts["proportion"] = (counts["count"] / counts["count"].sum()).round(6)
    counts.to_csv(TABLES_DIR / "sbs_l2_distribution.csv", index=False)
    logger.info("Saved sbs_l2_distribution.csv (%d SBS rows)", len(sbs))
    return counts


def psychology_subdiscipline_distribution(df: pd.DataFrame) -> pd.DataFrame:
    """Distribution of psychology_subdiscipline (non-null rows)."""
    if "psychology_subdiscipline" not in df.columns:
        logger.warning("Column 'psychology_subdiscipline' not found — skipping.")
        return pd.DataFrame()

    sub = df["psychology_subdiscipline"].dropna()
    counts = sub.value_counts().reset_index()
    counts.columns = ["psychology_subdiscipline", "count"]
    counts["proportion"] = (counts["count"] / counts["count"].sum()).round(6)
    counts.to_csv(LANDSCAPE_TABLES / "psychology_subdiscipline_distribution.csv", index=False)

    # Bar figure
    fig, ax = plt.subplots(figsize=(10, max(4, len(counts) * 0.35)))
    ax.barh(counts["psychology_subdiscipline"][::-1], counts["count"][::-1], color="#4C72B0")
    ax.set_xlabel("Count")
    ax.set_title("Psychology Subdiscipline Distribution")
    plt.tight_layout()
    fig.savefig(LANDSCAPE_FIGURES / "psychology_subdiscipline_distribution.png", dpi=200)
    plt.close(fig)

    logger.info("Saved psychology_subdiscipline_distribution.csv + figure (%d rows with subdiscipline)", len(sub))
    return counts


def psychology_subdiscipline_missingness_by_year(df: pd.DataFrame) -> pd.DataFrame:
    """Missingness of psychology_subdiscipline by year (among SBS+Psychology rows)."""
    if "psychology_subdiscipline" not in df.columns or "subject_l2" not in df.columns:
        logger.warning("Hierarchy columns not found — skipping psych subdiscipline missingness.")
        return pd.DataFrame()

    psych = df[
        (df["subject_l1"] == "Social and Behavioral Sciences") &
        (df["subject_l2"] == "Psychology")
    ].copy()

    if psych.empty:
        logger.warning("No Psychology rows found for missingness analysis.")
        return pd.DataFrame()

    records = []
    for year, grp in psych.groupby("year_created"):
        n = len(grp)
        missing = grp["psychology_subdiscipline"].isna().sum()
        records.append({
            "year": year,
            "n_psych_rows": n,
            "missing_subdiscipline": int(missing),
            "missing_rate": round(missing / n, 4),
        })

    result = pd.DataFrame(records).sort_values("year")
    result.to_csv(LANDSCAPE_TABLES / "psychology_subdiscipline_missingness_by_year.csv", index=False)
    logger.info("Saved psychology_subdiscipline_missingness_by_year.csv")
    return result


def _ca_trend(k: np.ndarray, n_year: np.ndarray, x: np.ndarray) -> tuple:
    """
    Cochran-Armitage linear-by-linear trend test (two-sided, normal
    approximation) -- same formula as src/stats/psych_chisquare.py's
    per-subdiscipline trend test, reimplemented locally since scripts in
    this repo are run standalone (`python3 src/...`) rather than as an
    installed package, so a cross-module import isn't available here.

    k: category counts per ordered timepoint; n_year: totals per timepoint;
    x: ordered scores for the timepoints (e.g. 0..span). Returns (z, p).
    """
    from scipy import stats as _stats
    p_bar = k.sum() / n_year.sum()
    xbar = (n_year * x).sum() / n_year.sum()
    T = (k * (x - xbar)).sum()
    var = p_bar * (1 - p_bar) * (n_year * (x - xbar) ** 2).sum()
    z = float(T / np.sqrt(var)) if var > 0 else 0.0
    p = float(2 * _stats.norm.sf(abs(z)))
    return z, p


def psychology_label_audit_window(df: pd.DataFrame, year_min: int = 2020, year_max: int = 2025) -> dict:
    """
    Is the psychology-subdiscipline exclusion rate different within the
    2020-2025 analytic window than the all-years figure reported in the
    Method (67,084 psych-tagged / 19,509 unlabelled / 29.1%)? And is the
    unlabelled share flat across the window, or trending?

    Psychology-subject tagging is negligible before 2020 (only 66 of the
    67,084 psych-tagged records fall outside the window), so the headline
    rate barely moves -- but the per-year breakdown (already computable from
    psychology_subdiscipline_missingness_by_year()) shows the unlabelled
    share declining across the window itself, not staying flat.
    """
    if "psychology_subdiscipline" not in df.columns or "subject_l2" not in df.columns:
        logger.warning("Hierarchy columns not found — skipping psych label audit.")
        return {}

    psych = df[
        (df["subject_l1"] == "Social and Behavioral Sciences") &
        (df["subject_l2"] == "Psychology")
    ].copy()
    psych["labelled"] = psych["psychology_subdiscipline"].notna()

    win = psych[psych["year_created"].between(year_min, year_max)]

    n_all = len(psych)
    unlabelled_all = int((~psych["labelled"]).sum())
    n_win = len(win)
    unlabelled_win = int((~win["labelled"]).sum())

    by_year = (
        win.groupby("year_created")["labelled"]
        .agg(n="size", labelled="sum")
        .reset_index()
        .sort_values("year_created")
    )
    by_year["unlabelled"] = by_year["n"] - by_year["labelled"]
    by_year["unlabelled_rate"] = by_year["unlabelled"] / by_year["n"]

    x = (by_year["year_created"] - year_min).values.astype(float)
    k = by_year["unlabelled"].values.astype(float)
    n_year = by_year["n"].values.astype(float)
    ca_z, ca_p = _ca_trend(k, n_year, x)

    verdict = pd.DataFrame([{
        "n_all_years": n_all,
        "unlabelled_all_years": unlabelled_all,
        "unlabelled_pct_all_years": unlabelled_all / n_all,
        "n_window": n_win,
        "unlabelled_window": unlabelled_win,
        "unlabelled_pct_window": unlabelled_win / n_win,
        "unlabelled_rate_first_year": float(by_year["unlabelled_rate"].iloc[0]),
        "unlabelled_rate_last_year": float(by_year["unlabelled_rate"].iloc[-1]),
        "ca_z": ca_z,
        "ca_p": ca_p,
    }])
    verdict.to_csv(TABLES_DIR / "psych_label_audit_verdict.csv", index=False)

    wordcount_by_label = (
        win.groupby("labelled")["responses_word_count"].median().rename("median_word_count").reset_index()
    )
    wordcount_by_label.to_csv(TABLES_DIR / "psych_label_audit_proxies_wordcount.csv", index=False)

    template_by_label = pd.crosstab(win["labelled"], win["registration_supplement"], normalize="index")
    template_by_label.to_csv(TABLES_DIR / "psych_label_audit_proxies_template.csv")

    logger.info(
        "Psych label audit: all-years unlabelled %d/%d (%.2f%%); window unlabelled %d/%d (%.2f%%); "
        "window trend %.1f%%→%.1f%% (CA z=%.2f, p=%.4f)",
        unlabelled_all, n_all, 100 * unlabelled_all / n_all,
        unlabelled_win, n_win, 100 * unlabelled_win / n_win,
        100 * by_year["unlabelled_rate"].iloc[0], 100 * by_year["unlabelled_rate"].iloc[-1],
        ca_z, ca_p,
    )

    return {
        "verdict": verdict,
        "by_year": by_year,
        "wordcount_by_label": wordcount_by_label,
        "template_by_label": template_by_label,
    }


def psychology_subdiscipline_missingness_by_schema(df: pd.DataFrame) -> pd.DataFrame:
    """Missingness of psychology_subdiscipline by schema, among SBS+Psychology rows."""
    if "psychology_subdiscipline" not in df.columns or "subject_l2" not in df.columns:
        return pd.DataFrame()

    psych = df[
        (df["subject_l1"] == "Social and Behavioral Sciences") &
        (df["subject_l2"] == "Psychology")
    ].copy()

    if psych.empty:
        return pd.DataFrame()

    col = "registration_supplement"
    records = []
    for schema, grp in psych.groupby(psych[col].fillna("(unknown)")):
        n = len(grp)
        missing = grp["psychology_subdiscipline"].isna().sum()
        records.append({
            "schema": schema,
            "n_psych_rows": n,
            "missing_subdiscipline": int(missing),
            "missing_rate": round(missing / n, 4),
        })

    result = pd.DataFrame(records).sort_values("n_psych_rows", ascending=False)
    result.to_csv(LANDSCAPE_TABLES / "psychology_subdiscipline_missingness_by_schema.csv", index=False)
    logger.info("Saved psychology_subdiscipline_missingness_by_schema.csv")
    return result


# ── Orchestrator ─────────────────────────────────────────────────────

def run(df: pd.DataFrame) -> dict:
    """Run all label diagnostic and missingness steps."""
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    LANDSCAPE_TABLES.mkdir(parents=True, exist_ok=True)
    LANDSCAPE_FIGURES.mkdir(parents=True, exist_ok=True)

    results = {}
    results["coverage"] = label_coverage(df)
    dist, entropy = subject_distribution(df)
    results["distribution"] = dist
    results["entropy"] = entropy
    results["rare"] = rare_class_detection(df)
    results["missing_year"] = missingness_by_year(df)
    results["missing_schema"] = missingness_by_schema(df)
    results["missing_text"] = missingness_vs_text_length(df)
    # Option C hierarchy diagnostics
    results["sbs_l2"] = sbs_l2_distribution(df)
    results["psych_subdiscipline"] = psychology_subdiscipline_distribution(df)
    results["psych_subdiscipline_missing_year"] = psychology_subdiscipline_missingness_by_year(df)
    results["psych_subdiscipline_missing_schema"] = psychology_subdiscipline_missingness_by_schema(df)
    results["psych_label_audit"] = psychology_label_audit_window(df)
    return results


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
    )
    CLEAN_PATH = PROJECT_ROOT / "data" / "processed" / "preregistrations_clean.parquet"
    df = pd.read_parquet(CLEAN_PATH)
    run(df)
