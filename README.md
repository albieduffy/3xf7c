# OSF Preregistration Diffusion — Replication Package

Code and data to reproduce the results reported in:

> **How has the disciplinary composition and preregistration practice of psychology
> evolved on the OSF (2020–2025)? A meta-science analysis of the diffusion of
> preregistration.**
> MSc Research Project, Department of Psychology, Goldsmiths, University of London.
> Preregistered at **[osf.io/3xf7c](https://osf.io/3xf7c)**.

The study analyses 47,524 psychology preregistrations carrying a subdiscipline
label on the Open Science Framework (2020–2025), retrieved via the public OSF
API. It tests how each subdiscipline's share of the labelled corpus changed
over time (Cochran-Armitage trend tests) and whether a text-derived indicator
of registration "thoroughness" differs by subdiscipline once document length,
registration template, and year are controlled for (a nested OLS regression).

## What's in this repo

```
├── data/processed/
│   └── preregistrations_clean.parquet   # analytic subset (see "Data" below)
├── reports/tables/rigor/
│   └── rigor_features.parquet           # pre-computed thoroughness features (see "Data")
├── src/
│   ├── ingest/
│   │   ├── load.py                      # raw OSF JSONL -> parquet (reference only, see "Data")
│   │   └── standardize.py               # parquet -> clean parquet (reference only, see "Data")
│   ├── descriptive/
│   │   ├── labels.py                    # labelling-coverage diagnostics (Method section)
│   │   └── psych_descriptive.py         # RQ1: subdiscipline landscape (-> Figure 1)
│   └── stats/
│       ├── psych_chisquare.py           # RQ2: diffusion / trend tests (-> Figure 2)
│       ├── rigor_features.py            # thoroughness-index regex extraction (reference only, see "Data")
│       └── rigor_model.py               # nested OLS regression (-> Figures 3-4)
├── r/                                   # APA table/figure rendering (see "The R layer")
│   ├── rigor_model_refit.R              # independent R refit of the nested regression
│   ├── table1.R … table6.R
│   └── figure1.R … figure4.R
├── run_dissertation_pipeline.py         # single entry point for the Python stages
├── install.R                            # R package installer
└── requirements.txt
```

## Data

`data/processed/preregistrations_clean.parquet` is not the full OSF corpus.
The full corpus (243,441 registrations, all fields, all subjects — several
GB) isn't redistributed here for size reasons. Instead, this file is a
derived subset:

* filtered to records with subject taxonomy `subject_l1 == "Social and
  Behavioral Sciences"` and `subject_l2 == "Psychology"` (67,084 rows, all
  years 2012–2025 — matching the *n* reported in the dissertation's Method
  section)
* columns trimmed to exactly what the included scripts use: `id,
  year_created, subject_l1, subject_l2, psychology_subdiscipline,
  registration_supplement, responses_word_count`. No title, description, or
  registration response text is included.

Because `psych_descriptive.py`, `psych_chisquare.py`, and the `labels.py`
functions used here all internally filter to this same Psychology subset
before computing anything, this trimmed file reproduces their outputs
exactly while being a few hundred KB instead of gigabytes.

`reports/tables/rigor/rigor_features.parquet` is likewise a derived
artifact: one row per Psychology-subject registration with the six binary
"thoroughness" presence flags (hypothesis, sample-size justification, named
statistical test, alpha threshold, multiple-comparison correction, exclusion
criteria) and word counts already extracted — **not** the underlying
registration text those flags were extracted from. `rigor_model.py` reads
this file directly, so the nested regression (Tables/Figures 3–4) is fully
reproducible from it.

Why the raw text isn't included: `src/stats/rigor_features.py` contains
the actual regex extraction rules (kept here for audit/transparency — read
it to see exactly how "thoroughness" is operationalised), but running it
requires each registration's response text, which is materially larger and
is not bundled in this lightweight repo. If you want to rebuild everything
from scratch, including re-running the extraction, `src/ingest/load.py` and
`src/ingest/standardize.py` are included for reference — point `load.py` at
a fresh JSONL dump from the [public OSF API](https://developer.osf.io/) and
run the pipeline forward from there.

## Reproducing the results

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python run_dissertation_pipeline.py
```

This writes CSV/PNG outputs to `reports/tables/{landscape,rigor}/` and
`reports/figures/landscape/`, including a first-pass fit of the nested
regression in Python (`src/stats/rigor_model.py`, via statsmodels).

Then, in R:

```r
source("install.R")  # one-time
```
```bash
Rscript r/rigor_model_refit.R
```

This independently refits the same nested regression in R (see "The R
layer" below), overwrites `reports/tables/rigor/rigor_model_*.csv` and the
correlation/descriptive tables with its own numbers, and prints a
cross-check against the Python fit (`n` and R² should match exactly).
Finally, render every APA table and greyscale figure:

```bash
for f in r/table*.R r/figure*.R; do Rscript "$f"; done
```

Outputs land in `reports/tables/apa/*.docx` and
`reports/figures/publication/*.png`.

### Script → result mapping

| Script | Produces |
|---|---|
| `src/descriptive/labels.py` | Method-section labelling-coverage stats (67,084 psychology-tagged / 19,509 unlabelled / 29.1%; year-by-year coverage trend) |
| `src/descriptive/psych_descriptive.py` + `r/figure1.R` | Figure 1 (subdiscipline landscape) |
| `src/stats/psych_chisquare.py` + `r/table1.R`, `r/table2.R`, `r/table3.R`, `r/figure2.R` | RQ2 diffusion: omnibus χ² (year × subdiscipline), Cochran-Armitage trend tests, χ² (subdiscipline × template), Figure 2 |
| `src/stats/rigor_model.py` (Python fit) + `r/rigor_model_refit.R` (independent R refit) + `r/table4.R`, `r/table5.R`, `r/table6.R`, `r/figure3.R`, `r/figure4.R` | Supporting indicator: correlations, nested regression, subdiscipline descriptives, Figures 3–4 |

## The R layer

`r/table1.R`–`table3.R` and `figure1.R`–`figure2.R` are pure rendering
scripts: they read CSV output the Python stages already computed (RQ1/RQ2
landscape and diffusion statistics) and format it into APA-7 Word tables
(`flextable`/`officer`) and greyscale figures (`ggplot2`/`patchwork`). They
do not fit any model.

The nested "thoroughness" regression is different: it is fit twice,
independently — once in Python (`src/stats/rigor_model.py`, via
`statsmodels`) and once in R (`r/rigor_model_refit.R`, via base `lm()`,
reconstructing the same analysis-sample filtering and treatment contrasts
from scratch against `reports/tables/rigor/rigor_features.parquet`, with
`sandwich`/`lmtest` for the HC3 robustness check). Both fits reproduce the
same analytic sample (n = 37,206) and model R² (.3015); `rigor_model_refit.R`
prints this comparison when run. `table4.R`–`table6.R` and
`figure3.R`–`figure4.R` render the R fit's output, matching the
dissertation's Method section description of an independent R cross-check.

## Software versions

Python 3.8, pandas 2.0.3, SciPy 1.10.1, statsmodels 0.14.1 (per the
dissertation's Software and Reproducibility section). R 4.5.1, flextable
0.9.10, officer 0.7.0, ggplot2, patchwork 1.3.2, arrow, dplyr, sandwich,
lmtest.
