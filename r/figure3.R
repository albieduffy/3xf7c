# figure3.R
#
# Figure 3: Subdiscipline Thoroughness Gap, Net of Length, Template, and Year.
# Forest plot of the Model 3 subdiscipline coefficients (see Table 6) --
# index points relative to the Social Psychology reference level, with 95%
# CIs. Greyscale, APA 7th-edition-style (Calibri 11pt, falls back to Arial
# if Calibri isn't installed; no baked-in title -- the "Figure 3" number,
# italic title, and Note belong in the manuscript caption, not the image),
# with a figure legend positioned inside the plot borders, title-cased.
# Supersedes reports/figures/landscape/rigor_subdiscipline_gap.png (same
# data, but that version bakes the title/note into the image and uses a
# single blue hue rather than a greyscale-safe encoding).
#
# Source data: reports/tables/rigor/rigor_model_subdiscipline.csv, produced
# by src/stats/rigor_model.py::summarise_models() from the M3 nested model
# (same analysis sample as Tables 5-6: labelled-Psychology, 2020-2025,
# quantitative/structured templates, non-zero word count, N = 37,206).
#
# Run from the project root: Rscript r/figure3.R

library(ggplot2)

# Calibri is an APA-approved font, but isn't installed on every system (it
# ships with Microsoft Office, not the OS). Fall back to Arial -- also
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

sub <- read.csv("reports/tables/rigor/rigor_model_subdiscipline.csv")
sub <- sub[order(-sub$coef), ]
sub$subdiscipline <- factor(sub$subdiscipline, levels = rev(sub$subdiscipline))
sub$sig <- factor(
  ifelse(sub$p_value < .05, "Significant", "Not Significant"),
  levels = c("Significant", "Not Significant")
)

p <- ggplot(sub, aes(x = coef, y = subdiscipline, fill = sig)) +
  geom_vline(xintercept = 0, linetype = "dashed", color = "grey30", linewidth = 0.5) +
  geom_col(width = 0.68, color = "grey20", linewidth = 0.3) +
  geom_errorbar(aes(xmin = ci_low, xmax = ci_high), width = 0.25, color = "black", linewidth = 0.4) +
  scale_fill_manual(
    values = c(Significant = "grey30", `Not Significant` = "grey80"),
    labels = c(Significant = "Significant (p < .05)", `Not Significant` = "Not Significant (p ≥ .05)")
  ) +
  # Extra headroom above the top bar so the top-center legend has clear space
  # instead of sitting over the Experimental Analysis of Behavior error bar.
  scale_y_discrete(expand = expansion(add = c(0.6, 1.7))) +
  labs(x = "Coefficient vs. Social Psychology reference (index points)", y = NULL, fill = NULL) +
  theme_minimal(base_family = font_family, base_size = 11) +
  theme(
    panel.grid.major.y = element_blank(),
    panel.grid.minor = element_blank(),
    panel.grid.major.x = element_line(color = "grey85", linewidth = 0.4),
    axis.line.x = element_line(color = "grey30"),
    axis.ticks.x = element_line(color = "grey30"),
    axis.ticks.y = element_blank(),
    axis.text = element_text(color = "black"),
    legend.position = "inside",
    legend.position.inside = c(0.5, 0.98),
    legend.justification = c("center", "top"),
    legend.background = element_rect(fill = "white", color = "grey30", linewidth = 0.4),
    legend.margin = margin(6, 8, 6, 8),
    legend.text = element_text(size = 9),
    plot.margin = margin(10, 14, 10, 10)
  )

out_dir <- "reports/figures/publication"
if (!dir.exists(out_dir)) dir.create(out_dir, recursive = TRUE)
out_path <- file.path(out_dir, "figure3_subdiscipline_gap_greyscale.png")

ggsave(out_path, p, width = 7.5, height = 7, dpi = 300, bg = "white")

message(sprintf(
  "Saved %s (%d subdisciplines vs. Social Psychology reference, %d significant at p < .05)",
  out_path, nrow(sub), sum(sub$sig == "Significant")
))

