#!/usr/bin/env python3
"""
run_dissertation_pipeline.py — Dissertation Analysis Pipeline
================================================================
Runs the Python half of the analysis behind:

    "How has the disciplinary composition and preregistration practice of
    psychology evolved on the OSF (2020-2025)? A meta-science analysis of
    the diffusion of preregistration."  (preregistered at osf.io/3xf7c)

This is a trimmed fork of the source project's run_prep_pipeline.py,
stripped of the unrelated conference-poster stages (features, baseline,
sbs_classifier, psych_classifier).

Stages
------
  labels             -> src/descriptive/labels.py (Method: labelling-coverage stat)
  psych_descriptive  -> src/descriptive/psych_descriptive.py (RQ1 landscape, Figure 1)
  psych_chisquare    -> src/stats/psych_chisquare.py (RQ2 diffusion, Figure 2)
  rigor_model        -> src/stats/rigor_model.py (Tables/Figures 3-4)

`rigor_features` (src/stats/rigor_features.py) is NOT run by default: its
output (reports/tables/rigor/rigor_features.parquet) ships pre-computed in
this repo, because generating it requires the raw registration response
text, which is not redistributed here for size reasons (see README). The
module is still included for transparency/audit of the extraction rules,
and can be run manually against the full-text corpus if you rebuild it
from the raw OSF API dump.

Usage
-----
    python run_dissertation_pipeline.py
    python run_dissertation_pipeline.py --stages psych_chisquare rigor_model
"""
from __future__ import annotations

import argparse
import logging
import pathlib
import time
import sys

import pandas as pd

PROJECT_ROOT = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.descriptive import labels as prep_labels
from src.descriptive import psych_descriptive as prep_psych_descriptive
from src.stats import psych_chisquare as prep_psych_chisquare
from src.stats import rigor_model as prep_rigor_model

CLEAN_PATH = PROJECT_ROOT / "data" / "processed" / "preregistrations_clean.parquet"

logger = logging.getLogger("dissertation_pipeline")

ALL_STAGES = ["labels", "psych_descriptive", "psych_chisquare", "rigor_model"]


def _timer(label):
    class Timer:
        def __enter__(self):
            self.t0 = time.perf_counter()
            logger.info("── Starting: %s ──", label)
            return self

        def __exit__(self, *args):
            elapsed = time.perf_counter() - self.t0
            logger.info("── Finished: %s (%.1f s) ──\n", label, elapsed)

    return Timer()


def main():
    parser = argparse.ArgumentParser(
        description="OSF Preregistrations — Dissertation Analysis Pipeline",
    )
    parser.add_argument(
        "--stages", nargs="+", choices=ALL_STAGES, default=ALL_STAGES,
        help="Which stages to run (default: all).",
    )
    args = parser.parse_args()

    for sub in ("tables/landscape", "tables/rigor", "tables/apa", "tables/labels",
                "figures/landscape", "figures/publication"):
        (PROJECT_ROOT / "reports" / sub).mkdir(parents=True, exist_ok=True)

    logger.info("Loading %s …", CLEAN_PATH)
    df = pd.read_parquet(CLEAN_PATH)
    logger.info("Loaded %d rows (Psychology-subject subset, all years).", len(df))

    if "labels" in args.stages:
        with _timer("Label Diagnostics (psychology-hierarchy subset)"):
            prep_labels.psychology_subdiscipline_distribution(df)
            prep_labels.psychology_subdiscipline_missingness_by_year(df)
            prep_labels.psychology_label_audit_window(df)

    if "psych_descriptive" in args.stages:
        with _timer("Psychology Descriptive Analysis (RQ1)"):
            prep_psych_descriptive.run(df)

    if "psych_chisquare" in args.stages:
        with _timer("Psychology Landscape Chi-square Tests (RQ2)"):
            prep_psych_chisquare.run(df)

    if "rigor_model" in args.stages:
        with _timer("Thoroughness Signal Model (Supporting Indicator)"):
            prep_rigor_model.run()

    logger.info("✓ Pipeline complete.")
    logger.info("Tables  → reports/tables/{landscape,rigor}/")
    logger.info("Figures → reports/figures/landscape/")
    logger.info("Next: Rscript r/rigor_model_refit.R to independently refit the nested")
    logger.info("regression in R (cross-checked against this Python fit), then")
    logger.info("Rscript r/table*.R / r/figure*.R to render the APA tables/figures.")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
    )
    main()
