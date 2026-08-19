"""
prep_psych_chisquare.py — Chi-square independence tests for the Psychology landscape
=====================================================================================
Two tests:
  1. Year × Subdiscipline (2020–2025): are subdiscipline proportions stable over time?
  2. Subdiscipline × Template: do subdisciplines differ in registration template use?

For each test the module outputs:
  - Observed-counts contingency table (CSV)
  - Chi-square summary (chi2, p, df, Cramér's V)  (CSV)
  - Standardised-residuals heatmap  (PNG)
"""
from __future__ import annotations

import pathlib
import logging

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats

logger = logging.getLogger(__name__)

PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
TABLES_DIR = PROJECT_ROOT / "reports" / "tables" / "landscape"
FIGURES_DIR = PROJECT_ROOT / "reports" / "figures" / "landscape"

sns.set_theme(style="whitegrid", palette="muted", font_scale=1.1)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _psych_labeled(df: pd.DataFrame) -> pd.DataFrame:
    mask = (
        (df.get("subject_l1", pd.Series("", index=df.index)) == "Social and Behavioral Sciences")
        & (df.get("subject_l2", pd.Series("", index=df.index)) == "Psychology")
        & df["psychology_subdiscipline"].notna()
    )
    return df[mask].copy()


def _cramers_v(chi2: float, n: int, k: int, r: int) -> float:
    """Cramér's V with bias-corrected formula (Bergsma 2013)."""
    phi2 = chi2 / n
    k_tilde = k - (k - 1) ** 2 / (n - 1)
    r_tilde = r - (r - 1) ** 2 / (n - 1)
    phi2_tilde = max(0.0, phi2 - (k - 1) * (r - 1) / (n - 1))
    denom = min(k_tilde - 1, r_tilde - 1)
    if denom <= 0:
        return 0.0
    return float(np.sqrt(phi2_tilde / denom))


def _std_residuals(observed: np.ndarray, expected: np.ndarray) -> np.ndarray:
    """Standardised Pearson residuals: (O - E) / sqrt(E)."""
    with np.errstate(divide="ignore", invalid="ignore"):
        res = np.where(expected > 0, (observed - expected) / np.sqrt(expected), 0.0)
    return res


def _residual_heatmap(
    residuals: np.ndarray,
    row_labels: list[str],
    col_labels: list[str],
    title: str,
    path: pathlib.Path,
    figsize: tuple[float, float] = (12, 7),
) -> None:
    """Save a standardised-residuals heatmap."""
    fig, ax = plt.subplots(figsize=figsize)
    vmax = max(3.0, float(np.abs(residuals).max()))
    sns.heatmap(
        residuals,
        xticklabels=col_labels,
        yticklabels=row_labels,
        cmap="RdBu_r",
        center=0,
        vmin=-vmax,
        vmax=vmax,
        annot=True,
        fmt=".1f",
        linewidths=0.4,
        cbar_kws={"label": "Standardised residual"},
        ax=ax,
    )
    ax.set_title(title)
    plt.xticks(rotation=45, ha="right")
    plt.yticks(rotation=0)
    plt.tight_layout()
    fig.savefig(path, dpi=200)
    plt.close(fig)
    logger.info("Saved %s", path.name)


# ── Test 1: Year × Subdiscipline (2020–2025) ─────────────────────────────────

def chisq_year_by_category(
    df: pd.DataFrame,
    year_min: int = 2020,
    year_max: int = 2025,
    min_total: int = 100,
) -> dict:
    """
    Chi-square test of independence: year_created × psychology_subdiscipline.

    Rows with year outside [year_min, year_max] and subdisciplines with fewer
    than min_total labeled rows across the window are excluded.

    Returns a dict with keys: chi2, p, dof, cramers_v, n, n_cells_low_expected.
    """
    psych = _psych_labeled(df)
    scope = psych[
        (psych["year_created"] >= year_min) & (psych["year_created"] <= year_max)
    ].copy()

    if scope.empty:
        logger.warning("No labeled Psychology rows in %d–%d.", year_min, year_max)
        return {}

    # Drop rare subdisciplines
    sub_totals = scope["psychology_subdiscipline"].value_counts()
    keep_subs = sub_totals[sub_totals >= min_total].index
    n_dropped = int((sub_totals < min_total).sum())
    if n_dropped:
        logger.info(
            "Dropping %d subdiscipline(s) with < %d total rows: %s",
            n_dropped,
            min_total,
            list(sub_totals[sub_totals < min_total].index),
        )
    scope = scope[scope["psychology_subdiscipline"].isin(keep_subs)]

    # Build contingency table: rows=subdiscipline, cols=year
    ct = (
        scope.groupby(["psychology_subdiscipline", "year_created"])
        .size()
        .unstack(fill_value=0)
    )
    ct.index.name = "psychology_subdiscipline"

    observed = ct.values.astype(float)
    chi2_val, p_val, dof, expected = stats.chi2_contingency(observed, correction=False)
    n = int(observed.sum())
    r, k = observed.shape
    v = _cramers_v(chi2_val, n, k, r)

    n_low = int((expected < 5).sum())
    pct_low = round(n_low / expected.size * 100, 1)

    summary = pd.DataFrame([{
        "test": "Year × Subdiscipline",
        "year_range": f"{year_min}–{year_max}",
        "n_subdisciplines": r,
        "n_years": k,
        "n_observations": n,
        "chi2": round(chi2_val, 3),
        "p_value": float(f"{p_val:.2e}"),
        "dof": dof,
        "cramers_v": round(v, 4),
        "n_cells_expected_lt5": n_low,
        "pct_cells_expected_lt5": pct_low,
        "min_total_threshold": min_total,
    }])
    summary.to_csv(TABLES_DIR / "psych_chisq_year_by_category.csv", index=False)
    ct.to_csv(TABLES_DIR / "psych_chisq_year_by_category_counts.csv")

    logger.info(
        "Year × Category  χ²(%.0f)=%.2f, p=%s, V=%.4f  (n=%d, %d cells E<5)",
        dof, chi2_val, p_val, v, n, n_low,
    )

    # Standardised residuals heatmap (subdiscipline × year)
    res = _std_residuals(observed, expected)
    _residual_heatmap(
        res,
        row_labels=list(ct.index),
        col_labels=[str(y) for y in ct.columns],
        title=f"Standardised Residuals: Year × Subdiscipline ({year_min}–{year_max})",
        path=FIGURES_DIR / "psych_chisq_year_by_category_residuals.png",
        figsize=(10, max(6, r * 0.45)),
    )

    return {
        "chi2": chi2_val,
        "p": p_val,
        "dof": dof,
        "cramers_v": v,
        "n": n,
        "n_cells_low_expected": n_low,
        "ct": ct,
        "summary": summary,
    }


# ── Test 2: Subdiscipline × Template ─────────────────────────────────────────

def chisq_category_by_template(
    df: pd.DataFrame,
    year_min: int = 2020,
    year_max: int = 2025,
    top_templates: int = 8,
    min_sub_total: int = 100,
) -> dict:
    """
    Chi-square test of independence: psychology_subdiscipline × registration_supplement.

    Analysis is restricted to:
      - rows with year in [year_min, year_max], matching chisq_year_by_category
        and trend_tests so all three Psychology-landscape tests share one window
      - the top_templates most common templates within that window
      - subdisciplines with >= min_sub_total labeled rows within that window

    Returns a dict with chi2, p, dof, cramers_v, n, n_cells_low_expected.
    """
    psych = _psych_labeled(df)
    psych = psych[
        (psych["year_created"] >= year_min) & (psych["year_created"] <= year_max)
    ].copy()
    schema_col = "registration_supplement"
    if schema_col not in psych.columns:
        logger.error("Column '%s' not found.", schema_col)
        return {}

    psych[schema_col] = psych[schema_col].fillna("(none)")

    # Keep top templates
    top_tpl = (
        psych[schema_col].value_counts().head(top_templates).index.tolist()
    )
    # Keep subdisciplines with enough data
    sub_totals = psych["psychology_subdiscipline"].value_counts()
    keep_subs = sub_totals[sub_totals >= min_sub_total].index

    n_dropped_subs = int((sub_totals < min_sub_total).sum())
    if n_dropped_subs:
        logger.info(
            "Dropping %d subdiscipline(s) with < %d rows: %s",
            n_dropped_subs,
            min_sub_total,
            list(sub_totals[sub_totals < min_sub_total].index),
        )

    scope = psych[
        psych["psychology_subdiscipline"].isin(keep_subs)
        & psych[schema_col].isin(top_tpl)
    ]

    if scope.empty:
        logger.warning("No rows remain after filtering for category × template test.")
        return {}

    # Contingency table: rows=subdiscipline, cols=template
    ct = (
        scope.groupby(["psychology_subdiscipline", schema_col])
        .size()
        .unstack(fill_value=0)
    )
    # Reorder columns by overall frequency
    ct = ct[top_tpl]
    ct.index.name = "psychology_subdiscipline"

    observed = ct.values.astype(float)
    chi2_val, p_val, dof, expected = stats.chi2_contingency(observed, correction=False)
    n = int(observed.sum())
    r, k = observed.shape
    v = _cramers_v(chi2_val, n, k, r)

    n_low = int((expected < 5).sum())
    pct_low = round(n_low / expected.size * 100, 1)

    summary = pd.DataFrame([{
        "test": "Subdiscipline × Template",
        "year_range": f"{year_min}–{year_max}",
        "n_subdisciplines": r,
        "n_templates": k,
        "n_observations": n,
        "chi2": round(chi2_val, 3),
        "p_value": float(f"{p_val:.2e}"),
        "dof": dof,
        "cramers_v": round(v, 4),
        "n_cells_expected_lt5": n_low,
        "pct_cells_expected_lt5": pct_low,
        "min_sub_total_threshold": min_sub_total,
        "top_templates_k": top_templates,
    }])
    summary.to_csv(TABLES_DIR / "psych_chisq_category_by_template.csv", index=False)
    ct.to_csv(TABLES_DIR / "psych_chisq_category_by_template_counts.csv")

    logger.info(
        "Category × Template  χ²(%.0f)=%.2f, p=%s, V=%.4f  (n=%d, %d cells E<5)",
        dof, chi2_val, p_val, v, n, n_low,
    )

    # Shorten template labels for readability in the heatmap
    short_labels = _shorten_template_labels(top_tpl)

    res = _std_residuals(observed, expected)
    _residual_heatmap(
        res,
        row_labels=list(ct.index),
        col_labels=short_labels,
        title="Standardised Residuals: Subdiscipline × Registration Template",
        path=FIGURES_DIR / "psych_chisq_category_by_template_residuals.png",
        figsize=(max(10, k * 1.4), max(6, r * 0.45)),
    )

    return {
        "chi2": chi2_val,
        "p": p_val,
        "dof": dof,
        "cramers_v": v,
        "n": n,
        "n_cells_low_expected": n_low,
        "ct": ct,
        "summary": summary,
    }


# ── Test 1b: Per-subdiscipline temporal trend (Cochran-Armitage) ─────────────

def _benjamini_hochberg(pvals: np.ndarray) -> np.ndarray:
    """Benjamini-Hochberg FDR-adjusted q-values."""
    p = np.asarray(pvals, dtype=float)
    m = p.size
    order = np.argsort(p)
    ranked = p[order] * m / (np.arange(m) + 1)
    # enforce monotonicity from the largest p downward
    q_sorted = np.minimum.accumulate(ranked[::-1])[::-1]
    q = np.empty_like(q_sorted)
    q[order] = np.clip(q_sorted, 0, 1)
    return q


def _ca_trend(k: np.ndarray, n_year: np.ndarray, x: np.ndarray) -> tuple[float, float]:
    """
    Cochran-Armitage linear-by-linear trend test (two-sided, normal approximation).

    k: category counts per ordered timepoint; n_year: totals per timepoint
    (same denominator the category's share is computed against); x: ordered
    scores for the timepoints (e.g. 0..span). Returns (z, p).
    """
    p_bar = k.sum() / n_year.sum()
    xbar = (n_year * x).sum() / n_year.sum()
    T = (k * (x - xbar)).sum()
    var = p_bar * (1 - p_bar) * (n_year * (x - xbar) ** 2).sum()
    z = float(T / np.sqrt(var)) if var > 0 else 0.0
    p = float(2 * stats.norm.sf(abs(z)))
    return z, p


def trend_tests(
    df: pd.DataFrame,
    year_min: int = 2020,
    year_max: int = 2025,
    min_total: int = 100,
) -> dict:
    """
    Per-subdiscipline temporal trend analysis on the labeled Psychology subset.

    The omnibus Year × Subdiscipline chi-square treats `year` as nominal and
    averages one directional shift across many flat categories, so it understates
    monotonic trends. This routine isolates the per-subdiscipline signal:

      - Cochran-Armitage linear-by-linear trend test (year as ordered score),
        with Benjamini-Hochberg FDR correction across subdisciplines.
      - Absolute-vs-relative growth decomposition: each subdiscipline's fold
        change vs the whole labeled-Psychology subset's fold change, so a rising
        *share* can be distinguished from merely tracking field-wide growth.

    Output: reports/tables/psych_subdiscipline_trends.csv (one row per subdiscipline).
    """
    psych = _psych_labeled(df)
    scope = psych[
        (psych["year_created"] >= year_min) & (psych["year_created"] <= year_max)
    ].copy()
    if scope.empty:
        logger.warning("No labeled Psychology rows in %d–%d.", year_min, year_max)
        return {}

    sub_totals = scope["psychology_subdiscipline"].value_counts()
    keep_subs = sub_totals[sub_totals >= min_total].index
    scope = scope[scope["psychology_subdiscipline"].isin(keep_subs)]

    ct = (
        scope.groupby(["psychology_subdiscipline", "year_created"])
        .size()
        .unstack(fill_value=0)
    )
    ct = ct.reindex(columns=range(year_min, year_max + 1), fill_value=0)

    years = np.array(ct.columns, dtype=float)
    x = years - year_min                      # ordered scores 0..(span)
    n_year = ct.values.sum(axis=0).astype(float)   # labeled-Psych total per year
    overall_fold = float(n_year[-1] / n_year[0]) if n_year[0] > 0 else np.nan

    rows = []
    for sub in ct.index:
        k = ct.loc[sub].values.astype(float)   # counts per year for this subdiscipline
        n_total = k.sum()
        z, p = _ca_trend(k, n_year, x)

        share = k / n_year
        share_2020, share_2025 = float(share[0]), float(share[-1])
        count_fold = float(k[-1] / k[0]) if k[0] > 0 else np.nan
        rel_to_field = float(count_fold / overall_fold) if overall_fold and not np.isnan(count_fold) else np.nan

        rows.append({
            "psychology_subdiscipline": sub,
            "n_total": int(n_total),
            "share_2020": round(share_2020, 4),
            "share_2025": round(share_2025, 4),
            "share_change_pp": round((share_2025 - share_2020) * 100, 2),
            "count_2020": int(k[0]),
            "count_2025": int(k[-1]),
            "count_fold": round(count_fold, 2) if not np.isnan(count_fold) else np.nan,
            "field_fold": round(overall_fold, 2),
            "growth_vs_field": round(rel_to_field, 2) if not np.isnan(rel_to_field) else np.nan,
            "ca_z": round(z, 2),
            "ca_p": float(f"{p:.2e}"),
        })

    out = pd.DataFrame(rows)
    out["ca_q_bh"] = _benjamini_hochberg(out["ca_p"].values)
    out["ca_q_bh"] = out["ca_q_bh"].map(lambda v: float(f"{v:.2e}"))
    out = out.sort_values("ca_z", ascending=False).reset_index(drop=True)
    out.to_csv(TABLES_DIR / "psych_subdiscipline_trends.csv", index=False)

    rising = out[(out["ca_z"] > 0) & (out["ca_q_bh"] < 0.05)]
    falling = out[(out["ca_z"] < 0) & (out["ca_q_bh"] < 0.05)]
    logger.info(
        "Trend tests: %d subdisciplines, field grew %.2fx (%d→%d). "
        "Significant rising: %s | falling: %s",
        len(out), overall_fold, int(n_year[0]), int(n_year[-1]),
        list(rising["psychology_subdiscipline"]),
        list(falling["psychology_subdiscipline"]),
    )
    return {"trends": out, "overall_fold": overall_fold}


def _shorten_template_labels(labels: list[str], max_len: int = 30) -> list[str]:
    abbrev = {
        "OSF Preregistration": "OSF Prereg",
        "Preregistration Template from AsPredicted.org": "AsPredicted",
        "Open-Ended Registration": "Open-Ended",
        "Secondary Data Preregistration": "Secondary Data",
        "OSF-Standard Pre-Data Collection Registration": "OSF-Standard",
        "Pre-Registration in Social Psychology (van 't Veer & Giner-Sorolla, 2016): Pre-Registration": "van 't Veer & G-S",
        "Generalized Systematic Review Registration": "Systematic Review",
        "Qualitative Preregistration": "Qualitative",
        "Registered Report Protocol Preregistration": "Registered Report",
        "Character Lab Short-Form Registration": "Char Lab Short",
    }
    out = []
    for lbl in labels:
        short = abbrev.get(lbl, lbl)
        if len(short) > max_len:
            short = short[:max_len - 1] + "…"
        out.append(short)
    return out


# ── Orchestrator ──────────────────────────────────────────────────────────────

def run(df: pd.DataFrame) -> dict:
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)

    results = {}
    results["year_by_category"] = chisq_year_by_category(df)
    results["trend_tests"] = trend_tests(df)
    results["category_by_template"] = chisq_category_by_template(df)
    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-8s  %(message)s")
    CLEAN_PATH = PROJECT_ROOT / "data" / "processed" / "preregistrations_clean.parquet"
    _df = pd.read_parquet(CLEAN_PATH)
    run(_df)
