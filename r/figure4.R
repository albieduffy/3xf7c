# figure4.R
#
# Figure 4: Raw Thoroughness Index and Mean Response Length by Year,
# 2020-2025. Two-panel line chart: unadjusted mean thoroughness index by
# year (left) and mean response word count by year (right) -- the length
# confound that drives the apparent rise in the left panel (see Table 6 /
# Figure 3: the year effect does not survive controlling for word count,
# template, and subdiscipline). Greyscale, APA 7th-edition-style (Calibri
# 11pt, falls back to Arial if Calibri isn't installed; no baked-in
# "Figure N"/title -- that belongs in the manuscript caption).
#
# The p value in the annotation is read from rigor_model_verdict.csv
# (year_p_net, the Model 3 year_c coefficient's p value) rather than
# hardcoded, precisely so it can't go stale the way the p = 0.36 in the old
# notebook-pilot figure (reports/figures/landscape/rigor_temporal_raw_vs_length.png)
# did against the later p = .373 full-sample result.
#
# IMPORTANT: this reads the *regression-sample* yearly means (N = 37,206:
# psychology-labelled, 2020-2025, quantitative/structured templates,
# non-zero word count -- same rows the Model 3 year_c coefficient below is
# fit on), not the full labelled-Psychology landscape (N = 47,524). An
# earlier version of this script read rigor_summary_by_year.csv
# (src/stats/rigor_features.py, unrestricted templates), which is why the
# raw yearly index rose ~10% there -- on the restricted sample the raw rise
# is only ~1.4% (3.89 in 2020 to 3.95 in 2025, non-monotonic in between),
# meaning most of that apparent rise was a template/subdiscipline
# composition shift over time, not a genuine within-sample trend; the
# residual length-inflation story (word count +10.8% over the same window)
# still holds within the restricted sample.
#
# Source data: reports/tables/rigor/rigor_summary_by_year_restricted.csv,
# produced by src/stats/rigor_model.py::yearly_descriptives() on the same
# build_design() sample as Tables 5-6 and Figure 3, and
# reports/tables/rigor/rigor_model_verdict.csv (year_p_net, the Model 3
# year_c coefficient's p value).
#
# Run from the project root: Rscript r/figure4.R

library(ggplot2)
library(patchwork)

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

by_year <- read.csv("reports/tables/rigor/rigor_summary_by_year_restricted.csv")
verdict <- read.csv("reports/tables/rigor/rigor_model_verdict.csv")

p_net <- verdict$year_p_net[1]
p_str <- if (p_net < .001) "< .001" else sub("^0\\.", ".", sprintf("%.3f", p_net))

apa_panel_theme <- theme_minimal(base_family = font_family, base_size = 11) +
  theme(
    panel.grid.minor = element_blank(),
    panel.grid.major = element_line(color = "grey85", linewidth = 0.4),
    axis.line = element_line(color = "grey30"),
    axis.ticks = element_line(color = "grey30"),
    axis.text = element_text(color = "black"),
    plot.title = element_text(size = 11, hjust = 0)
  )

p_index <- ggplot(by_year, aes(x = year_created, y = thoroughness_index)) +
  geom_line(color = "black", linewidth = 0.6) +
  geom_point(color = "black", size = 2.2) +
  scale_x_continuous(breaks = by_year$year_created) +
  labs(
    title = "Raw mean index by year (unadjusted for length)",
    x = "Year", y = "Mean thoroughness index (0-6)"
  ) +
  apa_panel_theme

p_wordcount <- ggplot(by_year, aes(x = year_created, y = responses_word_count)) +
  geom_line(color = "black", linewidth = 0.6) +
  geom_point(color = "black", shape = 15, size = 2.2) +
  scale_x_continuous(breaks = by_year$year_created) +
  labs(
    title = "Mean word count by year (the length confound)",
    x = "Year", y = "Mean response word count"
  ) +
  apa_panel_theme

combined <- p_index + p_wordcount +
  plot_annotation(
    subtitle = sprintf(
      "Net of word count, template, and subdiscipline (Table 2, Model 3), the year slope is non-significant (p = %s)",
      p_str
    ),
    theme = theme(
      plot.subtitle = element_text(family = font_family, size = 10.5, hjust = 0.5)
    )
  )

out_dir <- "reports/figures/publication"
if (!dir.exists(out_dir)) dir.create(out_dir, recursive = TRUE)
out_path <- file.path(out_dir, "figure4_temporal_raw_vs_length_greyscale.png")

ggsave(out_path, combined, width = 10, height = 4.5, dpi = 300, bg = "white")

message(sprintf("Saved %s (year slope net of controls: p = %s)", out_path, p_str))
