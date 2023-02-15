#
#  Russell Kackley (rkackley@naoj.org)
#  E. Jeschke
#
import os
import pathlib
import tomli

if ('CONFHOME' in os.environ and
    len(os.environ['CONFHOME'].strip()) > 0):
    path = pathlib.Path(os.environ['CONFHOME']) / 'qplan' / 'HSC_cfg.toml'
else:
    path = pathlib.Path(os.environ['HOME']) / '.qplan' / 'HSC_cfg.toml'

with path.open(mode="rb") as cfg_f:
    HSC_cfg = tomli.load(cfg_f)
