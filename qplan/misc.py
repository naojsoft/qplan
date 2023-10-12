#
# misc.py -- miscellaneous queue support functions
#
#  E. Jeschke
#
import math
from datetime import timedelta
from collections import namedtuple

import numpy as np

# gen2 imports
#from astro import radec

# local imports
from . import entity

TelMove = namedtuple('TelMove', ['rot1_start_deg', 'rot1_stop_deg',
                                 'rot2_start_deg', 'rot2_stop_deg',
                                 'az1_start_deg', 'az1_stop_deg',
                                 'az2_start_deg', 'az2_stop_deg',
                                 'alt_start_deg', 'alt_stop_deg',
                                 ])

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


def calc_slew_time_delta(delta_az_deg, delta_el_deg, delta_rot_deg,
                         rate_az=0.5, rate_el=0.5, rate_rot=1.5):
    """Calculate slew time given a delta in azimuth, elevation and
    rotator rotation.

    NOTE: basically assumes that these three motions will be done
    concurrently and so we simply return the time of the one that
    will take the longest.
    """
    time_sec = max(math.fabs(delta_el_deg) / rate_el,
                   math.fabs(delta_az_deg) / rate_az,
                   math.fabs(delta_rot_deg) / rate_rot)
    return time_sec


def calc_slew_time(cur_alt_deg, cur_az_deg, cur_rot_deg,
                   to_alt_deg, to_az_deg, to_rot_deg):

    delta_alt = to_alt_deg - cur_alt_deg
    delta_az = to_az_deg - cur_az_deg
    delta_rot = to_rot_deg - cur_rot_deg

    slew_sec = calc_slew_time_delta(delta_az, delta_alt, delta_rot)
    return slew_sec


def calc_alternate_angle(ang_deg):
    """calculates the alternative usable angle to the given one."""
    _ang_deg = ang_deg - np.sign(ang_deg) * 360
    return _ang_deg


def calc_rotation_choices(cr_start, cr_stop, pa_deg):
    """cr_start and cr_stop are CalculationResult objects for the
    same target at two different times.
    """
    pang1_deg = cr_start.pang_deg
    pang2_deg = cr_stop.pang_deg

    # calculate direction of movement
    # if rotation movement is greater than 180 degrees, then switch the
    # rotation direction of movement to the smaller one with opposite sign
    rot_delta = np.fmod(pang2_deg - pang1_deg, 360.0)
    if np.abs(rot_delta) > 180.0:
        rot_delta = - np.sign(rot_delta) * (rot_delta - np.sign(rot_delta) * 360)

    # rotator_angle = parallactic_angle + position_angle
    rot1_start = np.fmod(pang1_deg + pa_deg, 360.0)
    # calculate the other possible angle for this target
    rot2_start = calc_alternate_angle(rot1_start)

    rot1_stop = rot1_start + rot_delta
    rot2_stop = rot2_start + rot_delta

    az1_start = cr_start.az_deg
    az2_start = calc_alternate_angle(az1_start)
    az1_stop = cr_stop.az_deg

    # calculate direction of movement for standard rotation
    # (see remarks above for rot_delta)
    az_delta = np.fmod(az1_stop - az1_start, 360.0)
    if np.abs(az_delta) > 180.0:
        az_delta = - np.sign(az_delta) * (az_delta - np.sign(az_delta) * 360)
    az2_stop = az2_start + az_delta

    # return both rotation moves, both azimuth moves and elevation start/stop
    return TelMove(rot1_start, rot1_stop, rot2_start, rot2_stop,
                   az1_start, az1_stop, az2_start, az2_stop,
                   cr_start.alt_deg, cr_stop.alt_deg)


def calc_optimal_rotation(rot1_start, rot1_stop, rot2_start, rot2_stop,
                          cur_rot_deg, min_rot, max_rot):
    rot1_ok = ((min_rot <= rot1_start <= max_rot) and
               (min_rot <= rot1_stop <= max_rot))
    rot2_ok = ((min_rot <= rot2_start <= max_rot) and
               (min_rot <= rot2_stop <= max_rot))

    if rot1_ok:
        if not rot2_ok:
            return rot1_start, rot1_stop

        # figure out which rotation would be the shorter distance
        # from the current location
        delta1 = np.fabs(cur_rot_deg - rot1_start)
        delta2 = np.fabs(cur_rot_deg - rot2_start)
        if delta1 < delta2:
            return rot1_start, rot1_stop
        return rot2_start, rot2_stop

    elif rot2_ok:
        return rot2_start, rot2_stop
    else:
        return None, None
