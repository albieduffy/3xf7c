# table4.R
#
# Table 4: Descriptive Statistics for the Thoroughness Index by Psychology
# Subdiscipline. Renders an APA 7th-edition-style three-line table (Calibri
# 11pt, bold table number, italic title-case title, no vertical rules,
# italicised statistical symbols) to a standalone Word document. Supersedes
# the untracked reports/tables/apa/table1_descriptives_by_subdiscipline.rtf
# (same underlying measure, but that file had no N column and, it turns out,
# was built before rigor_summary_by_subdiscipline.csv was restricted to
# 2020-2025 -- its M/SD values are stale and don't match the current data).
#
# IMPORTANT: this reads the *regression-sample* descriptives (N = 37,206:
# psychology-labelled, 2020-2025, quantitative/structured templates,
# non-zero word count -- same rows the Table 6 model is fit on), not the
# full labelled-Psychology landscape (N = 47,524, Figure 1/Tables 1-3). An
# earlier version of this script read rigor_summary_by_subdiscipline.csv
# (src/stats/rigor_features.py, unrestricted templates), which is why its
# means didn't match the numbers quoted in the "Supporting Indicator" prose
# and its N column summed to 47,524 instead of 37,206 -- the index is only
# valid on the quant/structured-template subset (see rigor_model.py's
# module docstring), so descriptives reported alongside the regression must
# use the same restriction the regression itself uses.
#
# The thoroughness index is a transparent 0-6 composite: the count of six
# binary presence flags detected in each registration's response text
# (hypothesis, sample-size justification, named statistical test, alpha
# threshold, correction for multiple comparisons, exclusion criteria). See
# src/stats/rigor_features.py for the extraction rules and caveats (it is a
# face-valid text indicator of what was written, not a validated instrument
# or a measure of actual rigour).
#
# Source data: reports/tables/rigor/rigor_summary_by_subdiscipline_restricted.csv,
# produced by src/stats/rigor_model.py::subdiscipline_descriptives() on the
# same build_design() sample as the Table 6 regression and Table 5
# correlations (N = 37,206).
#
# Run from the project root: Rscript r/table4.R

library(flextable)
library(officer)

rigor <- read.csv("reports/tables/rigor/rigor_summary_by_subdiscipline_restricted.csv")
rigor <- rigor[order(-rigor$M), ]

# Calibri is an APA-approved font, but isn't installed on every system (it
# ships with Microsoft Office, not the OS). The docx just stores the font
# name as metadata for Word to resolve at open-time, so no local rendering
# dependency here -- unlike the figure PNGs, no fallback check is needed.
font_family <- "Calibri"

tbl_df <- data.frame(
  subdiscipline = rigor$psychology_subdiscipline,
  n = format(rigor$N, big.mark = ",", trim = TRUE),
  M = sprintf("%.2f", rigor$M),
  SD = sprintf("%.2f", rigor$SD),
  check.names = FALSE
)

ft <- flextable(tbl_df)

# ── Header labels: italicise the Latin statistical symbols (N, M, SD).
ft <- compose(ft, part = "header", j = "subdiscipline",
              value = as_paragraph("Subdiscipline"))
ft <- compose(ft, part = "header", j = "n",
              value = as_paragraph(as_i("N")))
ft <- compose(ft, part = "header", j = "M",
              value = as_paragraph(as_i("M")))
ft <- compose(ft, part = "header", j = "SD",
              value = as_paragraph(as_i("SD")))

# ── APA three-line table: rule under the header and one at the foot; no
#    vertical or interior horizontal rules.
ft <- border_remove(ft)
std_border <- fp_border(color = "black", width = 1)
ft <- hline_top(ft, part = "header", border = std_border)
ft <- hline_bottom(ft, part = "header", border = std_border)
ft <- hline_bottom(ft, part = "body", border = std_border)

ft <- align(ft, align = "center", part = "all")
ft <- align(ft, j = "subdiscipline", align = "left", part = "all")
ft <- font(ft, fontname = font_family, part = "all")
ft <- fontsize(ft, size = 11, part = "all")
ft <- padding(ft, padding = 3, part = "all")
ft <- autofit(ft)

n_total <- sum(rigor$N)
note_text <- sprintf(
  paste0(
    "Thoroughness index is a 0-6 composite of binary presence flags ",
    "(hypothesis, sample-size justification, named statistical test, alpha ",
    "threshold, correction for multiple comparisons, exclusion criteria) ",
    "detected in the registration response text; it is a face-valid text ",
    "indicator, not a validated instrument. Computed on the same analysis ",
    "sample as Tables 5-6: labelled-Psychology OSF registrations, 2020-2025, ",
    "restricted to quantitative/structured templates with non-zero response ",
    "word count (N = %s across %d subdisciplines); rows are sorted descending ",
    "by M. Subdisciplines with small N (e.g., Transpersonal Psychology, ",
    "Community Psychology) should be interpreted cautiously."
  ),
  format(n_total, big.mark = ",", trim = TRUE), nrow(rigor)
)

doc <- read_docx()
doc <- body_add_fpar(doc, fpar(ftext(
  "Table 4", fp_text(font.family = font_family, font.size = 11, bold = TRUE)
)))
doc <- body_add_fpar(doc, fpar(ftext(
  "Descriptive Statistics for the Thoroughness Index by Psychology Subdiscipline",
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
out_path <- file.path(out_dir, "table4_descriptives_thoroughness_by_subdiscipline.docx")
print(doc, target = out_path)

message(sprintf(
  "Saved %s (%d subdisciplines, N = %s)",
  out_path, nrow(rigor), format(n_total, big.mark = ",", trim = TRUE)
))

