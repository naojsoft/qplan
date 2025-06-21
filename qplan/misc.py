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

    Parameters
    ----------
    ang_deg : float or array of float
        The input angle(s) in degrees

    Returns
    -------
    alt_deg : float or array of float
        The output angle(s) in degrees
    """
    alt_deg = ang_deg - np.sign(ang_deg) * 360
    return alt_deg


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


def check_rotation_limits(rot_start, rot_stop, min_rot, max_rot):
    """Check rotation against limits.

    Parameters
    ----------
    rot_start : float or NaN
        Rotation start value

    rot_stop : float or NaN
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
    if np.isnan(rot_start) or np.isnan(rot_stop):
        rot_ok = False
    else:
        rot_ok = ((min_rot <= rot_start <= max_rot) and
                  (min_rot <= rot_stop <= max_rot))
    return rot_ok


def calc_optimal_rotation(left_start_deg, left_stop_deg,
                          right_start_deg, right_stop_deg,
                          cur_rot_deg, min_rot_deg, max_rot_deg):
    """Find optimal rotation, while checking against limits.

    Parameters
    ----------
    left_start_deg : float, NaNs ok
        Rotation possibility 1 start value

    left_stop_deg : float, NaNs ok
        Rotation possibility 1 stop value

    right_start_deg : float, NaNs ok
        Rotation possibility 2 start value

    right_stop_deg : float, NaNs ok
        Rotation possibility 2 stop value

    cur_rot_deg : float
        Current rotation value

    min_rot_deg : float
        Minimum rotation value

    max_rot_deg : float
        Maximum rotation value

    Returns
    -------
    rot1_ok, rot2_ok : tuple of start and stop rotation values
        floats if rotation is allowed, NaN otherwise
    """
    left_ok = check_rotation_limits(left_start_deg, left_stop_deg,
                                    min_rot_deg, max_rot_deg)
    right_ok = check_rotation_limits(right_start_deg, right_stop_deg,
                                     min_rot_deg, max_rot_deg)

    if left_ok:
        if not right_ok:
            return left_start_deg, left_stop_deg

        # figure out which rotation would be the shorter distance
        # from the current location
        delta_l = np.fabs(cur_rot_deg - left_start_deg)
        delta_r = np.fabs(cur_rot_deg - right_start_deg)
        if delta_l < delta_r:
            return left_start_deg, left_stop_deg
        return right_start_deg, right_stop_deg

    elif right_ok:
        return right_start_deg, right_stop_deg
    else:
        return np.nan, np.nan


def calc_subaru_azimuths(az_deg):
    """Calculate Subaru (0 deg == South) azimuth possibilities.

    Parameters
    ----------
    az_deg: float
        A traditional azimuth value where 0 deg == North

    Returns
    -------
    (naz_deg, paz_deg): tuple of float or NaN
        possible translated azimuths (0 deg == South), one of them may be NaN

    NOTE: naz_deg is always in the negative direction, paz_deg in the positive
    """
    # limit angle to 0 <= az_deg < 360.0
    az_deg = normalize_angle(az_deg, limit='full', ang_offset=0.0)

    if 0.0 <= az_deg <= 90.0:
        naz_deg = - (180.0 - az_deg)
        paz_deg = 180.0 + az_deg
    elif 90.0 < az_deg < 180.0:
        naz_deg = - (180.0 - az_deg)
        paz_deg = np.nan
    elif 180.0 < az_deg < 270.0:
        naz_deg = np.nan
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


def calc_possible_azimuths(dec_deg, az_start_deg, az_stop_deg, obs_lat_deg):
    """Calculate possible azimuth moves.

    Parameters
    ----------
    dec_deg : float
        Declination of target in degrees

    az_start_deg: float
        azimuth for target at start of observation

    az_stop_deg: float
        azimuth for target at stop of observation (end of exposure)

    obs_lat_deg: float
        Observers latitude in degrees

    Returns
    -------
    az_choices : list of (float, float) tuples
        List of possible azimuth start and stops in Subaru (S==0 deg) coordinates
    """
    # circumpolar_deg_limit = 90.0 - obs_lat_deg
    # if dec_deg > circumpolar_deg:
    #     # target in North for whole range
    #     # circumpolar orbit, object may go E to W or W to E
    #     # 2 az directions are possible
    #     if cr1.ha < cr2.ha:
    #         # object moving E to W
    #         pass
    #     else:
    #         # object moving W to E
    #         pass

    # NOTE: this "fudge factor" was added because some objects azimuth
    # as calculated by the ephemeris engine fall outside of the expected
    # ranges--this hopefully allows us to ensure that we can test whether
    # a target is will be truly in the North or South only
    fudge_factor_deg = 0.1

    if dec_deg > obs_lat_deg + fudge_factor_deg:
        # target in North for whole range
        # 2 az directions are possible
        naz_deg_start, paz_deg_start = calc_subaru_azimuths(az_start_deg)

        if not (-270.0 <= naz_deg_start <= -90.0):
            raise ValueError(f"AZ(neg) start value ({naz_deg_start}) out of range for target in North")
        if not (90.0 <= paz_deg_start <= 270.0):
            raise ValueError(f"AZ(pos) start value ({paz_deg_start}) out of range for target in North")

        naz_deg_stop, paz_deg_stop = calc_subaru_azimuths(az_stop_deg)

        if not (-270.0 <= naz_deg_stop <= -90.0):
            raise ValueError(f"AZ(neg) stop value ({naz_deg_stop}) out of range for target in North")
        if not (90.0 <= paz_deg_stop <= 270.0):
            raise ValueError(f"AZ(pos) stop value ({paz_deg_stop}) out of range for target in North")

        return [(naz_deg_start, naz_deg_stop), (paz_deg_start, paz_deg_stop)]

    elif dec_deg < 0.0 - fudge_factor_deg:
        # target in South for whole range
        # only 1 az direction is possible

        naz_deg_start, paz_deg_start = calc_subaru_azimuths(az_start_deg)
        naz_deg_stop, paz_deg_stop = calc_subaru_azimuths(az_stop_deg)

        if not np.isnan(naz_deg_start):
            # <-- target in SE
            if not np.isnan(paz_deg_start):
                raise ValueError(f"target in SE has two AZ start values ({naz_deg_start},{paz_deg_start})")
            if not np.isnan(naz_deg_stop):
                # <-- target finishes in SE
                return [(naz_deg_start, naz_deg_stop)]
            else:
                # <-- target finishes in SW
                return [(naz_deg_start, paz_deg_stop)]
        else:
            # <-- target in SW
            if np.isnan(paz_deg_stop):
                raise ValueError(f"target in SW has no AZ stop value ({paz_deg_stop})")
            if not np.isnan(naz_deg_stop):
                raise ValueError(f"target in SW has neg AZ stop value ({naz_deg_stop})")
            return [(paz_deg_start, paz_deg_stop)]

    else:
        # target could be in N and may dip S, depending on start or exp time
        # 2 az directions are possible if target stays in N
        # else only 1 az direction is possible
        start_quad = get_quadrant(az_start_deg)
        stop_quad = get_quadrant(az_stop_deg)

        naz_deg_start, paz_deg_start = calc_subaru_azimuths(az_start_deg)
        naz_deg_stop, paz_deg_stop = calc_subaru_azimuths(az_stop_deg)

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


def calc_offset_angle(pang_deg, pa_deg, flip=False, ins_delta=0.0):
    """Calculate the instrument rotator offset.

    NOTE: DOES NOT NORMALIZE THE ANGLES

    Parameters
    ----------
    pang_deg : float
        Parallactic angle for target at a certain time

    pa_deg : float
        The desired position angle in degrees

    flip : bool (optional, defaults to False)
        Whether the image is flipped or not (depends on foci)

    ins_delta : float (optional, defaults to 0.0)
        Instrument mounting offset to apply

    Returns
    -------
    offset_deg : float
        The rotator offset value for this observation
    """
    # offset_angle = parallactic_angle + position_angle
    offset_deg = pang_deg + pa_deg

    if flip:
        # non-mirror image, such as foci Cs, or NsOpt w/ImR
        offset_deg = -offset_deg

    offset_deg = offset_deg + ins_delta
    return offset_deg


def calc_possible_rotations(start_pang_deg, stop_pang_deg, pa_deg, ins_name,
                            dec_deg, obs_lat_deg):
    """Calculate the possible instrument rotations.

    Parameters
    ----------
    start_pang_deg : float
        Parallactic angle for target at start of observation

    stop_pang_deg : float
        Parallactic angle for target at stop of observation (end of exposure)

    pa_deg : float
        The desired position angle in degrees

    ins_name : str
        Instrument name

    dec_deg : float
        Declination of target in degrees

    ob_lat_deg : float
        Observers latitude in degrees

    Returns
    -------
    possible_rots : array of (float, float)
        The rotator offset angles for this parallactic angle

    NOTE: the possibilities are not guaranteed to be achievable.
    They should be further checked against limits.
    """
    ins_delta = mount_offsets.get(ins_name, 0.0)
    ins_flip = mount_flip.get(ins_name, False)

    is_north = dec_deg > obs_lat_deg

    if is_north and np.sign(start_pang_deg) != np.sign(stop_pang_deg):
        # north target has a discontinuity in parallactic angle as the target
        # passes through the meridian.  If sign is different for a northerly
        # target, then we need to calculate the alternate angle to calculate
        # the correct direction of rotation
        stop_pang_deg = calc_alternate_angle(stop_pang_deg)

    start_offset_deg = calc_offset_angle(start_pang_deg, pa_deg, flip=ins_flip,
                                         ins_delta=ins_delta)
    stop_offset_deg = calc_offset_angle(stop_pang_deg, pa_deg, flip=ins_flip,
                                        ins_delta=ins_delta)

    rot_diff = stop_offset_deg - start_offset_deg
    # sign of this should indicate the direction of the rotation
    # rot_sign = np.sign(rot_diff)

    # normalize angles to (-360, +360)
    left_start_deg = normalize_angle(start_offset_deg, limit=None)
    left_stop_deg = left_start_deg + rot_diff

    right_start_deg = calc_alternate_angle(left_start_deg)
    right_stop_deg = right_start_deg + rot_diff

    return np.array([(left_start_deg, left_stop_deg),
                     (right_start_deg, right_stop_deg)])
