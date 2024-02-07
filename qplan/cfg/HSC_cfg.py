#
#  Russell Kackley (rkackley@naoj.org)
#  E. Jeschke
#
import pathlib
try:
    import tomllib
except ImportError:
    # see setup.cfg, for python < 3.11
    import tomli as tomllib

from qplan.util.paths import qplan_home

path = pathlib.Path(qplan_home) / 'HSC_cfg.toml'

with path.open(mode="rb") as cfg_f:
    dct = tomllib.load(cfg_f)
    # NOTE: defines all_filters and semester_filters
    globals().update(dct)
