# This script should be run with code/sarix_model as the working directory:
# python retrospective-experiments/sarix_experiments.py

import datetime
import subprocess
from itertools import product

# model_names = [
#     f'sarix_p{p}_4rt_theta{theta_pooling}_sigmanone_xmas_spike' \
#         for (p, theta_pooling) in product([2, 4, 6, 8], ['none', 'shared'])
# ]
model_names = [
    f'sarix_p{p}_4rt_theta{theta_pooling}_sigmanone' \
        for (p, theta_pooling) in product([2, 4, 6, 8], ['none', 'shared'])
]

ref_dates = [
    (datetime.date(2023, 10, 14) + datetime.timedelta(i * 7)).isoformat() \
        for i in range(30)
]

def run_command(command):
    """Run system command"""
    subprocess.run(command)


output_root = '../../retrospective-hub/model-output'

commands = [[
    "python",
    "sarix_model.py",
    "--ref_date", ref_date,
    "--output_root", output_root,
    "--model_name", model_name]
    for (model_name, ref_date) in product(model_names, ref_dates)]

for command in commands:
    run_command(command)
