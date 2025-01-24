#
# misc.py -- miscellaneous queue support functions
#
#  E. Jeschke
#
from datetime import timedelta

# 3rd party
import numpy as np

# local imports
from . import entity

# mount angle offsets for certain instruments
mount_offsets = dict(FOCAS=0.259, MOIRCS=45.0)
# whether PA should be flipped
mount_flip = dict(FOCAS=True, MOIRCS=True)


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
    time_sec = max(np.fabs(delta_el_deg) / rate_el,
                   np.fabs(delta_az_deg) / rate_az,
                   np.fabs(delta_rot_deg) / rate_rot)
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


def check_rotation_limits(rot_start, rot_stop, min_rot, max_rot):
    """Check rotation against limits.

    Parameters
    ----------
    rot_start : float or None
        Rotation start value

    rot_stop : float or None
        Rotation stop value

    min_rot : float
        Minimum rotation value

    max_rot : float
        Maximum rotation value

    Returns
    -------
    rot_ok : bool
        True if rotation is allowed, False otherwise
    """
    if None in (rot_start, rot_stop):
        rot_ok = False
    else:
        rot_ok = ((min_rot <= rot_start <= max_rot) and
                  (min_rot <= rot_stop <= max_rot))
    return rot_ok


def calc_optimal_rotation(rot1_start, rot1_stop, rot2_start, rot2_stop,
                          cur_rot, min_rot, max_rot):
    """Find optimal rotation, while checking against limits.

    Parameters
    ----------
    rot1_start : float or None
        Rotation possibility 1 start value

    rot1_stop : float or None
        Rotation possibility 1 stop value

    rot2_start : float or None
        Rotation possibility 2 start value

    rot2_stop : float or None
        Rotation possibility 2 stop value

    cur_rot : float
        Current rotation value

    min_rot : float
        Minimum rotation value

    max_rot : float
        Maximum rotation value

    Returns
    -------
    rot1_ok, rot2_ok : tuple of start and stop rotation values
        floats if rotation is allowed, None otherwise
    """
    rot1_ok = check_rotation_limits(rot1_start, rot1_stop, min_rot, max_rot)
    rot2_ok = check_rotation_limits(rot2_start, rot2_stop, min_rot, max_rot)

    if rot1_ok:
        if not rot2_ok:
            return rot1_start, rot1_stop

        # figure out which rotation would be the shorter distance
        # from the current location
        delta1 = np.fabs(cur_rot - rot1_start)
        delta2 = np.fabs(cur_rot - rot2_start)
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
    az_deg = normalize_angle(az_deg, limit='full', ang_offset=0.0)

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


def calc_rotator_offsets(cr, pa_deg, flip=False, ins_delta=0.0):
    """Calculate the effective instrument rotator offset.

    Parameters
    ----------
    cr : ~qplan.util.calcpos.CalculationResult
        Calculation result for target at a certain time

    pa_deg : float
        The desired position angle in degrees

    flip : bool (optional, defaults to False)
        Whether the image is flipped or not (depends on foci)

    ins_delta : float (optional, defaults to 0.0)
        Instrument mounting offset to apply

    Returns
    -------
    offset_deg : float
        The desirable rotator value for this observation
    """
    pang_deg = cr.pang_deg
    # offset_angle = parallactic_angle + position_angle
    offset_deg = pang_deg + pa_deg

    if flip:
        # non-mirror image, such as foci Cs, or NsOpt w/ImR
        offset_deg = -offset_deg

    offset_deg = offset_deg + ins_delta
    offset_deg = normalize_angle(offset_deg, limit='full')
    alt_offset_deg = calc_alternate_angle(offset_deg)

    return offset_deg, alt_offset_deg


def calc_possible_rotations(cr_start, cr_stop, pa_deg, ins_name):
    """Calculate the possible instrument rotations.

    Parameters
    ----------
    cr_start: ~qplan.util.calcpos.CalculationResult
        Calculation result for target at start of observation

    cr_stop: ~qplan.util.calcpos.CalculationResult
        Calculation result for target at stop of observation (end of exposure)

    pa_deg : float
        The desired position angle in degrees

    ins_name : str
        Instrument name

    Returns
    -------
    offset_deg : float
        The desirable rotator value for this observation
    """
    ins_delta = mount_offsets.get(ins_name, 0.0)
    ins_flip = mount_flip.get(ins_name, False)

    rot1_start_deg, rot2_start_deg = calc_rotator_offsets(cr_start, pa_deg,
                                                          flip=ins_flip,
                                                          ins_delta=ins_delta)
    rot1_stop_deg, rot2_stop_deg = calc_rotator_offsets(cr_stop, pa_deg,
                                                        flip=ins_flip,
                                                        ins_delta=ins_delta)
    return [(rot1_start_deg, rot1_stop_deg), (rot2_start_deg, rot2_stop_deg)]
