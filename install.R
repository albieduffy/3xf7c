# Installs the R packages used by r/*.R to render the APA tables/figures and
# to independently refit the nested regression (rigor_model_refit.R).
# flextable/officer/ggplot2/patchwork versions match those reported in the
# dissertation's Software and Reproducibility section (R 4.5.1).
install.packages(c(
  "flextable",    # 0.9.10 — Word table rendering
  "officer",      # 0.7.0  — Word document assembly
  "ggplot2",      # figures
  "patchwork",    # 1.3.2  — multi-panel figures (figure4.R)
  "systemfonts",  # optional — Calibri/Arial font detection fallback
  "arrow",        # rigor_model_refit.R — read rigor_features.parquet
  "dplyr",        # rigor_model_refit.R — data wrangling
  "sandwich",     # rigor_model_refit.R — HC3 robust standard errors
  "lmtest"        # rigor_model_refit.R — coeftest()/coefci() for HC3
))
