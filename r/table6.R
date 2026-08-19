# table6.R
#
# Table 6: Hierarchical Regression Predicting the Thoroughness Index.
# Renders an APA 7th-edition-style three-line nested-model-comparison table
# (Calibri 11pt, bold table number, italic title-case title, no vertical
# rules, italicised statistical symbols) to a standalone Word document.
#
# This is a concise R2/delta-R2 step summary (one row per nested model), not
# a full per-coefficient table -- the note explicitly frames the table around
# the four model-building steps, and reporting every coefficient (including
# the 16 subdiscipline dummies in Model 3) would bury that structure. The
# full Model 3 coefficient table is in reports/tables/rigor/rigor_model_coefficients.csv
# if a per-predictor table is wanted later. Supersedes the untracked
# reports/tables/apa/table3_hierarchical_regression.rtf (an apaTables sr2
# table for only 2 of the 4 steps).
#
# Source data: reports/tables/rigor/rigor_model_nested.csv, produced by
# src/stats/rigor_model.py::summarise_models(), on the same analysis sample
# as Table 5 (build_design(): labelled-Psychology, 2020-2025, quantitative/
# structured templates, non-zero word count).
#
# Run from the project root: Rscript r/table6.R

library(flextable)
library(officer)

nested <- read.csv("reports/tables/rigor/rigor_model_nested.csv")
verdict <- read.csv("reports/tables/rigor/rigor_model_verdict.csv")
n_obs <- verdict$n[1]

# Calibri is an APA-approved font, but isn't installed on every system (it
# ships with Microsoft Office, not the OS). The docx just stores the font
# name as metadata for Word to resolve at open-time, so no local rendering
# dependency here -- unlike the figure PNGs, no fallback check is needed.
font_family <- "Calibri"

fmt_p <- function(p) {
  if (is.na(p)) return("")
  if (p < .001) return("< .001")
  sub("^0\\.", ".", sprintf("%.3f", p))
}
fmt_r2 <- function(x, digits = 3) if (is.na(x)) "" else sub("^0\\.", ".", sprintf(paste0("%.", digits, "f"), x))
fmt_num <- function(x, digits = 2) if (is.na(x)) "" else sprintf(paste0("%.", digits, "f"), x)

# Incremental-F degrees of freedom: df1 = increase in df_model over the prior
# step; df2 = residual df of the fuller model (N - df_model - 1). Not stored
# in rigor_model_nested.csv, so derived here from df_model and N.
nested$df1 <- c(NA, diff(nested$df_model))
nested$df2 <- n_obs - nested$df_model - 1

predictors_added <- c(
  "log(Word Count)",
  "+ Template",
  "+ Year (Centered)",
  "+ Subdiscipline"
)

tbl_df <- data.frame(
  model = c("Model 0", "Model 1", "Model 2", "Model 3"),
  predictors = predictors_added,
  r2 = vapply(nested$r2, fmt_r2, character(1)),
  dr2 = vapply(nested$delta_r2_vs_prev, fmt_r2, character(1), digits = 4),
  f = vapply(nested$incr_F, fmt_num, character(1)),
  df1 = ifelse(is.na(nested$df1), "", as.character(nested$df1)),
  df2 = ifelse(is.na(nested$df1), "", format(nested$df2, big.mark = ",", trim = TRUE)),
  p = vapply(nested$incr_p, fmt_p, character(1)),
  check.names = FALSE
)

ft <- flextable(tbl_df)

# ── Header labels: italicise the Latin/Greek-Latin statistical symbols
#    (R2, delta R2, F, df, p); superscript the 2 in R2 rather than caret-2.
ft <- compose(ft, part = "header", j = "model", value = as_paragraph("Model"))
ft <- compose(ft, part = "header", j = "predictors", value = as_paragraph("Predictors Added"))
ft <- compose(ft, part = "header", j = "r2", value = as_paragraph(as_i("R"), as_sup("2")))
ft <- compose(ft, part = "header", j = "dr2", value = as_paragraph("Δ", as_i("R"), as_sup("2")))
ft <- compose(ft, part = "header", j = "f", value = as_paragraph(as_i("F")))
ft <- compose(ft, part = "header", j = "df1", value = as_paragraph(as_i("df"), as_sub("1")))
ft <- compose(ft, part = "header", j = "df2", value = as_paragraph(as_i("df"), as_sub("2")))
ft <- compose(ft, part = "header", j = "p", value = as_paragraph(as_i("p")))

# ── APA three-line table: rule under the header and one at the foot; no
#    vertical or interior horizontal rules.
ft <- border_remove(ft)
std_border <- fp_border(color = "black", width = 1)
ft <- hline_top(ft, part = "header", border = std_border)
ft <- hline_bottom(ft, part = "header", border = std_border)
ft <- hline_bottom(ft, part = "body", border = std_border)

ft <- align(ft, align = "center", part = "all")
ft <- align(ft, j = c("model", "predictors"), align = "left", part = "all")
ft <- font(ft, fontname = font_family, part = "all")
ft <- fontsize(ft, size = 11, part = "all")
ft <- padding(ft, padding = 4, part = "all")
ft <- autofit(ft)

note_text <- sprintf(
  paste0(
    "Model 0 = log word count; Model 1 = Model 0 + template; Model 2 = ",
    "Model 1 + year; Model 3 = Model 2 + subdiscipline. Criterion is the ",
    "0-6 thoroughness index (see Table 4). %s and %s are the F-test and ",
    "p value for the change in R%s from the previous model. Analysis ",
    "sample matches Table 5: labelled-Psychology OSF registrations, ",
    "2020-2025, quantitative/structured templates only, non-zero response ",
    "word count (N = %s). Full Model 3 coefficients, including all ",
    "subdiscipline and template effects, are reported in ",
    "rigor_model_coefficients.csv."
  ),
  "F", "p", "²", format(n_obs, big.mark = ",", trim = TRUE)
)

doc <- read_docx()
doc <- body_add_fpar(doc, fpar(ftext(
  "Table 6", fp_text(font.family = font_family, font.size = 11, bold = TRUE)
)))
doc <- body_add_fpar(doc, fpar(ftext(
  "Hierarchical Regression Predicting the Thoroughness Index",
  fp_text(font.family = font_family, font.size = 11, italic = TRUE)
)))
doc <- body_add_flextable(doc, ft)
doc <- body_add_par(doc, "", style = "Normal")
doc <- body_add_fpar(doc, fpar(
  ftext("Note. ", fp_text(font.family = font_family, font.size = 10, italic = TRUE)),
  ftext(note_text, fp_text(font.family = font_family, font.size = 10))
))

out_dir <- "reports/tables/apa"
if (!dir.exists(out_dir)) dir.create(out_dir, recursive = TRUE)
out_path <- file.path(out_dir, "table6_hierarchical_regression.docx")
print(doc, target = out_path)

message(sprintf("Saved %s (N = %s)", out_path, format(n_obs, big.mark = ",", trim = TRUE)))
