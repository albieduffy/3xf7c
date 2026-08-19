# table2.R
#
# Table 2: Cochran-Armitage Trend Test Results by Psychology Subdiscipline,
# 2020-2025. Renders an APA 7th-edition-style three-line table (Calibri 11pt,
# bold table number, italic title-case title, no vertical rules, italicised
# statistical symbols, APA p/q-value rounding) to a standalone Word document.
# Supersedes the untracked reports/tables/apa/table6_cochran_armitage_trends.docx
# (same underlying test, but that file baked the number+title into one line
# and rendered p/q as unrounded floating-point strings ~80 digits long).
#
# Source data: reports/tables/landscape/psych_subdiscipline_trends.csv, produced
# by the Cochran-Armitage trend test per subdiscipline (see Figure 2, which
# plots the k = 11 subdisciplines significant here at FDR q < .05). Rows are
# ordered by ascending p (descending |z|), matching table6's original order.
#
# Run from the project root: Rscript r/table2.R

library(flextable)
library(officer)

trends <- read.csv("reports/tables/landscape/psych_subdiscipline_trends.csv")
trends <- trends[order(trends$ca_p), ]

# Calibri is an APA-approved font, but isn't installed on every system (it
# ships with Microsoft Office, not the OS). The docx just stores the font
# name as metadata for Word to resolve at open-time, so no local rendering
# dependency here -- unlike the figure PNGs, no fallback check is needed.
font_family <- "Calibri"

fmt_p <- function(p) {
  if (p < .001) return("< .001")
  sub("^0\\.", ".", sprintf("%.3f", p))  # APA: no leading zero, bounded-by-1 stat
}

tbl_df <- data.frame(
  subdiscipline = trends$psychology_subdiscipline,
  n = format(trends$n_total, big.mark = ",", trim = TRUE),
  share2020 = sprintf("%.4f", trends$share_2020),
  share2025 = sprintf("%.4f", trends$share_2025),
  change = sprintf("%.2f", trends$share_change_pp),
  z = sprintf("%.2f", trends$ca_z),
  p = vapply(trends$ca_p, fmt_p, character(1)),
  q = vapply(trends$ca_q_bh, fmt_p, character(1)),
  check.names = FALSE
)

ft <- flextable(tbl_df)

# ── Header labels: italicise the Latin/lowercase statistical symbols
#    (N, z, p, q); percentages and pp changes are plain descriptive text.
ft <- compose(ft, part = "header", j = "subdiscipline",
              value = as_paragraph("Subdiscipline"))
ft <- compose(ft, part = "header", j = "n",
              value = as_paragraph(as_i("N")))
ft <- compose(ft, part = "header", j = "share2020",
              value = as_paragraph("Share 2020"))
ft <- compose(ft, part = "header", j = "share2025",
              value = as_paragraph("Share 2025"))
ft <- compose(ft, part = "header", j = "change",
              value = as_paragraph("Share Change (pp)"))
ft <- compose(ft, part = "header", j = "z",
              value = as_paragraph(as_i("z"), " (CA Trend)"))
ft <- compose(ft, part = "header", j = "p",
              value = as_paragraph(as_i("p")))
ft <- compose(ft, part = "header", j = "q",
              value = as_paragraph(as_i("q"), " (BH-FDR)"))

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

n_sig <- sum(trends$ca_q_bh < .05)
n_rising <- sum(trends$ca_q_bh < .05 & trends$ca_z > 0)
n_falling <- sum(trends$ca_q_bh < .05 & trends$ca_z < 0)

note_text <- sprintf(
  paste0(
    "Cochran-Armitage test for linear trend in each subdiscipline's share of ",
    "labelled-Psychology OSF registrations, 2020-2025, tested independently ",
    "across k = %d subdisciplines with >= 100 labelled registrations in the ",
    "window. p values are two-tailed; q values are Benjamini-Hochberg (1995) ",
    "false-discovery-rate-adjusted p values across the %d tests. %d ",
    "subdisciplines reached q < .05 (%d rising, %d falling); these are the ",
    "subdisciplines plotted in Figure 2."
  ),
  nrow(trends), nrow(trends), n_sig, n_rising, n_falling
)

doc <- read_docx()
doc <- body_add_fpar(doc, fpar(ftext(
  "Table 2", fp_text(font.family = font_family, font.size = 11, bold = TRUE)
)))
doc <- body_add_fpar(doc, fpar(ftext(
  "Cochran–Armitage Trend Test Results by Psychology Subdiscipline, 2020–2025",
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
out_path <- file.path(out_dir, "table2_cochran_armitage_trends.docx")
print(doc, target = out_path)

message(sprintf(
  "Saved %s (%d subdisciplines tested, %d significant at q < .05: %d rising, %d falling)",
  out_path, nrow(trends), n_sig, n_rising, n_falling
))
