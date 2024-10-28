import os
from pathlib import Path

from itertools import chain, product

import datetime

import math
import numpy as np
import pandas as pd

from data_pipeline.loader import FluDataLoader
from data_pipeline.utils import get_holidays

import datetime

from sarix import sarix


# config settings

# date of forecast generation
# forecast_date = datetime.date.today()
forecast_date = datetime.date.fromisoformat("2024-01-03")

# next Saturday: weekly forecasts are relative to this date
ref_date = forecast_date - datetime.timedelta((forecast_date.weekday() + 2) % 7 - 7)
print(f'reference date = {ref_date}')

# maximum forecast horizon
max_horizon = 5

# quantile levels at which to generate predictions
q_levels = [0.01, 0.025, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.35,
            0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80,
            0.85, 0.90, 0.95, 0.975, 0.99]
q_labels = ['0.01', '0.025', '0.05', '0.1', '0.15', '0.2', '0.25', '0.3', '0.35',
            '0.4', '0.45', '0.5', '0.55', '0.6', '0.65', '0.7', '0.75', '0.8',
            '0.85', '0.9', '0.95', '0.975', '0.99']


def get_sarix_preds(power_transform):
    fdl = FluDataLoader('../../data-raw')
    df = fdl.load_data(hhs_kwargs={'as_of': ref_date},
                       sources=['hhs'],
                       power_transform=power_transform)
    
    # season week relative to christmas
    df = df.merge(
        get_holidays() \
            .query("holiday == 'Christmas Day'") \
            .drop(columns=['holiday', 'date']) \
            .rename(columns={'season_week': 'xmas_week'}),
        how='left',
        on='season') \
    .assign(delta_xmas = lambda x: x['season_week'] - x['xmas_week'])
    df['xmas_spike'] = np.maximum(3 - np.abs(df['delta_xmas']), 0)
    
    batched_xy = df[["inc_trans_cs", "xmas_spike"]].values.reshape(len(df['location'].unique()), -1, 2)
    
    sarix_fit_all_locs_theta_pooled = sarix.SARIX(
        xy = batched_xy,
        p = 8,
        d = 0,
        P = 0,
        D = 0,
        season_period = 1,
        transform='none',
        theta_pooling='shared',
        sigma_pooling='none',
        forecast_horizon = 5,
        num_warmup = 1000,
        num_samples = 1000,
        num_chains = 1)
    
    pred_qs = np.percentile(sarix_fit_all_locs_theta_pooled.predictions[..., :, :, 0],
                            np.array(q_levels) * 100, axis=0)
    
    df_hhs_last_obs = df.groupby(['location']).tail(1)
    
    preds_df = pd.concat([
        pd.DataFrame(pred_qs[i, :, :]) \
        .set_axis(df_hhs_last_obs['location'], axis='index') \
        .set_axis(np.arange(1, max_horizon+1), axis='columns') \
        .assign(output_type_id = q_label) \
        for i, q_label in enumerate(q_labels)
    ]) \
    .reset_index() \
    .melt(['location', 'output_type_id'], var_name='horizon') \
    .merge(df_hhs_last_obs, on='location', how='left')
    
    # build data frame with predictions on the original scale
    preds_df['value'] = (preds_df['value'] + preds_df['inc_trans_center_factor']) * preds_df['inc_trans_scale_factor']
    if power_transform == '4rt':
        preds_df['value'] = np.maximum(preds_df['value'], 0.0) ** 4
    else:
        preds_df['value'] = np.maximum(preds_df['value'], 0.0) ** 2
    
    preds_df['value'] = (preds_df['value'] - 0.01 - 0.75**4) * preds_df['pop'] / 100000
    preds_df['value'] = np.maximum(preds_df['value'], 0.0)
    
    # keep just required columns and rename to match hub format
    preds_df = preds_df[['location', 'wk_end_date', 'horizon', 'output_type_id', 'value']]
    
    preds_df['target_end_date'] = preds_df['wk_end_date'] + pd.to_timedelta(7*preds_df['horizon'], unit='days')
    preds_df['reference_date'] = ref_date
    preds_df['horizon'] = preds_df['horizon'] - 2
    preds_df['output_type'] = 'quantile'
    preds_df['target'] = 'wk inc flu hosp'
    preds_df.drop(columns='wk_end_date', inplace=True)
    
    if not Path(f'../../retrospective-hub/model-output/UMass-sarix_{power_transform}').exists():
        Path(f'../../retrospective-hub/model-output/UMass-sarix_{power_transform}').mkdir(parents=True)
    
    preds_df.to_csv(f'../../retrospective-hub/model-output/UMass-sarix_{power_transform}/{str(ref_date)}-UMass-sarix_{power_transform}.csv', index=False)



for power_transform in ['4rt']:
    get_sarix_preds(power_transform)
