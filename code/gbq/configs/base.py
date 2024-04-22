from types import SimpleNamespace

base_config = SimpleNamespace(
  incl_level_feats = True,

  # bagging setup
  num_bags = 100,
  bag_frac_samples = 0.7
)