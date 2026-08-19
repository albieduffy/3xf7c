# table1.R
#
# Table 1: Chi-Square Test of Independence, Year x Psychology Subdiscipline,
# 2020-2025. Renders an APA 7th-edition-style three-line table (Calibri 11pt,
# bold table number, italic title-case title, no vertical rules, italicised
# statistical symbols, APA p-value rounding) to a standalone Word document.
#
# Source data: reports/tables/landscape/psych_chisq_year_by_category.csv,
# produced by src/stats/psych_chisquare.py::chisq_year_by_category(). That
# test excludes the 3 subdisciplines with < 100 labelled registrations across
# 2020-2025 (Comparative, Community, and Transpersonal Psychology), leaving
# k = 19 subdisciplines and N = 47,370 (vs. N = 47,524 across all 22
# subdisciplines in Figure 1).
#
# Run from the project root: Rscript r/table1.R

library(flextable)
library(officer)

stats <- read.csv("reports/tables/landscape/psych_chisq_year_by_category.csv")
s <- as.list(stats[1, ])

fmt_p <- function(p) {
  if (p < .001) return("< .001")
  sprintf("%.3f", p)
}

fmt_v <- function(v) {
  sub("^0\\.", ".", sprintf("%.2f", v))  # APA: no leading zero, bounded-by-1 stat
}

tbl_df <- data.frame(
  k = s$n_subdisciplines,
  years = s$n_years,
  N = format(s$n_observations, big.mark = ",", trim = TRUE),
  chi2 = sprintf("%.2f", s$chi2),
  df = s$dof,
  p = fmt_p(s$p_value),
  v = fmt_v(s$cramers_v),
  check.names = FALSE
)

ft <- flextable(tbl_df)

# ── Header labels: italicise the Latin statistical symbols (N, df, p, V);
#    chi-square is a Greek letter and stays upright per APA convention.
ft <- compose(ft, part = "header", j = "k",
              value = as_paragraph("k (subdisciplines)"))
ft <- compose(ft, part = "header", j = "years",
              value = as_paragraph("Years"))
ft <- compose(ft, part = "header", j = "N",
              value = as_paragraph(as_i("N")))
ft <- compose(ft, part = "header", j = "chi2",
              value = as_paragraph("χ²"))
ft <- compose(ft, part = "header", j = "df",
              value = as_paragraph(as_i("df")))
ft <- compose(ft, part = "header", j = "p",
              value = as_paragraph(as_i("p")))
ft <- compose(ft, part = "header", j = "v",
              value = as_paragraph("Cramér's ", as_i("V")))

# ── APA three-line table: rule under the header and one at the foot; no
#    vertical or interior horizontal rules.
ft <- border_remove(ft)
std_border <- fp_border(color = "black", width = 1)
ft <- hline_top(ft, part = "header", border = std_border)
ft <- hline_bottom(ft, part = "header", border = std_border)
ft <- hline_bottom(ft, part = "body", border = std_border)

ft <- align(ft, align = "center", part = "all")
ft <- font(ft, fontname = "Calibri", part = "all")
ft <- fontsize(ft, size = 11, part = "all")
ft <- padding(ft, padding = 4, part = "all")
ft <- autofit(ft)

n_excluded <- 22L - s$n_subdisciplines  # 22 total labelled subdisciplines (see Figure 1)
note_text <- sprintf(
  paste0(
    "Chi-square test of independence assessing whether the distribution of ",
    "registrations across psychology subdisciplines differed by year, ",
    "2020-2025. Restricted to subdisciplines with ≥ 100 labelled ",
    "registrations across the window (%d excluded); %s%% of cells had an ",
    "expected count < 5."
  ),
  n_excluded, format(s$pct_cells_expected_lt5, trim = TRUE)
)

doc <- read_docx()
doc <- body_add_fpar(doc, fpar(ftext(
  "Table 1", fp_text(font.family = "Calibri", font.size = 11, bold = TRUE)
)))
doc <- body_add_fpar(doc, fpar(ftext(
  "Chi-Square Test of Independence: Year by Psychology Subdiscipline, 2020–2025",
  fp_text(font.family = "Calibri", font.size = 11, italic = TRUE)
)))
doc <- body_add_flextable(doc, ft)
doc <- body_add_par(doc, "", style = "Normal")
doc <- body_add_fpar(doc, fpar(
  ftext("Note. ", fp_text(font.family = "Calibri", font.size = 10, italic = TRUE)),
  ftext(note_text, fp_text(font.family = "Calibri", font.size = 10))
))

out_dir <- "reports/tables/apa"
if (!dir.exists(out_dir)) dir.create(out_dir, recursive = TRUE)
out_path <- file.path(out_dir, "table1_chisq_year_by_subdiscipline.docx")
print(doc, target = out_path)

message(sprintf("Saved %s", out_path))
