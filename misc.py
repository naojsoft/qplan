#
# misc.py -- miscellaneous queue support functions
#
#  Eric Jeschke (eric@naoj.org)
#
from datetime import timedelta
import math
import csv
import yaml

# gen2 imports
#from astro import radec

# local imports
import entity

# def get_body_SOSS(name, ra_funky, dec_funky, equinox=2000):
#     ra_deg = radec.funkyHMStoDeg(ra_funky)
#     dec_deg = radec.funkyDMStoDeg(dec_funky)
#     ra = radec.raDegToString(ra_deg, format='%02d:%02d:%06.3f')
#     dec = radec.decDegToString(dec_deg, format='%s%02d:%02d:%05.2f')
    
#     return get_body(name, ra, dec, equinox=equinox)


def make_slots(start_time, night_length_mn, min_slot_length_sc):
    """
    Parameters
    ----------
    start_time : datetime.datetime
       Start of observation
    night_length_mn : int
        Night length in MINUTES
    min_slot_length_sc : int
        Slot length in SECONDS
    """
    night_slots = []
    for isec in range(0, night_length_mn*60, min_slot_length_sc):
        slot_start = start_time + timedelta(0, isec)
        night_slots.append(entity.Slot(slot_start, min_slot_length_sc))
    
    return night_slots

def alt2airmass(alt_deg):
    xp = 1.0 / math.sin(math.radians(alt_deg + 244.0/(165.0 + 47*alt_deg**1.1)))
    return xp
    
am_inv = []
for alt in range(0, 91):
    alt_deg = float(alt)
    am = alt2airmass(alt_deg)
    am_inv.append((am, alt_deg))

def airmass2alt(am):
    for (x, alt_deg) in am_inv:
        if x <= am:
            return alt_deg
    return 90.0

def calc_slew_time(d_az, d_el, rate_az=0.5, rate_el=0.5):
    """Calculate slew time given a delta in azimuth aand elevation.
    """
    time_sec = max(math.fabs(d_el) / rate_el,
                   math.fabs(d_az) / rate_az)
    return time_sec


#END
