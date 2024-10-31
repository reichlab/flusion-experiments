# This is a copy of ../gbq/utils.py
# with updated model_name choices
# In a future refactor, we should consolidate

import argparse
import importlib
from pathlib import Path
from types import SimpleNamespace

import datetime

def parse_args():
    '''
    Parse arguments to the sarix_model.py script
    
    Returns
    -------
    Two configuration objects collecting settings for the model and the run:
    - `model_config` contains settings for the model
    - `run_config` contains the following properties:
        - `ref_date`: the reference date for the forecast
        - `output_root`: `pathlib.Path` object with the root directory for
            saving model outputs
        - `max_horizon`: integer, maximum forecast horizon relative to the
            last observed data
        - `q_levels`: list of floats with quantile levels for predictions
        - `q_labels`: list of strings with names for the quantile levels
    '''
    parser = _make_parser()
    args = parser.parse_args()
    
    ref_date = _validate_ref_date(args.ref_date)
    model_name = args.model_name
    
    model_config = importlib.import_module(f'configs.{model_name}').config
    
    run_config = SimpleNamespace(
        ref_date=ref_date,
        output_root=args.output_root,
        artifact_store_root=args.artifact_store_root,
        save_feat_importance=args.save_feat_importance
    )
    
    if args.short_run:
        # override model-specified num_bags to a smaller value
        # model_config.num_bags = 10
        
        # maximum forecast horizon
        run_config.max_horizon = 3
        
        # quantile levels at which to generate predictions
        run_config.q_levels = [0.025, 0.50, 0.975]
        run_config.q_labels = ['0.025', '0.5', '0.975']
        
        if model_config.model_class == "sarix":
            run_config.num_warmup = 200
            run_config.num_samples = 200
            run_config.num_chains = 1
    else:
        # maximum forecast horizon
        run_config.max_horizon = 5
        
        # quantile levels at which to generate predictions
        run_config.q_levels = [0.01, 0.025, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30,
                               0.35, 0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70,
                               0.75, 0.80, 0.85, 0.90, 0.95, 0.975, 0.99]
        run_config.q_labels = ['0.01', '0.025', '0.05', '0.1', '0.15', '0.2',
                               '0.25', '0.3', '0.35', '0.4', '0.45', '0.5',
                               '0.55', '0.6', '0.65', '0.7', '0.75', '0.8',
                               '0.85', '0.9', '0.95', '0.975', '0.99']
        
        if model_config.model_class == "sarix":
            run_config.num_warmup = 1000
            run_config.num_samples = 1000
            run_config.num_chains = 1
    
    return model_config, run_config


def _make_parser():
    parser = argparse.ArgumentParser(description='Run gradient boosting model for flu prediction')
    parser.add_argument('--ref_date',
                        help='reference date for predictions in format YYYY-MM-DD; a Saturday',
                        type=lambda s: datetime.date.fromisoformat(s),
                        default=None)
    parser.add_argument('--model_name',
                        help='Model name',
                        choices=['sarix_p8_4rt_thetashared_sigmanone_xmas_spike'],
                        default='sarix_p8_4rt_thetashared_sigmanone_xmas_spike')
    parser.add_argument('--short_run',
                        help='Flag to do a short run; overrides model-default num_bags to 10 and uses 3 quantile levels',
                        action='store_true')
    parser.add_argument('--output_root',
                        help='Path to a directory in which model outputs are saved',
                        type=lambda s: Path(s),
                        default=Path('../../submissions-hub/model-output'))
    parser.add_argument('--artifact_store_root',
                        help='Path to a directory in which artifacts related to model runs are saved',
                        type=lambda s: Path(s),
                        default=Path('../../submissions-hub/model-artifacts'))
    parser.add_argument('--save_feat_importance',
                        help='Flag to save feature importances',
                        action='store_true')
    
    return parser


def _validate_ref_date(ref_date):
    if ref_date is None:
        today = datetime.date.today()
        
        # next Saturday: weekly forecasts are relative to this date
        ref_date = today - datetime.timedelta((today.weekday() + 2) % 7 - 7)
        
        return ref_date
    elif isinstance(ref_date, datetime.date):
        # check that it's a Saturday
        if ref_date.weekday() != 5:
            raise ValueError('ref_date must be a Saturday')
        
        return ref_date
    else:
        raise TypeError('ref_date must be a datetime.date object')


def build_save_path(root, run_config, model_config, subdir=None):
    save_dir = root / f'UMass-{model_config.model_name}'
    if subdir is not None:
        save_dir = save_dir / subdir
    save_dir.mkdir(parents=True, exist_ok=True)
    return save_dir / f'{str(run_config.ref_date)}-UMass-{model_config.model_name}.csv'
