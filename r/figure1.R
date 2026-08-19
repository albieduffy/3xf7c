# figure1.R
#
# Figure 1 (RQ1 landscape): count and percentage share of OSF preregistrations
# across psychology subdisciplines, 2020-2025. Greyscale, base-R barplot(),
# styled to APA 7th edition figure conventions (Calibri 11pt, falls back to
# Arial if Calibri isn't installed; no chart junk, no baked-in title/legend --
# the "Figure 1" number and italicised title belong in the manuscript caption,
# not the image; see reports/figures/publication/figure_captions.md).
#
# Source data: reports/tables/landscape/psych_yearly_subdiscipline_counts.csv
# (the same table underlying src/stats/publication_figures.py), summed across
# 2020-2025 and excluding the "(unspecified)" (no subdiscipline label) column.
#
# Run from the project root: Rscript r/figure1.R

yearly <- read.csv(
  "reports/tables/landscape/psych_yearly_subdiscipline_counts.csv",
  check.names = FALSE
)

subdiscipline_cols <- setdiff(names(yearly), c("year_created", "(unspecified)"))
counts <- colSums(yearly[, subdiscipline_cols])
counts <- sort(counts)  # ascending: largest bar ends up at the top with horiz = TRUE

n_total <- sum(counts)
shares <- counts / n_total * 100

bar_labels <- sprintf(
  "%s (%.1f%%)",
  format(counts, big.mark = ",", trim = TRUE),
  shares
)

# Calibri is an APA-approved figure font, but isn't installed on every system
# (it ships with Microsoft Office, not the OS). Fall back to Arial -- also
# APA-approved and metrically similar -- if Calibri isn't available locally.
installed_families <- if (requireNamespace("systemfonts", quietly = TRUE)) {
  systemfonts::system_fonts()$family
} else {
  character(0)
}
font_family <- if ("Calibri" %in% installed_families) "Calibri" else "Arial"
if (font_family != "Calibri") {
  message("Calibri not found on this system; using Arial instead.")
}

out_dir <- "reports/figures/publication"
if (!dir.exists(out_dir)) dir.create(out_dir, recursive = TRUE)
out_path <- file.path(out_dir, "figure1_psychology_landscape_greyscale.png")

png(out_path, width = 7.5, height = 6.0, units = "in", res = 300, pointsize = 11)

op <- par(
  family = font_family,
  font.axis = 1, font.lab = 1,
  las = 1,                      # horizontal category labels
  mar = c(4, 15.5, 1, 6),       # room for long subdiscipline names + trailing labels
  cex.axis = 0.8,
  cex.lab = 0.9,
  bty = "n"
)

bp <- barplot(
  counts,
  horiz = TRUE,
  col = "grey65",
  border = "grey30",
  xlim = c(0, max(counts) * 1.28),
  xlab = "Number of registrations (2020-2025)",
  ylab = ""
)

text(
  x = counts + max(counts) * 0.02,
  y = bp,
  labels = bar_labels,
  adj = 0,
  cex = 0.7,
  col = "black",
  xpd = NA  # allow the longest label (largest bar) to spill into the right margin
)

axis(1, col = "grey30", col.axis = "black")
axis(2, at = bp, labels = FALSE, col = "grey30", tick = TRUE, lwd = 0, lwd.ticks = 0)

par(op)
invisible(dev.off())

message(sprintf(
  "Saved %s (N = %s psychology registrations, %d subdisciplines, 2020-2025)",
  out_path, format(n_total, big.mark = ","), length(counts)
))
