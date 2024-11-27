library(hubData)
library(hubEvals)
library(tidyverse)

hub_path <- "../../retrospective-hub"
hub_con <- connect_hub(hub_path)

all_hub_models <- list.dirs(file.path(hub_path, "model-output"), full.names = FALSE)
# all_sarix_models <- all_hub_models[grepl("sarix", all_hub_models, fixed = TRUE)]
# all_sarix_models <- all_sarix_models[!grepl("flusion", all_sarix_models, fixed = TRUE)]

selected_models <- c(
  "UMass-gbq_qr_no_reporting_adj",
  "UMass-sarix_p6_4rt_thetashared_sigmanone"
)

forecasts <- hub_con |>
  dplyr::filter(
    output_type == "quantile",
    model_id %in% selected_models,
    reference_date >= "2023-10-14",
    target_end_date <= "2024-04-27",
    location != "US",
    location != "78"
  ) |>
  dplyr::collect() |>
  as_model_out_tbl()
forecasts <- forecasts |>
  dplyr::filter(horizon < 3) %>%
  dplyr::mutate(horizon = horizon + 1)

hub_path <- "../../../FluSight-forecast-hub"
hub_con <- connect_hub(hub_path)
baseline_forecasts <- hub_con |>
  dplyr::filter(
    output_type == "quantile",
    model_id == "FluSight-baseline",
    reference_date >= "2023-10-14",
    target_end_date <= "2024-04-27",
    location != "US",
    location != "78"
  ) |>
  dplyr::collect() |>
  as_model_out_tbl()

forecasts <- dplyr::bind_rows(forecasts, baseline_forecasts)

oracle_output <- read_csv("https://raw.githubusercontent.com/cdcepi/FluSight-forecast-hub/refs/heads/main/target-data/target-hospital-admissions.csv") |>
  dplyr::mutate(target_end_date = date, observation = value) |>
  dplyr::select(location, target_end_date, observation)

scores <- hubEvals::score_model_out(
  model_out_tbl = forecasts,
  target_observations = oracle_output,
  metrics = c("ae_median", "wis"),
  by = c("model_id", "reference_date", "target_end_date")
)

rwis_scores <- scores |>
  dplyr::select(-ae_median) |>
  tidyr::pivot_wider(
    id_cols = c("reference_date", "target_end_date"),
    names_from = "model_id",
    values_from = "wis"
  ) |>
  dplyr::mutate(
    `UMass-gbq_qr_no_reporting_adj` = `UMass-gbq_qr_no_reporting_adj` / `FluSight-baseline`,
    `UMass-sarix_p6_4rt_thetashared_sigmanone` = `UMass-sarix_p6_4rt_thetashared_sigmanone` / `FluSight-baseline`
  ) |>
  dplyr::select(-`FluSight-baseline`) |>
  tidyr::pivot_longer(
    cols = tidyselect::all_of(selected_models),
    names_to = "model_id",
    values_to = "rwis"
  )

ggplot(data = rwis_scores |> dplyr::filter(!is.na(rwis))) +
  geom_raster(
    mapping = aes(x = reference_date, y = target_end_date, fill = rwis)
  ) +
  geom_hline(yintercept = as.Date("2023-12-23"), linetype = 2) +
  geom_vline(xintercept = as.Date("2023-12-23"), linetype = 2) +
  scale_fill_gradient2(
    low = 'blue', mid = 'white', high = 'red',
    midpoint = 1, guide = 'colourbar', aesthetics = 'fill'
  ) +
  facet_wrap( ~ model_id)
