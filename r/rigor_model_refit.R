# rigor_model_refit.R
#
# Independent R refit of the nested OLS "thoroughness" model (dissertation
# Supporting Indicator: Table 5, Table 6, Table 4, Figures 3-4).
#
# src/stats/rigor_model.py fits this model in Python (statsmodels). This
# script reconstructs the same analysis sample and the same nested model
# sequence independently, in R (base lm()), from the same starting point
# both use: reports/tables/rigor/rigor_features.parquet (per-record
# thoroughness flags + word counts; see src/stats/rigor_features.py for how
# those flags were extracted). It is not a wrapper around the Python output
# -- it re-implements build_design() and fit_nested() from scratch using R
# idioms (dplyr filtering, factor()/relevel() for treatment contrasts,
# lm()/anova() for the nested F-tests, sandwich::vcovHC for the HC3
# robustness check).
#
# If reports/tables/rigor/rigor_model_verdict.csv already exists (i.e. the
# Python rigor_model.py stage has already run), this script reads it first
# and prints a cross-check comparison of n and R^2 before overwriting it --
# this is the comparison the dissertation's Method section describes
# ("the refit reproduced an identical analytic sample (n = 37,206) and
# model R^2 (.301)").
#
# This script's own output -- not src/stats/rigor_model.py's -- is what
# table4.R, table5.R, table6.R, figure3.R, and figure4.R render, so those
# ARE genuinely "generated from the R fit", as the dissertation states.
#
# Run from the project root, after run_dissertation_pipeline.py and before
# table4.R/table5.R/table6.R/figure3.R/figure4.R:
#   Rscript r/rigor_model_refit.R

suppressPackageStartupMessages({
  library(arrow)
  library(dplyr)
  library(sandwich)
  library(lmtest)
})

YEAR_MIN <- 2020
YEAR_MAX <- 2025
MIN_SUBDISC_N <- 200  # subdisciplines below this count are pooled into "Other (pooled)"

TABLES_DIR <- "reports/tables/rigor"
FEATURES_PATH <- file.path(TABLES_DIR, "rigor_features.parquet")
VERDICT_PATH <- file.path(TABLES_DIR, "rigor_model_verdict.csv")

# Quantitative/structured templates the thoroughness index is valid for
# (substring match, first match wins -- mirrors QUANT_TEMPLATE_KEYS in
# src/stats/rigor_model.py exactly, including key order).
QUANT_TEMPLATE_KEYS <- c(
  "OSF Preregistration"             = "OSF Prereg",
  "AsPredicted"                     = "AsPredicted",
  "van 't Veer"                     = "van 't Veer",
  "Secondary Data Preregistration"  = "Secondary Data"
)

short_template <- function(x) {
  if (is.na(x)) return(NA_character_)
  for (key in names(QUANT_TEMPLATE_KEYS)) {
    if (grepl(key, x, fixed = TRUE)) return(unname(QUANT_TEMPLATE_KEYS[key]))
  }
  NA_character_
}

# ── Snapshot the Python-fit verdict (if present) before we overwrite it ────
py_verdict <- if (file.exists(VERDICT_PATH)) read.csv(VERDICT_PATH) else NULL

# ── Build the analysis sample (independent reconstruction of build_design())
features <- read_parquet(FEATURES_PATH)

df <- features %>%
  filter(!is.na(psychology_subdiscipline)) %>%
  filter(year_created >= YEAR_MIN, year_created <= YEAR_MAX) %>%
  mutate(template = vapply(registration_supplement, short_template, character(1))) %>%
  filter(!is.na(template)) %>%
  filter(responses_word_count > 0) %>%
  mutate(
    log_wc = log1p(responses_word_count),
    year_c = year_created - YEAR_MIN
  )

sub_counts <- table(df$psychology_subdiscipline)
keep_subs <- names(sub_counts[sub_counts >= MIN_SUBDISC_N])
df$subdisc <- ifelse(df$psychology_subdiscipline %in% keep_subs,
                      as.character(df$psychology_subdiscipline), "Other (pooled)")

ref_sub <- names(sort(table(df$subdisc), decreasing = TRUE))[1]
df$subdisc <- relevel(factor(df$subdisc), ref = ref_sub)

ref_tpl <- names(sort(table(df$template), decreasing = TRUE))[1]
df$template <- relevel(factor(df$template), ref = ref_tpl)

n_obs <- nrow(df)
cat(sprintf(
  "Independent R refit -- analysis sample: %d records, %d subdisciplines (ref=%s), templates=%s, years %d-%d\n",
  n_obs, nlevels(df$subdisc), ref_sub, paste(levels(df$template), collapse = ", "), YEAR_MIN, YEAR_MAX
))

# ── Descriptive companions (Table 4, Figure 4 inputs) ──────────────────────
# Uses the original, unpooled subdiscipline labels (not the "Other (pooled)"
# grouping above), matching src/stats/rigor_model.py::subdiscipline_descriptives().
subdiscipline_descriptives <- df %>%
  group_by(psychology_subdiscipline) %>%
  summarise(N = n(), M = mean(thoroughness_index), SD = sd(thoroughness_index), .groups = "drop") %>%
  arrange(desc(M))
write.csv(subdiscipline_descriptives,
          file.path(TABLES_DIR, "rigor_summary_by_subdiscipline_restricted.csv"), row.names = FALSE)

yearly_descriptives <- df %>%
  group_by(year_created) %>%
  summarise(N = n(), thoroughness_index = mean(thoroughness_index),
            responses_word_count = mean(responses_word_count), .groups = "drop")
write.csv(yearly_descriptives,
          file.path(TABLES_DIR, "rigor_summary_by_year_restricted.csv"), row.names = FALSE)

# ── Correlation table (Table 5 input) ───────────────────────────────────────
CORR_VARS <- c(
  thoroughness_index    = "Thoroughness Index",
  responses_word_count  = "Word Count",
  log_wc                = "Log Word Count",
  year_c                = "Year (Centered)"
)
corr_cols <- names(CORR_VARS)

corr_desc <- data.frame(
  variable = unname(CORR_VARS[corr_cols]),
  M = round(sapply(corr_cols, function(c) mean(df[[c]])), 3),
  SD = round(sapply(corr_cols, function(c) sd(df[[c]])), 3),
  n = n_obs,
  row.names = NULL
)
write.csv(corr_desc, file.path(TABLES_DIR, "rigor_correlation_descriptives.csv"), row.names = FALSE)

pearson_ci <- function(r, n, alpha = 0.05) {
  z <- atanh(pmin(pmax(r, -0.999999), 0.999999))
  se <- 1 / sqrt(n - 3)
  zc <- qnorm(1 - alpha / 2)
  c(tanh(z - zc * se), tanh(z + zc * se))
}

corr_pairs <- combn(corr_cols, 2, simplify = FALSE)
corr_rows <- lapply(corr_pairs, function(p) {
  test <- cor.test(df[[p[1]]], df[[p[2]]])
  ci <- pearson_ci(unname(test$estimate), n_obs)
  data.frame(
    var1 = CORR_VARS[[p[1]]], var2 = CORR_VARS[[p[2]]],
    r = round(unname(test$estimate), 4), p_value = test$p.value,
    ci_low = round(ci[1], 4), ci_high = round(ci[2], 4), n = n_obs
  )
})
corr <- do.call(rbind, corr_rows)
write.csv(corr, file.path(TABLES_DIR, "rigor_correlations.csv"), row.names = FALSE)

# ── Nested OLS models (Table 6 input) ───────────────────────────────────────
m0 <- lm(thoroughness_index ~ log_wc, data = df)
m1 <- lm(thoroughness_index ~ log_wc + template, data = df)
m2 <- lm(thoroughness_index ~ log_wc + template + year_c, data = df)
m3 <- lm(thoroughness_index ~ log_wc + template + year_c + subdisc, data = df)

models <- list(M0_length_only = m0, M1_plus_template = m1,
               M2_plus_year = m2, M3_plus_subdisc = m3)
order <- names(models)

nested_rows <- list()
prev_name <- NULL
for (name in order) {
  m <- models[[name]]
  s <- summary(m)
  row <- data.frame(
    model = name,
    df_model = length(coef(m)) - 1,
    r2 = round(s$r.squared, 4),
    adj_r2 = round(s$adj.r.squared, 4),
    aic = round(AIC(m), 1),
    delta_r2_vs_prev = NA_real_,
    incr_F = NA_real_,
    incr_p = NA_real_
  )
  if (!is.null(prev_name)) {
    prev_m <- models[[prev_name]]
    a <- anova(prev_m, m)
    row$delta_r2_vs_prev <- round(s$r.squared - summary(prev_m)$r.squared, 4)
    row$incr_F <- round(a$F[2], 2)
    row$incr_p <- a$`Pr(>F)`[2]
  }
  nested_rows[[name]] <- row
  prev_name <- name
}
nested <- do.call(rbind, nested_rows)
write.csv(nested, file.path(TABLES_DIR, "rigor_model_nested.csv"), row.names = FALSE)

# ── Full Model 3 coefficient table, classical + HC3 robust SEs ─────────────
s3 <- summary(m3)
ci <- confint(m3)
hc3 <- coeftest(m3, vcov. = vcovHC(m3, type = "HC3"))
ci_hc3 <- coefci(m3, vcov. = vcovHC(m3, type = "HC3"))

coef_df <- data.frame(
  term = rownames(s3$coefficients),
  coef = round(unname(s3$coefficients[, "Estimate"]), 4),
  std_err = unname(s3$coefficients[, "Std. Error"]),
  p_value = unname(s3$coefficients[, "Pr(>|t|)"]),
  ci_low = unname(ci[, 1]),
  ci_high = unname(ci[, 2]),
  std_err_hc3 = unname(hc3[, "Std. Error"]),
  p_value_hc3 = unname(hc3[, "Pr(>|t|)"]),
  ci_low_hc3 = unname(ci_hc3[, 1]),
  ci_high_hc3 = unname(ci_hc3[, 2]),
  row.names = NULL
)
write.csv(coef_df, file.path(TABLES_DIR, "rigor_model_coefficients.csv"), row.names = FALSE)

# ── Subdiscipline effects net of controls, ranked (Figure 3 input) ─────────
sub_rows <- coef_df[grepl("^subdisc", coef_df$term), ]
sub_rows$subdiscipline <- sub("^subdisc", "", sub_rows$term)
sub_rows <- sub_rows[order(-sub_rows$coef), c("subdiscipline", "coef", "std_err", "p_value", "ci_low", "ci_high")]
write.csv(sub_rows, file.path(TABLES_DIR, "rigor_model_subdiscipline.csv"), row.names = FALSE)

# ── Verdict (machine-readable gate result, Figure 4 input) ─────────────────
year_b <- unname(coef(m3)["year_c"])
year_p <- unname(s3$coefficients["year_c", "Pr(>|t|)"])
span_change <- year_b * (YEAR_MAX - YEAR_MIN)

subdisc_terms <- coef_df$term[grepl("^subdisc", coef_df$term)]
subdisc_sig <- sum(coef_df$p_value[coef_df$term %in% subdisc_terms] < 0.05)
subdisc_sig_hc3 <- sum(coef_df$p_value_hc3[coef_df$term %in% subdisc_terms] < 0.05)

m3_nested_row <- nested[nested$model == "M3_plus_subdisc", ]
subdisc_incr_p <- m3_nested_row$incr_p
subdisc_incr_dr2 <- m3_nested_row$delta_r2_vs_prev
year_p_hc3 <- unname(hc3["year_c", "Pr(>|t|)"])

rq3_survives <- isTRUE(year_p < 0.05 && abs(year_b) >= 0.02)
rq4_survives <- isTRUE(subdisc_incr_p < 0.05 && subdisc_incr_dr2 >= 0.005)

verdict <- data.frame(
  n = n_obs,
  log_wc_coef = round(unname(coef(m3)["log_wc"]), 4),
  log_wc_p = unname(s3$coefficients["log_wc", "Pr(>|t|)"]),
  year_slope_per_year_net = round(year_b, 4),
  year_total_change_2020_2025_net = round(span_change, 3),
  year_p_net = year_p,
  subdisc_levels = length(subdisc_terms),
  subdisc_sig_at_05 = subdisc_sig,
  subdisc_sig_at_05_hc3 = subdisc_sig_hc3,
  subdisc_block_delta_r2 = round(subdisc_incr_dr2, 4),
  subdisc_block_p = subdisc_incr_p,
  model_r2 = round(s3$r.squared, 4),
  year_p_net_hc3 = year_p_hc3,
  RQ3_temporal_survives = rq3_survives,
  RQ4_subdisc_gap_survives = rq4_survives
)
write.csv(verdict, VERDICT_PATH, row.names = FALSE)

# ── Cross-check against the Python fit, if available ────────────────────────
cat("\n", strrep("=", 78), "\n", sep = "")
cat("INDEPENDENT R REFIT vs. Python/statsmodels fit (src/stats/rigor_model.py)\n")
cat(strrep("=", 78), "\n")
if (!is.null(py_verdict)) {
  n_match <- py_verdict$n[1] == n_obs
  r2_match <- isTRUE(all.equal(py_verdict$model_r2[1], verdict$model_r2[1], tolerance = 1e-4))
  cat(sprintf("  n:        Python = %d   R = %d   %s\n",
              py_verdict$n[1], n_obs, if (n_match) "MATCH" else "MISMATCH"))
  cat(sprintf("  Model R2: Python = %.4f   R = %.4f   %s\n",
              py_verdict$model_r2[1], verdict$model_r2[1], if (r2_match) "MATCH" else "MISMATCH"))
  cat(sprintf("  Year p (net of controls): Python = %.4g   R = %.4g\n",
              py_verdict$year_p_net[1], verdict$year_p_net[1]))
  cat(sprintf("  Subdiscipline block delta-R2: Python = %.4f   R = %.4f\n",
              py_verdict$subdisc_block_delta_r2[1], verdict$subdisc_block_delta_r2[1]))
  if (!n_match || !r2_match) {
    warning("R refit does not match the Python fit -- investigate before trusting either.")
  }
} else {
  cat("  No prior Python-fit rigor_model_verdict.csv found to compare against\n")
  cat("  (run `python run_dissertation_pipeline.py` first for a cross-check).\n")
}
cat(strrep("=", 78), "\n")
cat(sprintf("R fit: n = %d, Model 3 R^2 = %.4f, year effect net of controls p = %.3f\n",
            n_obs, verdict$model_r2[1], verdict$year_p_net[1]))
