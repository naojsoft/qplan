#
# misc.py -- miscellaneous queue support functions
#
#  E. Jeschke
#
import math
from datetime import timedelta

# 3rd party
import numpy as np

# local imports
from . import entity

# mount angles for certain instruments
mount_deltas = dict(FOCAS=0.259, MOIRCS=45.0)


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
        slot_start = start_time + timedelta(seconds=isec)
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
    """Calculates the alternative usable angle to the given one.
    """
    _ang_deg = ang_deg - np.sign(ang_deg) * 360
    return _ang_deg


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


def normalize_angle(ang_deg, limit=None, ang_offset=0.0):
    """Normalize an angle.

    Parameters
    ----------
    az_deg: float
        A traditional azimuth value where 0 deg == North

    limit: str or None (optional, defaults to None)
        How to limit the range of the result angle

    ang_offset: float (optional, defaults to 0.0)
        Angle to add to the input angle to offset it

    Returns
    -------
    limit: None (-360, 360), 'full' (0, 360), or 'half' (-180, 180)

    To normalize to Subaru azimuth (AZ 0 == S), do
        normalize_angle(ang_deg, limit='half', ang_offset=-180)
    """
    ang_deg = ang_deg + ang_offset

    # constrain to -360, +360
    if np.fabs(ang_deg) >= 360.0:
        ang_deg = np.remainder(ang_deg, np.sign(ang_deg) * 360.0)
    if limit is None:
        return ang_deg

    # constrain to 0, +360
    if ang_deg < 0.0:
        ang_deg += 360.0
    if limit != 'half':
        return ang_deg

    # constrain to -180, +180
    if ang_deg > 180.0:
        ang_deg -= 360.0
    return ang_deg


def calc_subaru_azimuths(az_deg):
    """Calculate Subaru (0 deg == South) azimuth possibilities.

    Parameters
    ----------
    az_deg: float
        A traditional azimuth value where 0 deg == North

    Returns
    -------
    (naz_deg, paz_deg): tuple of float or None
        possible translated azimuths (0 deg == South), one of them may be None

    NOTE: naz_deg is always in the negative direction, paz_deg in the positive
    """
    # limit angle to 0 <= az_deg < 360.0
    # print(f"INPUT: az_deg (N) = {az_deg}")
    az_deg = normalize_angle(az_deg, limit='full', ang_offset=0.0)
    # print(f"NORMALIZED: az_deg (N) = {az_deg}")

    if 0.0 <= az_deg <= 90.0:
        naz_deg = - (180.0 - az_deg)
        paz_deg = 180.0 + az_deg
    elif 90.0 < az_deg < 180.0:
        naz_deg = - (180.0 - az_deg)
        paz_deg = None
    elif 180.0 < az_deg < 270.0:
        naz_deg = None
        paz_deg = az_deg - 180.0
    elif 270.0 < az_deg < 360.0:
        naz_deg = -270.0 + (az_deg - 270.0)
        paz_deg = az_deg - 180.0
    else:
        # az == 180.0
        naz_deg = 0.0
        paz_deg = 0.0

    # print(f"SUBARU: naz_deg (S) = {naz_deg}, paz_deg (S) = {paz_deg}")
    return naz_deg, paz_deg


def get_quadrant(az_deg):
    """Get the quadrant (NE, SE, SW, NW) for a given azimuth.

    Parameters
    ----------
    az_deg: float
        A traditional azimuth value where 0 deg == North

    Returns
    -------
    quadrant : str
        Quadrant which contains azimuth: 'NE', 'SE', 'SW', 'NW'
    """
    is_south = 90.0 < az_deg < 270.0
    if is_south:
        if az_deg <= 180.0:
            return 'SE'
        return 'SW'
    else:
        # <-- is North
        if 0.0 <= az_deg <= 90.0:
            return 'NE'
        return 'NW'


def calc_possible_azimuths(cr_start, cr_stop, obs_lat_deg):
    """Calculate possible azimuth moves.

    Parameters
    ----------
    cr_start: ~qplan.util.calcpos.CalculationResult
        Calculation result for target at start of observation

    cr_stop: ~qplan.util.calcpos.CalculationResult
        Calculation result for target at stop of observation (end of exposure)

    obs_lat_deg: float
        Observers latitude in degrees

    Returns
    -------
    az_choices : list of (float, float) tuples
        List of possible azimuth start and stops in Subaru (S==0 deg) coordinates
    """
    # circumpolar_deg_limit = 90.0 - obs_lat_deg
    # if cr1.dec_deg > circumpolar_deg:
    #     # target in North for whole range
    #     # circumpolar orbit, object may go E to W or W to E
    #     # 2 az directions are possible
    #     if cr1.ha < cr2.ha:
    #         # object moving E to W
    #         pass
    #     else:
    #         # object moving W to E
    #         pass

    # print(f"target DEC DEG={cr_start.dec_deg} OBS_LAT={obs_lat_deg}")
    if cr_start.dec_deg > obs_lat_deg:
        # target in North for whole range
        # 2 az directions are possible
        naz_deg_start, paz_deg_start = calc_subaru_azimuths(cr_start.az_deg)

        if not (-270.0 <= naz_deg_start <= -90.0):
            raise ValueError(f"AZ(neg) start value ({naz_deg_start}) out of range for target in North")
        if not (90.0 <= paz_deg_start <= 270.0):
            raise ValueError(f"AZ(pos) start value ({paz_deg_start}) out of range for target in North")

        naz_deg_stop, paz_deg_stop = calc_subaru_azimuths(cr_stop.az_deg)

        if not (-270.0 <= naz_deg_stop <= -90.0):
            raise ValueError(f"AZ(neg) stop value ({naz_deg_stop}) out of range for target in North")
        if not (90.0 <= paz_deg_stop <= 270.0):
            raise ValueError(f"AZ(pos) stop value ({paz_deg_stop}) out of range for target in North")

        return [(naz_deg_start, naz_deg_stop), (paz_deg_start, paz_deg_stop)]

    elif cr_start.dec_deg < 0.0:
        # target in South for whole range
        # only 1 az direction is possible

        naz_deg_start, paz_deg_start = calc_subaru_azimuths(cr_start.az_deg)
        naz_deg_stop, paz_deg_stop = calc_subaru_azimuths(cr_stop.az_deg)

        if naz_deg_start is not None:
            # <-- target in SE
            if paz_deg_start is not None:
                raise ValueError(f"target in SE has two AZ start values ({naz_deg_start},{paz_deg_start})")
            if naz_deg_stop is not None:
                # <-- target finishes in SE
                return [(naz_deg_start, naz_deg_stop)]
            else:
                # <-- target finishes in SW
                return [(naz_deg_start, paz_deg_stop)]
        else:
            # <-- target in SW
            if paz_deg_stop is None:
                raise ValueError(f"target in SW has no AZ stop value ({paz_deg_stop})")
            if naz_deg_stop is not None:
                raise ValueError(f"target in SW has neg AZ stop value ({naz_deg_stop})")
            return [(paz_deg_start, paz_deg_stop)]

    else:
        # target could be in N and may dip S, depending on start or exp time
        # 2 az directions are possible if target stays in N
        # else only 1 az direction is possible
        start_quad = get_quadrant(cr_start.az_deg)
        stop_quad = get_quadrant(cr_stop.az_deg)

        naz_deg_start, paz_deg_start = calc_subaru_azimuths(cr_start.az_deg)
        naz_deg_stop, paz_deg_stop = calc_subaru_azimuths(cr_stop.az_deg)

        if start_quad == 'NE':
            # <-- stop_quad can be in NE, SE, SW, NW
            if stop_quad not in ['NE', 'SE', 'SW', 'NW']:
                raise ValueError(f"stop quadrant '{stop_quad}' not valid for target originating in NE")
            if stop_quad == 'NE':
                # <-- two azimuths are possible
                return [(naz_deg_start, naz_deg_stop),
                        (paz_deg_start, paz_deg_stop)]
            elif stop_quad == 'SE':
                # <-- only one azimuth is possible
                return [(naz_deg_start, naz_deg_stop)]
            else:
                # <-- only one azimuth is possible
                return [(naz_deg_start, paz_deg_stop)]

        elif start_quad == 'SE':
            # <-- stop_quad can be in SE, SW, NW
            if stop_quad not in ['SE', 'SW', 'NW']:
                raise ValueError(f"stop quadrant '{stop_quad}' not valid for target originating in SE")
            if stop_quad == 'SE':
                # <-- only one azimuth is possible
                return [(naz_deg_start, naz_deg_stop)]
            else:
                # <-- only one azimuth is possible
                return [(naz_deg_start, paz_deg_stop)]

        elif start_quad == 'SW':
            # <-- stop_quad can be in SW, NW
            if stop_quad not in ['SW', 'NW']:
                raise ValueError(f"stop quadrant '{stop_quad}' not valid for target originating in SW")
            # <-- only one azimuth is possible
            return [(paz_deg_start, paz_deg_stop)]

        elif start_quad == 'NW':
            # <-- stop_quad can be in NW only
            if stop_quad not in ['NW']:
                raise ValueError(f"stop quadrant '{stop_quad}' not valid for target originating in NW")
            # <-- two azimuths are possible
            return [(naz_deg_start, naz_deg_stop),
                    (paz_deg_start, paz_deg_stop)]

        else:
            raise ValueError(f"start quadrant '{start_quad}' type not recognized")


def calc_rotator_offset(cr, az_deg, pa_deg, ins_name):
    """Calculate the effective instrument rotator offset.

    Parameters
    ----------
    cr : ~qplan.util.calcpos.CalculationResult
        Calculation result for target at a certain time

    az_deg : float
        The azimuth value (0 deg == South) chosen for the target

    pa_deg : float
        The desired position angle in degrees

    ins_name : str
        Instrument name

    Returns
    -------
    offset_deg : float
        The desirable rotator value for this observation

    NOTE: follows guidelines given by H. Okita for best rotator position
    """
    # get instrument mounting offset
    ins_delta = mount_deltas.get(ins_name, 0.0)

    pang_deg = cr.pang_deg
    # offset_angle = parallactic_angle + position_angle
    offset_deg = normalize_angle(pang_deg + pa_deg, limit='full')
    #offset_deg = np.fmod(pang_deg + pa_deg, 360.0)

    if ins_name in ['HSC', 'PPC']:
        # mirror image at Prime focus
        offset_deg = offset_deg + ins_delta

    elif ins_name in ['MOIRCS', 'FOCAS']:
        # Cassegrain focus
        offset_deg = -offset_deg + ins_delta

    else:
        raise ValueError(f"unknown instrument {ins_name}")

    # print(f"INITIAL OFFSET ANGLE {offset_deg} (pang={pang_deg}, AZ={az_deg})")
    # NOTE: az_deg is in Subaru format (0 deg == South)
    if (-180.0 < az_deg <= 0) or (az_deg >= 180.0):
        # <-- object in EAST, offset should be POSITIVE (see NOTE above)
        if offset_deg < 0.0:
            offset_deg += 360.0
        # print(f"EAST OBJ, ADJ OFFSET ANGLE {offset_deg}")

    elif (0.0 < az_deg <= 180.0) or (az_deg <= -180.0):
        # <-- object in WEST, offset should be NEGATIVE (see NOTE above)
        if offset_deg > 0.0:
            offset_deg -= 360.0
        # print(f"WEST OBJ, ADJ OFFSET ANGLE {offset_deg}")

    else:
        raise ValueError(f"unhandled azimuth {az_deg} deg")

    alt_offset_deg = calc_alternate_angle(offset_deg)
    # print(f"OFFSET ANGLE={offset_deg}, ALT ANGLE {alt_offset_deg}")

    return offset_deg, alt_offset_deg
