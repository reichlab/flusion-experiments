import time

import numpy as np
import pandas as pd

import lightgbm as lgb

from data_pipeline.loader import FluDataLoader
from preprocess import create_features_and_targets


def run_gbq_flu_model(model_config, run_config):
    '''
    Load flu data, generate predictions from a gbq model, and save them as a csv file.
    
    Parameters
    ----------
    model_config: configuration object with settings for the model
    run_config: configuration object with settings for the run
    '''
    # load flu data
    fdl = FluDataLoader('../../data-raw')
    df = fdl.load_data(hhs_kwargs={'as_of': run_config.ref_date})
    
    # augment data with features and target values
    df, feat_names = create_features_and_targets(
        df = df,
        incl_level_feats=model_config.incl_level_feats,
        max_horizon=run_config.max_horizon,
        curr_feat_names=['inc_4rt_cs', 'season_week', 'log_pop'])
    
    # keep only rows that are in-season
    df = df.query("season_week >= 5 and season_week <= 45")
    
    # "test set" df used to generate look-ahead predictions
    df_test = df.loc[df.wk_end_date == df.wk_end_date.max()] \
        .copy()
    x_test = df_test[feat_names]
    
    # "train set" df for model fitting; target value non-missing
    df_train = df.loc[~df['delta_target'].isna().values]
    x_train = df_train[feat_names]
    y_train = df_train['delta_target']

    # train model and obtain test set predictions
    preds_df = _train_gbq_and_predict(model_config, run_config,
                                      df_train, x_train, y_train,
                                      df_test, x_test)
    
    # save
    model_dir = run_config.output_root / f'UMass-{model_config.model_name}'
    model_dir.mkdir(parents=True, exist_ok=True)
    preds_df.to_csv(model_dir / f'{str(run_config.ref_date)}-UMass-{model_config.model_name}.csv', index=False)


def _train_gbq_and_predict(model_config, run_config,
                           df_train, x_train, y_train,
                           df_test, x_test):
    '''
    Train gbq model and get predictions on the original target scale,
    formatted in the FluSight hub format.
    
    Parameters
    ----------
    model_config: configuration object with settings for the model
    run_config: configuration object with settings for the run
    df_train: data frame with training data
    x_train: data frame with training instances in rows, features in columns
    y_train: series with target values
    df_test: data frame with test data
    x_test: data frame with test instances in rows, features in columns
    
    Returns
    -------
    Pandas data frame with test set predictions in FluSight hub format
    '''
    # test set predictions:
    # same number of rows as df_test, one column per quantile level
    test_pred_qs_df = _get_test_quantile_predictions(
        model_config, run_config,
        df_train, x_train, y_train, x_test
    )
    
    # add predictions to original test df
    df_test.reset_index(drop=True, inplace=True)
    df_test_w_preds = pd.concat([df_test, test_pred_qs_df], axis=1)
    
    # melt to get columns into rows, keeping only the things we need to invert data
    # transforms later on
    cols_to_keep = ['source', 'location', 'wk_end_date', 'pop',
                    'inc_4rt_cs', 'horizon',
                    'inc_4rt_center_factor', 'inc_4rt_scale_factor']
    preds_df = df_test_w_preds[cols_to_keep + run_config.q_labels]
    preds_df = preds_df.loc[(preds_df['source'] == 'hhs')]
    preds_df = pd.melt(preds_df,
                       id_vars=cols_to_keep,
                       var_name='quantile',
                       value_name = 'delta_hat')
    
    # build data frame with predictions on the original scale
    preds_df['inc_4rt_cs_target_hat'] = preds_df['inc_4rt_cs'] + preds_df['delta_hat']
    preds_df['inc_4rt_target_hat'] = (preds_df['inc_4rt_cs_target_hat'] + preds_df['inc_4rt_center_factor']) * (preds_df['inc_4rt_scale_factor'] + 0.01)
    preds_df['value'] = (np.maximum(preds_df['inc_4rt_target_hat'], 0.0) ** 4 - 0.01 - 0.75**4) * preds_df['pop'] / 100000
    preds_df['value'] = np.maximum(preds_df['value'], 0.0)
    
    # get predictions into the format needed for FluSight hub submission
    preds_df = _format_as_flusight_output(preds_df, run_config.ref_date)
    
    # sort quantiles to avoid quantile crossing
    preds_df = _quantile_noncrossing(
        preds_df,
        gcols = ['location', 'reference_date', 'horizon', 'target_end_date',
                 'target', 'output_type']
    )
    
    return preds_df


def _get_test_quantile_predictions(model_config, run_config,
                                   df_train, x_train, y_train, x_test):
    '''
    Train the model on bagged subsets of the training data and obtain
    quantile predictions. This is the heart of the method.
    
    Parameters
    ----------
    model_config: configuration object with settings for the model
    run_config: configuration object with settings for the run
    df_train: Pandas data frame with training data
    x_train: numpy array with training instances in rows, features in columns
    y_train: numpy array with target values
    x_test: numpy array with test instances in rows, features in columns
    
    Returns
    -------
    Pandas data frame with test set predictions. The number of rows matches
    the number of rows of `x_test`. The number of columns matches the number
    of quantile levels for predictions as specified in the `run_config`.
    Column names are given by `run_config.q_labels`.
    '''
    # seed for random number generation, based on reference date
    rng_seed = int(time.mktime(run_config.ref_date.timetuple()))
    rng = np.random.default_rng(seed=rng_seed)
    # seeds for lgb model fits, one per combination of bag and quantile level
    lgb_seeds = rng.integers(1e8, size=(model_config.num_bags, len(run_config.q_levels)))
    
    # training loop over bags
    oob_preds_by_bag = np.empty((x_train.shape[0], model_config.num_bags, len(run_config.q_levels)))
    oob_preds_by_bag[:] = np.nan
    test_preds_by_bag = np.empty((x_test.shape[0], model_config.num_bags, len(run_config.q_levels)))
    
    train_seasons = df_train['season'].unique()
    
    for b in range(model_config.num_bags):
        print(f'bag number {b+1}')
        # get indices of observations that are in bag
        bag_seasons = rng.choice(
            train_seasons,
            size = int(len(train_seasons) * model_config.bag_frac_samples),
            replace=False)
        bag_obs_inds = df_train['season'].isin(bag_seasons)
        
        for q_ind, q_level in enumerate(run_config.q_levels):
            # fit to bag
            model = lgb.LGBMRegressor(
                verbosity=-1,
                objective='quantile',
                alpha=q_level,
                random_state=lgb_seeds[b, q_ind])
            model.fit(X=x_train.loc[bag_obs_inds, :], y=y_train.loc[bag_obs_inds])
            
            # oob predictions and test set predictions
            oob_preds_by_bag[~bag_obs_inds, b, q_ind] = model.predict(X=x_train.loc[~bag_obs_inds, :])
            test_preds_by_bag[:, b, q_ind] = model.predict(X=x_test)
    
    # combined predictions across bags: median
    test_pred_qs = np.median(test_preds_by_bag, axis=1)
    
    # test predictions as a data frame, one column per quantile level
    test_pred_qs_df = pd.DataFrame(test_pred_qs)
    test_pred_qs_df.columns = run_config.q_labels
    
    return test_pred_qs_df


def _format_as_flusight_output(preds_df, ref_date):
    # keep just required columns and rename to match hub format
    preds_df = preds_df[['location', 'wk_end_date', 'horizon', 'quantile', 'value']] \
        .rename(columns={'quantile': 'output_type_id'})
    
    preds_df['target_end_date'] = preds_df['wk_end_date'] + pd.to_timedelta(7*preds_df['horizon'], unit='days')
    preds_df['reference_date'] = ref_date
    preds_df['horizon'] = preds_df['horizon'] - 2
    preds_df['target'] = 'wk inc flu hosp'
    
    preds_df['output_type'] = 'quantile'
    preds_df.drop(columns='wk_end_date', inplace=True)
    
    return preds_df


def _quantile_noncrossing(preds_df, gcols):
    '''
    Sort predictions to be in alignment with quantile levels, to prevent
    quantile crossing.
    
    Parameters
    ----------
    preds_df: data frame with quantile predictions
    gcols: columns to group by; predictions will be sorted within those groups
    
    Returns
    -------
    Sorted version of preds_df, guaranteed not to have quantile crossing
    '''
    g = preds_df.set_index(gcols).groupby(gcols)
    preds_df = g[['output_type_id', 'value']] \
        .transform(lambda x: x.sort_values()) \
        .reset_index()
    
    return preds_df