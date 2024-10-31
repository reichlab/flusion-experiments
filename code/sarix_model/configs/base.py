from types import SimpleNamespace

base_config = SimpleNamespace(
    model_class = 'sarix',
    
    # data sources and adjustments for reporting issues
    sources = ['hhs'],

    # fit locations separately or jointly
    fit_locations_separately = False,

    # SARI model parameters
    p = 1,
    P = 0,
    d = 0,
    D = 0,
    season_period = 1,

    # power transform applied to surveillance signals
    power_transform = 'none',

    # sharing of information about parameters
    theta_pooling='shared',
    sigma_pooling='none',
    
    # covariates
    x = ['xmas_spike']
)
