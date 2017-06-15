#
# HSC_cfg.py -- HSC configuration information
#
#  Russell Kackley (rkackley@naoj.org)
#
# List of filters available for each semester
filters = {
    'S16A': [f.upper() for f in ('g', 'r', 'i', 'z', 'Y', 'NB921', 'NB816', 'NB515', 'NB468', 'NB527', 'NB656')],
    'S16B': [f.upper() for f in ('g', 'r', 'i', 'i2', 'z', 'Y', 'NB387', 'NB515', 'NB527', 'NB816', 'NB921')],
    'S17A': [f.upper() for f in ('g', 'r2', 'i2', 'z', 'Y', 'NB387', 'NB527', 'NB656', 'NB718', 'NB816', 'NB921', 'NB926')],
    'S17B': [f.upper() for f in ('g', 'r2', 'i2', 'z', 'Y', 'NB387', 'NB527', 'NB816', 'NB926')],
    }
