library(hubValidations)
library(hubVis)
library(hubData)
library(lubridate)

ref_date <- as.Date("2024-01-06")

locations <- read.csv("../../submissions-hub/auxiliary-data/locations.csv")

forecast <- dplyr::bind_rows(
  read.csv(paste0("../../submissions-hub/model-output/UMass-sarix_p8_4rt_thetashared_sigmanone_xmas_spike/", ref_date, "-UMass-sarix_p8_4rt_thetashared_sigmanone_xmas_spike.csv")) |>
    dplyr::mutate(model_id = "UMass-sarix_4rt"),
) |>
  dplyr::left_join(locations)
head(forecast)

target_data <- readr::read_csv("https://raw.githubusercontent.com/cdcepi/FluSight-forecast-hub/main/target-data/target-hospital-admissions.csv")
head(target_data)


for (timespan in "rolling_12wk") {
  data_start = ref_date - 12 * 7

  incl_models <- "sarix_4rt"
  incl_models_vec = "UMass-sarix_4rt"

  p <- plot_step_ahead_model_output(
    forecast |> dplyr::filter(model_id %in% incl_models_vec),
    target_data |>
      dplyr::filter(date >= data_start) |>
      dplyr::mutate(observation = value),
    x_col_name = "target_end_date",
    x_target_col_name = "date",
    intervals = 0.95,
    facet = "location_name",
    facet_scales = "free_y",
    facet_nrow = 15,
    use_median_as_point = TRUE,
    interactive = FALSE,
    show_plot = FALSE
  )

  save_dir <- paste0("plots/", ref_date)
  if (!dir.exists(save_dir)) {
    dir.create(save_dir, recursive = TRUE)
  }

  save_path <- file.path(save_dir, paste0(ref_date, "_", incl_models, "_", timespan, ".pdf"))

  pdf(save_path, height = 24, width = 14)
  print(p)
  dev.off()
}
