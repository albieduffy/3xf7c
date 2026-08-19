"""
prep_rigor_features.py — Preregistration "thoroughness" feature extraction
==========================================================================
Builds a transparent, auditable text indicator of preregistration
methodological thoroughness from the registration response text.

Design principles
-----------------
* **Transparent & auditable.** Every component is a documented keyword/regex
  rule. No black-box model.
* **Length-robust composite.** The composite index sums *binary presence*
  flags (not raw counts), because keyword counts scale with document length.
  Raw counts and `responses_word_count` are retained separately so the
  length confound can be modelled explicitly.

Caveats (state these in the dissertation)
------------------------------------------
* The OSF registration form sections (hypotheses / analysis plan / etc.) are
  flattened into one `registration_responses_text` blob in this dataset, so
  components are detected across the whole response, not per-section.
* The measure captures *what was written*, not actual rigour or adherence.
* The measure is a face-valid text indicator, not a validated instrument.

Outputs (reports/tables/rigor/)
--------------------------------
* rigor_features.parquet           — per-record component + index table
* rigor_summary_by_year.csv        — mean index/components by year (psych)
* rigor_summary_by_subdiscipline.csv
* rigor_summary_by_template.csv
* rigor_length_correlation.csv     — index vs word-count confound check
"""
from __future__ import annotations

import re
import pathlib
import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
TABLES_DIR = PROJECT_ROOT / "reports" / "tables" / "rigor"

# ── Component definitions ─────────────────────────────────────────────────────
# Each entry: name -> compiled regex. IGNORECASE applied at compile time.
# Keep these readable: the hand-coding manual is derived directly from them.

_PATTERNS_RAW: dict[str, str] = {
    # Explicit hypotheses / directional predictions
    "hypothesis": r"\bhypothes(?:is|es|ize|ise|ized|ised|izing)\b|\bwe (?:predict|expect|anticipate|hypothesi[sz]e)\b|\bit is (?:predicted|expected|hypothesi[sz]ed)\b",
    # Enumerated hypotheses, e.g. "H1", "H2a", "Hypothesis 3"
    "enumerated_hypothesis": r"\bH\d{1,2}[a-z]?\b|\bhypothesis\s+\d{1,2}\b",
    # Sample-size / power justification
    "sample_size_justification": (
        r"\bpower analys[ei]s\b|\bg\s*\*?\s*power\b|\bstatistical power\b|"
        r"\bsample[- ]size (?:calculation|justification|determination|rationale)\b|"
        r"\ba priori\b|\beffect size\b|\bto detect\b|\b\d{1,3}\s*%\s*power\b|"
        r"\bpowered to\b|\bpower of\b|\b1\s*[-–]\s*β\b|\bminimum detectable\b|"
        r"\bsequential (?:analysis|testing)\b|\bstopping rule\b"
    ),
    # Named statistical tests / models
    "named_test": (
        r"\bt[- ]test\b|\banova\b|\bancova\b|\bmanova\b|\bregression\b|"
        r"\bchi[- ]square\b|\bmann[- ]whitney\b|\bwilcoxon\b|\bcorrelation\b|"
        r"\bmixed[- ]?(?:effects?)?\s*model\b|\bmultilevel model\b|\blinear model\b|"
        r"\bstructural equation\b|\bsem\b|\bmediation\b|\bmoderation\b|"
        r"\bbayes(?:ian)?\b|\bgenerali[sz]ed linear\b|\bglm[em]?\b|\blme\b|"
        r"\bfactor analysis\b|\bcluster analysis\b"
    ),
    # Significance / decision threshold
    "alpha_threshold": (
        r"\balpha\b|α|\bp\s*[<≤]\s*0?\.\d+|\bsignificance level\b|"
        r"\bcredible interval\b|\bbayes factor\b|\bBF\d{0,2}\b|\b\.05\b|\b\.01\b"
    ),
    # Multiple-comparison correction
    "correction": (
        r"\bbonferroni\b|\bholm\b|\bfalse discovery\b|\bfdr\b|\btukey\b|"
        r"\b[sš]id[aá]k\b|\bfamily[- ]?wise\b|"
        r"\bcorrect(?:ed|ion|ing)? for multiple\b|\bmultiple compar[ai]sons?\b"
    ),
    # Exclusion / data-handling criteria
    "exclusion_criteria": (
        r"\bexclu(?:de|ded|sion|sions)\b|\boutlier|\battention check\b|"
        r"\bremov(?:e|ed|ing) (?:participants|trials|outliers|data)\b|"
        r"\binclusion criteria\b|\bdata (?:quality|cleaning|exclusion)\b|"
        r"\bmissing data\b"
    ),
    # Directional / comparative prediction language (secondary; noisier)
    "directional": (
        r"\b(?:higher|lower|greater|smaller|larger|increas\w*|decreas\w*|"
        r"positive(?:ly)? (?:correlat|associat|relat)|"
        r"negative(?:ly)? (?:correlat|associat|relat))\b"
    ),
}

_PATTERNS = {name: re.compile(pat, re.IGNORECASE) for name, pat in _PATTERNS_RAW.items()}

# Binary flags that make up the core composite index (length-robust, high-validity).
# `enumerated_hypothesis` and `directional` are kept as columns but excluded from
# the composite to avoid double-counting / noise.
_COMPOSITE_COMPONENTS = [
    "hypothesis",
    "sample_size_justification",
    "named_test",
    "alpha_threshold",
    "correction",
    "exclusion_criteria",
]


# ── Feature extraction ─────────────────────────────────────────────────────────

def extract_features(df: pd.DataFrame, text_col: str = "registration_responses_text") -> pd.DataFrame:
    """
    Compute per-record thoroughness components and a composite index.

    Returns a DataFrame indexed like `df` with columns:
      id, year_created, registration_supplement, psychology_subdiscipline,
      responses_word_count, registration_response_count (if present),
      has_<component> (binary 0/1) and n_<component> (match count) for each rule,
      thoroughness_index (0–6 sum of core binary flags),
      thoroughness_index_z (standardised within the returned frame).
    """
    if text_col not in df.columns:
        raise KeyError(f"Text column '{text_col}' not found in DataFrame.")

    text = df[text_col].fillna("").astype(str)

    out = pd.DataFrame(index=df.index)
    for keep in ("id", "year_created", "registration_supplement",
                 "psychology_subdiscipline", "subject_l1", "subject_l2",
                 "responses_word_count", "registration_response_count"):
        if keep in df.columns:
            out[keep] = df[keep].values

    if "responses_word_count" not in out.columns:
        out["responses_word_count"] = text.str.split().str.len()

    for name, rgx in _PATTERNS.items():
        counts = text.map(lambda s, r=rgx: len(r.findall(s)))
        out[f"n_{name}"] = counts.astype(int)
        out[f"has_{name}"] = (counts > 0).astype(int)

    out["thoroughness_index"] = out[[f"has_{c}" for c in _COMPOSITE_COMPONENTS]].sum(axis=1)

    idx = out["thoroughness_index"].astype(float)
    std = idx.std(ddof=0)
    out["thoroughness_index_z"] = (idx - idx.mean()) / std if std > 0 else 0.0

    logger.info(
        "Extracted thoroughness features for %d records "
        "(mean index = %.2f / %d, %% with hypothesis = %.1f%%).",
        len(out), idx.mean(), len(_COMPOSITE_COMPONENTS),
        out["has_hypothesis"].mean() * 100,
    )
    return out


# ── Summaries (pilot signal check, before hand-coding) ────────────────────────

def _psych_mask(features: pd.DataFrame) -> pd.Series:
    return features.get("psychology_subdiscipline", pd.Series(index=features.index)).notna()


def summarise(features: pd.DataFrame) -> dict:
    """
    Write summary tables for the psychology subset: mean composite + components
    by year, subdiscipline, and template, plus a length-confound correlation.
    These give an immediate read on whether there is any signal/trend *before*
    investing in hand-coding (i.e. the week-3 pilot gate).
    """
    psych = features[_psych_mask(features)].copy()
    if psych.empty:
        logger.warning("No psychology-labelled rows; summaries skipped.")
        return {}

    comp_cols = [f"has_{c}" for c in _COMPOSITE_COMPONENTS]
    agg_cols = ["thoroughness_index"] + comp_cols

    # 2020-2025 window, matching rigor_model.py (YEAR_MIN/YEAR_MAX) and the
    # psychology-landscape chi-square/trend tests, so every psychology
    # subdiscipline table in the dissertation shares one analysis window.
    psych_window = psych[psych["year_created"].between(2020, 2025)]

    by_year = (
        psych_window
        .groupby("year_created")[agg_cols + ["responses_word_count"]]
        .mean().round(3)
    )
    by_year["n"] = psych_window.groupby("year_created").size()
    by_year.to_csv(TABLES_DIR / "rigor_summary_by_year.csv")

    by_sub = (
        psych_window.groupby("psychology_subdiscipline")[agg_cols]
        .mean().round(3)
    )
    by_sub["thoroughness_index_sd"] = (
        psych_window.groupby("psychology_subdiscipline")["thoroughness_index"]
        .std().round(3)
    )
    by_sub["n"] = psych_window.groupby("psychology_subdiscipline").size()
    by_sub = by_sub.sort_values("thoroughness_index", ascending=False)
    by_sub.to_csv(TABLES_DIR / "rigor_summary_by_subdiscipline.csv")

    if "registration_supplement" in psych.columns:
        by_tpl = (
            psych.groupby("registration_supplement")[agg_cols + ["responses_word_count"]]
            .mean().round(3)
        )
        by_tpl["n"] = psych.groupby("registration_supplement").size()
        by_tpl = by_tpl[by_tpl["n"] >= 100].sort_values("thoroughness_index", ascending=False)
        by_tpl.to_csv(TABLES_DIR / "rigor_summary_by_template.csv")

    # Length confound: correlation of index with log word count
    wc = psych["responses_word_count"].astype(float)
    valid = wc > 0
    if valid.sum() > 10:
        r = np.corrcoef(
            psych.loc[valid, "thoroughness_index"].astype(float),
            np.log1p(wc[valid]),
        )[0, 1]
    else:
        r = np.nan
    pd.DataFrame([{
        "n": int(valid.sum()),
        "pearson_index_vs_log_wordcount": round(float(r), 3),
        "note": "Strong positive r => composite is partly a length proxy; control word count in models.",
    }]).to_csv(TABLES_DIR / "rigor_length_correlation.csv", index=False)

    logger.info(
        "Psych thoroughness: 2020 mean=%.2f -> 2025 mean=%.2f  |  index~log(words) r=%.2f",
        by_year.loc[2020, "thoroughness_index"] if 2020 in by_year.index else float("nan"),
        by_year.loc[2025, "thoroughness_index"] if 2025 in by_year.index else float("nan"),
        r,
    )
    return {"by_year": by_year, "by_subdiscipline": by_sub}


# ── Orchestrator ──────────────────────────────────────────────────────────────

def run(df: pd.DataFrame) -> pd.DataFrame:
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    features = extract_features(df)
    features.to_parquet(TABLES_DIR / "rigor_features.parquet", index=False)
    summarise(features)
    return features


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-8s  %(message)s")
    CLEAN_PATH = PROJECT_ROOT / "data" / "processed" / "preregistrations_clean.parquet"
    _df = pd.read_parquet(CLEAN_PATH)
    run(_df)
