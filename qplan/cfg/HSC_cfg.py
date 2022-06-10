#
# HSC_cfg.py -- HSC configuration information
#
#  Russell Kackley (rkackley@naoj.org)
#

# Complete list of all HSC filters
all_filters =  [f.upper() for f in ('g', 'r', 'r2', 'i', 'i2', 'z', 'Y', 'NB387', 'NB391', 'NB395', 'NB400', 'NB430', 'NB468', 'NB497', 'NB506', 'NB515', 'NB527', 'NB656', 'NB718', 'NB816', 'NB921', 'NB926', 'IB945', 'NB973', 'NB1010', 'EB-gri')]

# List of filters available for each semester
semester_filters = {
    'S16A': [f.upper() for f in ('g', 'r', 'i', 'z', 'Y', 'NB921', 'NB816', 'NB515', 'NB468', 'NB527', 'NB656')],
    'S16B': [f.upper() for f in ('g', 'r', 'i', 'i2', 'z', 'Y', 'NB387', 'NB515', 'NB527', 'NB816', 'NB921')],
    'S17A': [f.upper() for f in ('g', 'r2', 'i2', 'z', 'Y', 'NB387', 'NB527', 'NB656', 'NB718', 'NB816', 'NB921', 'NB926')],
    'S17B': [f.upper() for f in ('g', 'r2', 'i2', 'z', 'Y', 'NB387', 'NB527', 'NB816', 'NB926')],
    'S18A': [f.upper() for f in ('g', 'r2', 'i2', 'z', 'Y', 'IB945', 'NB101', 'NB816')],
    'S18B': [f.upper() for f in ('g', 'r2', 'i2', 'z', 'Y', 'IB945', 'NB387', 'NB468', 'NB527', 'NB816', 'NB921', 'NB1010')],
    'S19A': [f.upper() for f in ('g', 'r2', 'i2', 'z', 'Y', 'IB945', 'NB387', 'NB527', 'NB816', 'NB921')],
    'S19B': [f.upper() for f in ('g', 'r2', 'i2', 'z', 'Y', 'NB400', 'NB468', 'NB515', 'NB816', 'NB926')],
    'S20A': [f.upper() for f in ('g', 'r2', 'i2', 'z', 'Y', 'NB400', 'NB816', 'NB921', 'NB926')],
    'S20B': [f.upper() for f in ('g', 'r2', 'i2', 'z', 'Y', 'NB430', 'NB497', 'NB816')],
    'S21A': [f.upper() for f in ('g', 'r2', 'i2', 'z', 'Y', 'NB497', 'NB515', 'NB527')],
    'S21B': [f.upper() for f in ('g', 'r2', 'i2', 'z', 'Y', 'NB395', 'NB497', 'NB527')],
    'S22A': [f.upper() for f in ('g', 'r2', 'i2', 'z', 'Y', 'NB395', 'NB497', 'NB527', 'NB656', 'NB718')],
    'S22A': [f.upper() for f in ('g', 'r2', 'i2', 'z', 'Y', 'NB395', 'NB497', 'NB527', 'NB656', 'NB718')],
    'S22B': [f.upper() for f in ('g', 'r2', 'i2', 'z', 'NB391', 'NB395', 'NB497', 'NB506', 'NB515', 'NB718', 'NB816', 'NB921', 'EB-gri')],
    }
