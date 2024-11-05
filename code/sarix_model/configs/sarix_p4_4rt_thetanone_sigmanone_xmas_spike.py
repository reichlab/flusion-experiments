import copy
from configs.base import base_config

config = copy.deepcopy(base_config)
config.model_name = 'sarix_p4_4rt_thetanone_sigmanone_xmas_spike'
config.p = 4
config.power_transform = '4rt'
config.theta_pooling = 'none'
