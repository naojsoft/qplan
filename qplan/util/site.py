#
# site.py -- module containing different preconfigured observing sites
#

import pytz
from qplan.util.calcpos import Observer

# Subaru Telescope
site_subaru = Observer('subaru',
                       longitude='-155:28:48.900',
                       latitude='+19:49:42.600',
                       elevation=4163,
                       pressure=615,
                       temperature=0,
                       timezone=pytz.timezone('HST'))

# ---------------------------------
# Add your site above here...


def add_site(name, observer):
    """Add a site."""
    global sites
    assert isinstance(observer, Observer), \
           ValueError("observer needs to be of Observer class")
    sites[name] = observer

def get_site(name):
    """Get an observing site.  May raise a KeyError if a site of the given name
    does not exist.
    """
    return sites[name]


# Add sites from this file
sites = {}
for name, value in list(globals().items()):
    if name.startswith('site_'):
        key = name[5:]
        add_site(key, value)

#END
