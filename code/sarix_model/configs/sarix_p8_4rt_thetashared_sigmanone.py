import copy
from configs.base import base_config

config = copy.deepcopy(base_config)
config.model_name = 'sarix_p8_4rt_thetashared_sigmanone'
config.p = 8
config.power_transform = '4rt'
config.x = []
