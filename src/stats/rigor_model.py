"""
prep_rigor_model.py — Does the thoroughness signal survive controls?
====================================================================
The pilot showed two candidate findings:
  * RQ3 (temporal): mean thoroughness index rose ~11% 2020->2025, BUT word
    count rose 34% and index~log(words) r=0.74, so the trend may be length
    inflation.
  * RQ4 (subdiscipline gap): established basic-science subfields scored higher
    than newly-adopting applied/clinical ones.

This script is the WEEK-2 SIGNAL GATE. Before any hand-coding is worth doing,
we must know whether these effects survive controlling for document length and
template. We fit the planned model

    thoroughness_index ~ C(year) + C(subdiscipline) + C(template) + log(word_count)

as a sequence of NESTED OLS models so the *incremental* contribution of each
block (beyond length) is explicit:

    M0: index ~ log_wc                      (length only — the confound)
    M1: + C(template)                       (template culture)
    M2: + year_c (continuous, centred)      (the temporal trend, net of above)
    M3: + C(subdiscipline)                  (the subdiscipline gap, net of above)

Decision rule (states in the dissertation):
  * If the year slope in M2/M3 is significant and non-trivial -> RQ3 survives.
  * If the subdiscipline block adds significant R^2 in M3 (incremental F-test)
    and the ranking still tracks the diffusion direction -> RQ4 survives.
  * If both collapse to ~0 once log_wc enters -> the measure is mostly a length
    proxy; fall back to Spine A (landscape + diffusion) and report this honestly.

Scope (from plans/dissertation/plan.md §4): the index is only valid for
quantitative / structured templates, so we restrict to:
    OSF Preregistration, AsPredicted, van 't Veer & Giner-Sorolla,
    Secondary Data Preregistration  (~37.7k psychology records).
Open-Ended / Qualitative / OSF-Standard / Registered Report Protocol are
excluded (the measure is invalid there: many score ~0 words / ~0 index).

Outputs
-------
* reports/tables/rigor_model_coefficients.csv  — full M3 coef table (b, SE, p, CI)
* reports/tables/rigor_model_nested.csv         — nested-model fit + ΔR² + F-tests
* reports/tables/rigor_model_subdiscipline.csv  — subdiscipline effects net of controls, ranked
* reports/tables/rigor_model_verdict.csv        — machine-readable pass/fail of the gate
"""
from __future__ import annotations

import pathlib
import logging

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from scipy import stats as spstats
from statsmodels.stats.anova import anova_lm

logger = logging.getLogger(__name__)

PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
TABLES_DIR = PROJECT_ROOT / "reports" / "tables" / "rigor"
FEATURES_PATH = TABLES_DIR / "rigor_features.parquet"

YEAR_MIN, YEAR_MAX = 2020, 2025

# Quantitative / structured templates the measure is valid for (see module docstring).
# Match on a substring so the long official names need not be reproduced exactly.
QUANT_TEMPLATE_KEYS = {
    "OSF Preregistration": "OSF Prereg",
    "AsPredicted": "AsPredicted",
    "van 't Veer": "van 't Veer",
    "Secondary Data Preregistration": "Secondary Data",
}

# Subdisciplines with at least this many in-scope records get their own dummy;
# rarer ones are pooled into "Other" so the design matrix is stable.
MIN_SUBDISC_N = 200


def _short_template(name: str) -> str | None:
    if not isinstance(name, str):
        return None
    for key, short in QUANT_TEMPLATE_KEYS.items():
        if key in name:
            return short
    return None


def build_design(features: pd.DataFrame) -> pd.DataFrame:
    """Filter to the in-scope analysis sample and build model columns."""
    df = features[features["psychology_subdiscipline"].notna()].copy()
    df = df[df["year_created"].between(YEAR_MIN, YEAR_MAX)]

    df["template"] = df["registration_supplement"].map(_short_template)
    df = df[df["template"].notna()]  # quantitative/structured templates only

    df = df[df["responses_word_count"].astype(float) > 0]
    df["log_wc"] = np.log1p(df["responses_word_count"].astype(float))
    df["year_c"] = df["year_created"].astype(float) - YEAR_MIN  # 0..5, slope = per-year change

    # Pool rare subdisciplines
    counts = df["psychology_subdiscipline"].value_counts()
    keep = counts[counts >= MIN_SUBDISC_N].index
    df["subdisc"] = np.where(
        df["psychology_subdiscipline"].isin(keep),
        df["psychology_subdiscipline"], "Other (pooled)",
    )

    # Reference level = most common subdiscipline (interpretable baseline)
    ref_sub = df["subdisc"].value_counts().idxmax()
    df["subdisc"] = pd.Categorical(
        df["subdisc"],
        categories=[ref_sub] + [c for c in df["subdisc"].unique() if c != ref_sub],
    )
    ref_tpl = df["template"].value_counts().idxmax()
    df["template"] = pd.Categorical(
        df["template"],
        categories=[ref_tpl] + [c for c in df["template"].unique() if c != ref_tpl],
    )

    df["y"] = df["thoroughness_index"].astype(float)
    logger.info(
        "Analysis sample: %d records, %d subdisciplines (ref=%s), templates=%s, years %d-%d.",
        len(df), df["subdisc"].nunique(), ref_sub,
        list(df["template"].cat.categories), YEAR_MIN, YEAR_MAX,
    )
    return df


# Continuous study variables for the descriptives/correlation table (Table 5);
# categorical controls (template, subdiscipline) aren't part of a means/SDs/
# correlations table. Order matches the nested model's build-up.
CORR_VARS = {
    "y": "Thoroughness Index",
    "responses_word_count": "Word Count",
    "log_wc": "Log Word Count",
    "year_c": "Year (Centered)",
}


def _pearson_ci(r: float, n: int, alpha: float = 0.05) -> tuple[float, float]:
    """Fisher r-to-z 95% CI for a Pearson correlation."""
    z = np.arctanh(np.clip(r, -0.999999, 0.999999))
    se = 1 / np.sqrt(n - 3)
    z_crit = spstats.norm.ppf(1 - alpha / 2)
    return float(np.tanh(z - z_crit * se)), float(np.tanh(z + z_crit * se))


def correlation_table(df: pd.DataFrame) -> pd.DataFrame:
    """
    Means, SDs, and pairwise Pearson correlations (with 95% CI) among the
    continuous study variables, on the same analysis sample as the M3 model
    (build_design() output: psychology-labelled, 2020-2025, quantitative/
    structured templates, non-zero word count). Companion descriptive table
    to the nested regression.
    """
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    cols = list(CORR_VARS.keys())
    data = df[cols].astype(float)
    n = len(data)

    desc = pd.DataFrame({
        "variable": [CORR_VARS[c] for c in cols],
        "M": data.mean().round(3).values,
        "SD": data.std().round(3).values,
        "n": n,
    })
    desc.to_csv(TABLES_DIR / "rigor_correlation_descriptives.csv", index=False)

    rows = []
    for i, c1 in enumerate(cols):
        for c2 in cols[i + 1:]:
            r, p = spstats.pearsonr(data[c1], data[c2])
            lo, hi = _pearson_ci(r, n)
            rows.append({
                "var1": CORR_VARS[c1], "var2": CORR_VARS[c2],
                "r": round(r, 4), "p_value": float(p),
                "ci_low": round(lo, 4), "ci_high": round(hi, 4), "n": n,
            })
    corr = pd.DataFrame(rows)
    corr.to_csv(TABLES_DIR / "rigor_correlations.csv", index=False)
    logger.info("Saved rigor_correlation_descriptives.csv + rigor_correlations.csv (n=%d)", n)
    return corr


def subdiscipline_descriptives(df: pd.DataFrame) -> pd.DataFrame:
    """
    Raw (unadjusted) N/M/SD of the thoroughness index by subdiscipline, on the
    same analysis sample as the nested regression (build_design() output:
    psychology-labelled, 2020-2025, quantitative/structured templates,
    non-zero word count). Uses the original, unpooled subdiscipline labels
    (not the "Other (pooled)" grouping build_design() creates for the
    regression's design matrix), so every subdiscipline present in this
    sample gets its own row. Descriptive companion to Table 6, not an input
    to it -- Table 4 should report means from the same N as the regression,
    not the larger, unrestricted landscape sample (Figure 1 / Table 1-3).
    """
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    desc = (
        df.groupby("psychology_subdiscipline", observed=True)["y"]
        .agg(N="count", M="mean", SD="std")
        .sort_values("M", ascending=False)
        .reset_index()
    )
    # Full precision on disk -- table4.R does the single display-rounding
    # pass to 2dp. Pre-rounding here to 3dp and letting R round again to 2dp
    # is double rounding: e.g. 4.185 isn't exactly representable as a double
    # (it's actually 4.18499999999999960920), so a second rounding pass reads
    # it as just under the boundary and rounds down to 4.18 instead of 4.19.
    desc.to_csv(TABLES_DIR / "rigor_summary_by_subdiscipline_restricted.csv", index=False)
    logger.info(
        "Saved rigor_summary_by_subdiscipline_restricted.csv (n=%d, %d subdisciplines)",
        len(df), len(desc),
    )
    return desc


def yearly_descriptives(df: pd.DataFrame) -> pd.DataFrame:
    """
    Raw (unadjusted) N/mean thoroughness index/mean word count by year, on the
    same analysis sample as the nested regression (build_design() output).
    Descriptive companion to Figure 4 -- the year-by-year trend Figure 4 plots
    must come from the same N=37,206 sample the "year effect is non-significant
    net of controls" claim is about, not the larger, unrestricted landscape
    sample (rigor_features.py::summarise(), N=47,524) Figure 4 previously read.
    Full precision on disk -- figure4.R does the only display-rounding pass.
    """
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    desc = (
        df.groupby("year_created", observed=True)
        .agg(N=("y", "count"),
             thoroughness_index=("y", "mean"),
             responses_word_count=("responses_word_count", "mean"))
        .reset_index()
    )
    desc.to_csv(TABLES_DIR / "rigor_summary_by_year_restricted.csv", index=False)
    logger.info(
        "Saved rigor_summary_by_year_restricted.csv (n=%d, %d years)",
        len(df), len(desc),
    )
    return desc


def fit_nested(df: pd.DataFrame):
    """Fit the four nested OLS models; return dict name->fitted result."""
    formulas = {
        "M0_length_only":  "y ~ log_wc",
        "M1_plus_template": "y ~ log_wc + C(template)",
        "M2_plus_year":     "y ~ log_wc + C(template) + year_c",
        "M3_plus_subdisc":  "y ~ log_wc + C(template) + year_c + C(subdisc)",
    }
    return {name: smf.ols(f, data=df).fit() for name, f in formulas.items()}


def year_robustness(df: pd.DataFrame) -> pd.DataFrame:
    """
    Robustness check for RQ3: does YEAR add anything as a categorical block
    (allowing any non-linear shape), net of log_wc + template + subdiscipline?
    The linear test could miss a non-monotonic trend; this joint F-test cannot.
    Writes per-year adjusted means (vs 2020 baseline) + the block F-test.
    """
    df = df.copy()
    df["year_cat"] = df["year_created"].astype(int).astype(str)
    base = smf.ols("y ~ log_wc + C(template) + C(subdisc)", data=df).fit()
    full = smf.ols("y ~ log_wc + C(template) + C(subdisc) + C(year_cat)", data=df).fit()
    cmp = anova_lm(base, full)
    block_F = float(cmp["F"].iloc[1])
    block_p = float(cmp["Pr(>F)"].iloc[1])
    block_dr2 = full.rsquared - base.rsquared

    rows = [{"year": YEAR_MIN, "adj_mean_vs_2020": 0.0, "std_err": 0.0, "p_value": np.nan}]
    for term in full.params.index:
        if term.startswith("C(year_cat)"):
            yr = term.replace("C(year_cat)[T.", "").rstrip("]").split(".")[0]
            rows.append({
                "year": int(float(yr)),
                "adj_mean_vs_2020": round(full.params[term], 4),
                "std_err": round(full.bse[term], 4),
                "p_value": full.pvalues[term],
            })
    out = pd.DataFrame(rows).sort_values("year")
    out.attrs["block_F"] = block_F
    out.attrs["block_p"] = block_p
    out.attrs["block_dr2"] = block_dr2
    # stash the F-test as trailing rows for the CSV
    meta = pd.DataFrame([{
        "year": "JOINT_F_TEST", "adj_mean_vs_2020": round(block_dr2, 5),
        "std_err": round(block_F, 2), "p_value": block_p,
    }])
    pd.concat([out, meta], ignore_index=True).to_csv(
        TABLES_DIR / "rigor_model_year_robustness.csv", index=False)
    return out


def summarise_models(models: dict, df: pd.DataFrame) -> dict:
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    m3 = models["M3_plus_subdisc"]

    # ── Nested fit table + incremental F-tests ────────────────────────────────
    order = ["M0_length_only", "M1_plus_template", "M2_plus_year", "M3_plus_subdisc"]
    rows = []
    prev = None
    for name in order:
        res = models[name]
        row = {
            "model": name,
            "df_model": int(res.df_model),
            "r2": round(res.rsquared, 4),
            "adj_r2": round(res.rsquared_adj, 4),
            "aic": round(res.aic, 1),
        }
        if prev is not None:
            row["delta_r2_vs_prev"] = round(res.rsquared - models[prev].rsquared, 4)
            try:
                cmp = anova_lm(models[prev], res)
                row["incr_F"] = round(float(cmp["F"].iloc[1]), 2)
                row["incr_p"] = float(cmp["Pr(>F)"].iloc[1])
            except Exception as e:  # pragma: no cover
                row["incr_F"], row["incr_p"] = np.nan, np.nan
                logger.warning("anova_lm failed for %s vs %s: %s", prev, name, e)
        rows.append(row)
        prev = name
    nested = pd.DataFrame(rows)
    nested.to_csv(TABLES_DIR / "rigor_model_nested.csv", index=False)

    # ── Year slope across models (does the trend survive adding length?) ──────
    year_track = []
    raw = smf.ols("y ~ year_c", data=df).fit()
    year_track.append(("year_only_no_controls", raw.params["year_c"], raw.bse["year_c"], raw.pvalues["year_c"]))
    for name in ["M2_plus_year", "M3_plus_subdisc"]:
        r = models[name]
        year_track.append((name, r.params["year_c"], r.bse["year_c"], r.pvalues["year_c"]))

    # ── Full M3 coefficient table (classical + HC3 robust SEs) ────────────────
    # Coefficients are identical under HC3 (it only reweights the covariance
    # matrix, not the point estimates) so a single coef column covers both;
    # std_err/p_value/CI are reported for each so the two can be compared
    # directly, e.g. to check whether any term crosses p=.05 under HC3 that
    # didn't under classical SEs.
    m3_hc3 = smf.ols("y ~ log_wc + C(template) + year_c + C(subdisc)", data=df).fit(cov_type="HC3")
    ci = m3.conf_int()
    ci_hc3 = m3_hc3.conf_int()
    coef = pd.DataFrame({
        "term": m3.params.index,
        "coef": m3.params.values,
        "std_err": m3.bse.values,
        "p_value": m3.pvalues.values,
        "ci_low": ci[0].values,
        "ci_high": ci[1].values,
        "std_err_hc3": m3_hc3.bse.values,
        "p_value_hc3": m3_hc3.pvalues.values,
        "ci_low_hc3": ci_hc3[0].values,
        "ci_high_hc3": ci_hc3[1].values,
    })
    coef["coef"] = coef["coef"].round(4)
    coef.to_csv(TABLES_DIR / "rigor_model_coefficients.csv", index=False)

    # ── Subdiscipline effects net of controls, ranked ────────────────────────
    sub_rows = coef[coef["term"].str.startswith("C(subdisc)")].copy()
    sub_rows["subdiscipline"] = (
        sub_rows["term"].str.replace(r"C\(subdisc\)\[T\.", "", regex=True).str.rstrip("]")
    )
    sub_rows = sub_rows.sort_values("coef", ascending=False)[
        ["subdiscipline", "coef", "std_err", "p_value", "ci_low", "ci_high"]
    ]
    sub_rows.to_csv(TABLES_DIR / "rigor_model_subdiscipline.csv", index=False)

    # ── Verdict (machine-readable gate result) ────────────────────────────────
    year_b = m3.params["year_c"]
    year_p = m3.pvalues["year_c"]
    span_change = year_b * (YEAR_MAX - YEAR_MIN)  # total index change 2020->2025 net of controls
    subdisc_terms = [t for t in m3.params.index if t.startswith("C(subdisc)")]
    subdisc_sig = sum(m3.pvalues[t] < 0.05 for t in subdisc_terms)
    subdisc_sig_hc3 = sum(m3_hc3.pvalues[t] < 0.05 for t in subdisc_terms)
    subdisc_incr_p = float(nested.loc[nested["model"] == "M3_plus_subdisc", "incr_p"].iloc[0])
    subdisc_incr_dr2 = float(nested.loc[nested["model"] == "M3_plus_subdisc", "delta_r2_vs_prev"].iloc[0])

    rq3_survives = bool(year_p < 0.05 and abs(year_b) >= 0.02)
    rq4_survives = bool(subdisc_incr_p < 0.05 and subdisc_incr_dr2 >= 0.005)

    verdict = pd.DataFrame([{
        "n": len(df),
        "log_wc_coef": round(m3.params["log_wc"], 4),
        "log_wc_p": m3.pvalues["log_wc"],
        "year_slope_per_year_net": round(year_b, 4),
        "year_total_change_2020_2025_net": round(span_change, 3),
        "year_p_net": year_p,
        "subdisc_levels": len(subdisc_terms),
        "subdisc_sig_at_05": int(subdisc_sig),
        "subdisc_sig_at_05_hc3": int(subdisc_sig_hc3),
        "subdisc_block_delta_r2": round(subdisc_incr_dr2, 4),
        "subdisc_block_p": subdisc_incr_p,
        "model_r2": round(m3.rsquared, 4),
        "year_p_net_hc3": float(m3_hc3.pvalues["year_c"]),
        "RQ3_temporal_survives": rq3_survives,
        "RQ4_subdisc_gap_survives": rq4_survives,
    }])
    verdict.to_csv(TABLES_DIR / "rigor_model_verdict.csv", index=False)

    return {"nested": nested, "year_track": year_track, "coef": coef,
            "subdisc": sub_rows, "verdict": verdict}


def run() -> dict:
    features = pd.read_parquet(FEATURES_PATH)
    df = build_design(features)
    out = {"correlations": correlation_table(df)}
    out["subdiscipline_descriptives"] = subdiscipline_descriptives(df)
    out["yearly_descriptives"] = yearly_descriptives(df)
    models = fit_nested(df)
    out.update(summarise_models(models, df))
    out["year_robust"] = year_robustness(df)

    # ── Console report ────────────────────────────────────────────────────────
    print("\n" + "=" * 78)
    print("RIGOUR SIGNAL GATE — does thoroughness survive length + template controls?")
    print("=" * 78)
    print(f"Analysis sample (psych, quant/structured templates, {YEAR_MIN}-{YEAR_MAX}): "
          f"{len(df):,} records\n")

    print("Nested models (incremental R^2 over previous block):")
    print(out["nested"].to_string(index=False))
    print()

    print("Year slope (index points per year), as controls are added:")
    for name, b, se, p in out["year_track"]:
        print(f"  {name:28s}  b={b:+.4f}  SE={se:.4f}  p={p:.2e}")
    print()

    print("Subdiscipline effects net of length+template+year (index points vs reference):")
    s = out["subdisc"]
    for _, r in pd.concat([s.head(5), s.tail(5)]).iterrows():
        star = "*" if r["p_value"] < 0.05 else " "
        print(f"  {star} {r['subdiscipline'][:38]:38s}  b={r['coef']:+.3f}  p={r['p_value']:.2e}")
    print()

    yr = out["year_robust"]
    print("RQ3 robustness — YEAR as categorical block (any shape), net of all controls:")
    for _, r in yr.iterrows():
        p = "" if pd.isna(r["p_value"]) else f"p={r['p_value']:.2e}"
        print(f"  {int(r['year'])}: adj mean vs 2020 = {r['adj_mean_vs_2020']:+.3f}  {p}")
    print(f"  Joint F-test (year block adds anything?): F={yr.attrs['block_F']:.2f}, "
          f"p={yr.attrs['block_p']:.2e}, ΔR²={yr.attrs['block_dr2']:.5f}")
    print()

    v = out["verdict"].iloc[0]
    print("-" * 78)
    print(f"log(word_count) effect: b={v['log_wc_coef']:+.3f}  (the confound — expect strong +)")
    print(f"RQ3 temporal trend net of controls: total change {YEAR_MIN}->{YEAR_MAX} = "
          f"{v['year_total_change_2020_2025_net']:+.3f} index pts, p={v['year_p_net']:.2e}")
    print(f"   -> RQ3 SURVIVES: {bool(v['RQ3_temporal_survives'])}")
    print(f"RQ4 subdiscipline gap: block ΔR²={v['subdisc_block_delta_r2']:.4f}, "
          f"p={v['subdisc_block_p']:.2e}, {int(v['subdisc_sig_at_05'])}/{int(v['subdisc_levels'])} levels sig")
    print(f"   -> RQ4 SURVIVES: {bool(v['RQ4_subdisc_gap_survives'])}")
    print()

    coef = out["coef"]
    eaob = coef[coef["term"] == "C(subdisc)[T.Experimental Analysis of Behavior]"].iloc[0]
    year_row = coef[coef["term"] == "year_c"].iloc[0]
    print("HC3 robust-SE refit of Model 3 (coefficients unchanged, SEs/p recomputed):")
    print(f"  Experimental Analysis of Behavior:  p (classical) = {eaob['p_value']:.6f}   "
          f"p (HC3) = {eaob['p_value_hc3']:.6f}   crosses .05? "
          f"{'YES' if eaob['p_value'] < .05 <= eaob['p_value_hc3'] or eaob['p_value_hc3'] < .05 <= eaob['p_value'] else 'no'}")
    print(f"  year_c:                              p (classical) = {year_row['p_value']:.6f}   "
          f"p (HC3) = {year_row['p_value_hc3']:.6f}   still non-significant under HC3? "
          f"{'YES' if year_row['p_value_hc3'] >= .05 else 'NO'}")
    print(f"  Subdiscipline dummies sig at p<.05:  classical = {int(v['subdisc_sig_at_05'])}/{int(v['subdisc_levels'])}   "
          f"HC3 = {int(v['subdisc_sig_at_05_hc3'])}/{int(v['subdisc_levels'])}")
    print("=" * 78 + "\n")
    return out


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-8s  %(message)s")
    run()
