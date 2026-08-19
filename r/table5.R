# table5.R
#
# Table 5: Means, Standard Deviations, and Correlations Among Study Variables.
# Renders an APA 7th-edition-style three-line correlation table (Calibri
# 11pt, bold table number, italic title-case title, no vertical rules,
# numbered variable rows, each correlation with its 95% CI stacked
# underneath in a smaller font) to a standalone Word document. Supersedes
# the untracked reports/tables/apa/table2_correlations.rtf (same four study
# variables; this version documents the analysis sample explicitly and adds
# exact p-value-derived significance stars instead of an apaTables black box).
#
# The four continuous study variables are the ones entering the M3 nested
# regression (see rigor_model.py / Table 6): the thoroughness index, raw
# response word count, log word count (the length-confound control), and
# year centered at 2020 (the RQ3 temporal predictor).
#
# Source data: reports/tables/rigor/rigor_correlation_descriptives.csv and
# rigor_correlations.csv, produced by src/stats/rigor_model.py::correlation_table(),
# on the same analysis sample as build_design(): labelled-Psychology
# registrations, 2020-2025, restricted to quantitative/structured templates
# (OSF Preregistration, AsPredicted, van 't Veer & Giner-Sorolla, Secondary
# Data Preregistration) with non-zero response word count.
#
# Run from the project root: Rscript r/table5.R

library(flextable)
library(officer)

desc <- read.csv("reports/tables/rigor/rigor_correlation_descriptives.csv")
corr <- read.csv("reports/tables/rigor/rigor_correlations.csv")

# Calibri is an APA-approved font, but isn't installed on every system (it
# ships with Microsoft Office, not the OS). The docx just stores the font
# name as metadata for Word to resolve at open-time, so no local rendering
# dependency here -- unlike the figure PNGs, no fallback check is needed.
font_family <- "Calibri"

vars <- desc$variable  # already in build order: Thoroughness Index, Word Count, Log Word Count, Year (Centered)
k <- length(vars)
n_obs <- desc$n[1]

fmt_r <- function(r) sub("^(-?)0\\.", "\\1.", sprintf("%.2f", r))
fmt_ci <- function(lo, hi) sprintf("[%s, %s]", fmt_r(lo), fmt_r(hi))
stars <- function(p) if (p < .01) "**" else if (p < .05) "*" else ""

corr_lookup <- function(v1, v2) {
  hit <- corr[(corr$var1 == v1 & corr$var2 == v2) | (corr$var1 == v2 & corr$var2 == v1), ]
  hit[1, ]
}

tbl_df <- data.frame(
  variable = paste0(seq_len(k), ". ", vars),
  M = sprintf("%.2f", desc$M),
  SD = sprintf("%.2f", desc$SD),
  check.names = FALSE
)
col_names <- paste0("c", seq_len(k - 1))
for (cn in col_names) tbl_df[[cn]] <- ""

ft <- flextable(tbl_df)

# ── Header labels: "Variable" plain, M/SD italicised, correlation columns
#    numbered (referring back to the numbered variable rows).
ft <- compose(ft, part = "header", j = "variable", value = as_paragraph("Variable"))
ft <- compose(ft, part = "header", j = "M", value = as_paragraph(as_i("M")))
ft <- compose(ft, part = "header", j = "SD", value = as_paragraph(as_i("SD")))
for (col_idx in seq_len(k - 1)) {
  ft <- compose(ft, part = "header", j = col_names[col_idx], value = as_paragraph(as.character(col_idx)))
}

# ── Fill the lower-triangle correlation cells: r with stars, 95% CI stacked
#    underneath in a smaller font (a two-run paragraph with an embedded line
#    break -- this flextable version has no soft_return() helper).
main_txt <- fp_text_default(font.family = font_family, font.size = 11)
ci_txt   <- fp_text_default(font.family = font_family, font.size = 9)

for (row_i in seq_len(k)) {
  for (col_idx in seq_len(row_i - 1)) {
    hit <- corr_lookup(vars[row_i], vars[col_idx])
    r_str <- paste0(fmt_r(hit$r), stars(hit$p_value))
    ci_str <- fmt_ci(hit$ci_low, hit$ci_high)
    ft <- compose(
      ft, i = row_i, j = col_names[col_idx],
      value = as_paragraph(
        as_chunk(r_str, props = main_txt),
        as_chunk(paste0("\n", ci_str), props = ci_txt)
      )
    )
  }
}

# ── APA three-line table: rule under the header and one at the foot; no
#    vertical or interior horizontal rules.
ft <- border_remove(ft)
std_border <- fp_border(color = "black", width = 1)
ft <- hline_top(ft, part = "header", border = std_border)
ft <- hline_bottom(ft, part = "header", border = std_border)
ft <- hline_bottom(ft, part = "body", border = std_border)

ft <- align(ft, align = "center", part = "all")
ft <- align(ft, j = "variable", align = "left", part = "all")
ft <- valign(ft, valign = "center", part = "all")
ft <- font(ft, fontname = font_family, part = "all")
ft <- fontsize(ft, size = 11, part = "all")
ft <- padding(ft, padding = 4, part = "all")
ft <- autofit(ft)

note_text <- sprintf(
  paste0(
    "M and SD are used to represent mean and standard deviation, ",
    "respectively. Values in square brackets indicate the 95%% confidence ",
    "interval for each correlation (Fisher r-to-z). Word Count is the raw ",
    "registration response word count; Log Word Count is log(1 + Word ",
    "Count), entered in the model as the length-confound control; Year ",
    "(Centered) is year of registration minus 2020. Computed on the same ",
    "analysis sample as the nested regression (Table 6): labelled-Psychology ",
    "OSF registrations, 2020-2025, restricted to quantitative/structured ",
    "templates with non-zero response word count (N = %s). ",
    "* indicates p < .05. ** indicates p < .01."
  ),
  format(n_obs, big.mark = ",", trim = TRUE)
)

doc <- read_docx()
doc <- body_add_fpar(doc, fpar(ftext(
  "Table 5", fp_text(font.family = font_family, font.size = 11, bold = TRUE)
)))
doc <- body_add_fpar(doc, fpar(ftext(
  "Means, Standard Deviations, and Correlations Among Study Variables",
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
out_path <- file.path(out_dir, "table5_correlations.docx")
print(doc, target = out_path)

message(sprintf("Saved %s (N = %s)", out_path, format(n_obs, big.mark = ",", trim = TRUE)))
