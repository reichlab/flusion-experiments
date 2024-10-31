import copy
from configs.base import base_config

config = copy.deepcopy(base_config)
config.model_name = 'sarix_p6_4rt_thetanone_sigmanone'
config.p = 6
config.power_transform = '4rt'
config.theta_pooling = 'none'
config.x = []
