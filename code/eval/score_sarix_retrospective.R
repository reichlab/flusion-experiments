library(hubData)
library(hubEvals)
library(tidyverse)

hub_path <- "../../retrospective-hub"
hub_con <- connect_hub(hub_path)

all_hub_models <- list.dirs(file.path(hub_path, "model-output"), full.names = FALSE)
all_sarix_models <- all_hub_models[grepl("sarix", all_hub_models, fixed = TRUE)]
all_sarix_models <- all_sarix_models[!grepl("flusion", all_sarix_models, fixed = TRUE)]

forecasts <- hub_con |>
  dplyr::filter(
    output_type == "quantile",
    model_id %in% all_sarix_models,
    reference_date >= "2023-10-14",
    target_end_date <= "2024-04-27",
    location != "US",
    location != "78"
  ) |>
  dplyr::collect() |>
  as_model_out_tbl()

oracle_output <- read_csv("https://raw.githubusercontent.com/cdcepi/FluSight-forecast-hub/refs/heads/main/target-data/target-hospital-admissions.csv") |>
  dplyr::mutate(target_end_date = date, observation = value) |>
  dplyr::select(location, target_end_date, observation)

scores <- hubEvals::score_model_out(
  model_out_tbl = forecasts,
  target_observations = oracle_output,
  metrics = c("ae_median", "wis"),
  by = "model_id"
)

scores <- scores |>
  dplyr::mutate(
    p = stringr::str_extract(model_id, "_p(.*?)_"),
    p = as.integer(substr(p, 3, nchar(p) - 1)),
    theta_pooling = stringr::str_extract(model_id, "_theta(.*?)_"),
    theta_pooling = substr(theta_pooling, 7, nchar(theta_pooling) - 1)
  )

ggplot(
  data = scores,
  mapping = aes(x = p, y = wis, color = theta_pooling)
) +
  geom_point(mapping = aes(shape = theta_pooling)) +
  geom_line(mapping = aes(linetype = theta_pooling, group = theta_pooling)) +
  theme_bw()

ggplot(
  data = scores,
  mapping = aes(x = p, y = ae_median, color = theta_pooling)
) +
  geom_point(mapping = aes(shape = theta_pooling)) +
  geom_line(mapping = aes(linetype = theta_pooling, group = theta_pooling)) +
  theme_bw()
