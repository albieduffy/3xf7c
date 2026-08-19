# table3.R
#
# Table 3: Chi-Square Test of Independence, Psychology Subdiscipline by
# Registration Template. Renders an APA 7th-edition-style three-line table
# (Calibri 11pt, bold table number, italic title-case title, no vertical
# rules, italicised statistical symbols, APA p-value rounding) to a
# standalone Word document.
#
# Source data: reports/tables/landscape/psych_chisq_category_by_template.csv,
# produced by src/stats/psych_chisquare.py::chisq_category_by_template(),
# restricted to 2020-2025 (matching Table 1 and Table 2) and to subdisciplines
# with >= 100 labelled rows and the 8 most common registration templates
# within that window.
#
# Run from the project root: Rscript r/table3.R

library(flextable)
library(officer)

stats <- read.csv("reports/tables/landscape/psych_chisq_category_by_template.csv")
s <- as.list(stats[1, ])

# Calibri is an APA-approved font, but isn't installed on every system (it
# ships with Microsoft Office, not the OS). The docx just stores the font
# name as metadata for Word to resolve at open-time, so no local rendering
# dependency here -- unlike the figure PNGs, no fallback check is needed.
font_family <- "Calibri"

fmt_p <- function(p) {
  if (p < .001) return("< .001")
  sub("^0\\.", ".", sprintf("%.3f", p))  # APA: no leading zero, bounded-by-1 stat
}

fmt_v <- function(v) {
  sub("^0\\.", ".", sprintf("%.2f", v))  # APA: no leading zero, bounded-by-1 stat
}

tbl_df <- data.frame(
  k = s$n_subdisciplines,
  templates = s$n_templates,
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
              value = as_paragraph("k (Subdisciplines)"))
ft <- compose(ft, part = "header", j = "templates",
              value = as_paragraph("Templates"))
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
ft <- font(ft, fontname = font_family, part = "all")
ft <- fontsize(ft, size = 11, part = "all")
ft <- padding(ft, padding = 4, part = "all")
ft <- autofit(ft)

# Template names, for the note (ordered by overall frequency, as tested)
tpl_counts <- read.csv("reports/tables/landscape/psych_chisq_category_by_template_counts.csv",
                        check.names = FALSE)
tpl_names <- setdiff(names(tpl_counts), "psychology_subdiscipline")
tpl_list <- paste(tpl_names, collapse = "; ")

n_excluded <- 22L - s$n_subdisciplines  # 22 total labelled subdisciplines (see Figure 1)
note_text <- sprintf(
  paste0(
    "Chi-square test of independence assessing whether registration-template ",
    "use differed by psychology subdiscipline, %s. Restricted to subdisciplines ",
    "with >= 100 labelled registrations across the window (%d excluded) and ",
    "the %d most common registration templates: %s. %s%% of cells had an ",
    "expected count < 5."
  ),
  s$year_range, n_excluded, s$top_templates_k, tpl_list, format(s$pct_cells_expected_lt5, trim = TRUE)
)

doc <- read_docx()
doc <- body_add_fpar(doc, fpar(ftext(
  "Table 3", fp_text(font.family = font_family, font.size = 11, bold = TRUE)
)))
doc <- body_add_fpar(doc, fpar(ftext(
  "Chi-Square Test of Independence: Psychology Subdiscipline by Registration Template",
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
out_path <- file.path(out_dir, "table3_chisq_subdiscipline_by_template.docx")
print(doc, target = out_path)

message(sprintf("Saved %s", out_path))
