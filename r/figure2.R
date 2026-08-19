# figure2.R
#
# Figure 2 (RQ2 diffusion): slope chart of each subdiscipline's share of
# labelled-Psychology OSF preregistrations in 2020 vs 2025, restricted to
# subdisciplines with a significant (FDR q < .05) Cochran-Armitage trend.
# Greyscale, APA 7th-edition-style: Calibri 11pt (falls back to Arial if
# Calibri isn't installed), no baked-in title, and a figure legend/key
# positioned inside the plot borders with title-cased entries (APA 7
# s7.24-7.26). Mirrors
# src/stats/publication_figures.py::diffusion_slope_figure(), but recodes trend
# direction (rising/falling) with line type and marker fill instead of colour,
# since colour carries no information in greyscale.
#
# Source data: reports/tables/landscape/psych_subdiscipline_trends.csv
# Run from the project root: Rscript r/figure2.R

library(ggplot2)

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

trends <- read.csv("reports/tables/landscape/psych_subdiscipline_trends.csv")

alpha <- 0.05
sig <- trends[trends$ca_q_bh < alpha, ]
sig <- sig[order(-sig$share_2025), ]
sig$trend <- factor(ifelse(sig$ca_z > 0, "Rising", "Falling"), levels = c("Rising", "Falling"))
sig$y0 <- sig$share_2020 * 100
sig$y1 <- sig$share_2025 * 100
sig$id <- factor(seq_len(nrow(sig)))

x0 <- 0
x1 <- 1
label_x <- x1 + 0.08

y_max <- max(c(sig$y0, sig$y1))
y_min <- min(c(sig$y0, sig$y1))
pad <- (y_max - y_min) * 0.05
y_breaks <- seq(0, ceiling(y_max / 5) * 5, by = 5)

# ── Direct labels at the 2025 end, greedy top-down collision avoidance ──────
# (sig is already sorted descending by share_2025/y1, as the algorithm requires)
line_height <- 1.15  # percentage points; tuned to the label font size below
label_y <- sig$y1
for (i in 2:length(label_y)) {
  if (label_y[i - 1] - label_y[i] < line_height) {
    label_y[i] <- label_y[i - 1] - line_height
  }
}
sig$label_y <- label_y

# Share can't be negative, so tick marks/gridlines stay confined to the real
# [0, y_max] data range; but if stacking pushed the lowest label below the
# panel's data floor, extend the panel's lower limit (labels only) so nothing
# gets clipped.
y_lower <- min(y_min - pad, min(label_y) - pad)

lines_df <- data.frame(
  id = rep(sig$id, each = 2),
  trend = rep(sig$trend, each = 2),
  x = rep(c(x0, x1), times = nrow(sig)),
  y = as.vector(t(cbind(sig$y0, sig$y1)))
)

trend_labels <- c(
  Rising  = "Rising Share (FDR q < .05)",
  Falling = "Falling Share (FDR q < .05)"
)

p <- ggplot() +
  geom_hline(yintercept = y_breaks, color = "grey85", linewidth = 0.4) +
  geom_line(
    data = lines_df, aes(x, y, group = id, linetype = trend),
    color = "black", linewidth = 0.7
  ) +
  geom_point(
    data = lines_df, aes(x, y, shape = trend),
    color = "black", fill = "white", size = 2.6, stroke = 0.9
  ) +
  geom_segment(
    data = subset(sig, abs(label_y - y1) > 1e-6),
    aes(x = x1, y = y1, xend = x1 + 0.03, yend = label_y),
    color = "grey50", linewidth = 0.3
  ) +
  geom_text(
    data = sig, aes(x = label_x, y = label_y, label = psychology_subdiscipline),
    hjust = 0, size = 3.2, color = "black", family = font_family
  ) +
  scale_linetype_manual(values = c(Rising = "solid", Falling = "dashed"), labels = trend_labels) +
  scale_shape_manual(values = c(Rising = 16, Falling = 21), labels = trend_labels) +
  scale_x_continuous(
    breaks = c(x0, x1), labels = c("2020", "2025"),
    limits = c(x0 - 0.15, x1 + 0.85), expand = c(0, 0)
  ) +
  scale_y_continuous(
    breaks = y_breaks, limits = c(y_lower, y_max + pad), expand = c(0, 0)
  ) +
  labs(x = NULL, y = "Share of labelled Psychology registrations (%)", linetype = NULL, shape = NULL) +
  theme_minimal(base_family = font_family, base_size = 11) +
  theme(
    panel.grid = element_blank(),
    axis.line.y = element_line(color = "grey30"),
    axis.ticks.y = element_line(color = "grey30"),
    axis.ticks.x = element_blank(),
    axis.text.x = element_text(size = 12, color = "black"),
    axis.text.y = element_text(color = "black"),
    axis.title.y = element_text(size = 11),
    legend.position = "inside",
    legend.position.inside = c(0.98, 0.98),
    legend.justification = c("right", "top"),
    legend.background = element_rect(fill = "white", color = "grey30", linewidth = 0.4),
    legend.margin = margin(6, 8, 6, 8),
    legend.text = element_text(size = 8.5),
    legend.key.width = unit(1.1, "cm"),
    plot.margin = margin(10, 10, 10, 10)
  )

out_dir <- "reports/figures/publication"
if (!dir.exists(out_dir)) dir.create(out_dir, recursive = TRUE)
out_path <- file.path(out_dir, "figure2_diffusion_slope_greyscale.png")

ggsave(out_path, p, width = 7.5, height = 9.5, dpi = 300, bg = "white")

message(sprintf(
  "Saved %s (%d significant subdisciplines: %d rising, %d falling; %d tested)",
  out_path, nrow(sig), sum(sig$trend == "Rising"), sum(sig$trend == "Falling"), nrow(trends)
))
