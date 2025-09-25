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
# Rotation limits
rot_limits = dict(PFS=(-174.0, 174.0))


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
    alt_deg = ang_deg - np.sign(ang_deg) * 360.0
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
        normalize_angle(ang_deg, limit='half', ang_offset=-180.0)
    """
    # convert to array if just a scalar
    is_array = isinstance(ang_deg, np.ndarray)
    if not is_array:
        ang_deg = np.array([ang_deg], dtype=float)

    ang_deg = (ang_deg + ang_offset).astype(float)

    # constrain to -360, +360
    mask = np.fabs(ang_deg) >= 360.0
    ang_deg[mask] = np.remainder(ang_deg[mask], np.sign(ang_deg[mask]) * 360.0)
    if limit is not None:
        # constrain to 0, +360
        mask = ang_deg < 0.0
        ang_deg[mask] += 360.0
        if limit == 'half':
            # constrain to -180, +180
            mask = ang_deg > 180.0
            ang_deg[mask] -= 360.0

    if not is_array:
        # extract scalar
        ang_deg = ang_deg[0]

    return ang_deg


def check_rotation_limits(rot_start_deg, rot_stop_deg, min_rot_deg, max_rot_deg):
    """Check rotation against limits.

    Parameters
    ----------
    rot_start : float or array of float, NaNs ok
        Rotation start value(s). NaN indicates a non-available angle.

    rot_stop : float or array of float, NaNs ok
        Rotation stop value(s). NaN indicates a non-available angle.

    min_rot_deg : float
        Minimum rotation value

    max_rot_deg : float
        Maximum rotation value

    Returns
    -------
    rot_ok : bool
        True if rotation is allowed, False otherwise
    """
    is_array = isinstance(rot_start_deg, np.ndarray)
    if not is_array:
        rot_start_deg = np.array([rot_start_deg], dtype=float)
        rot_stop_deg = np.array([rot_stop_deg], dtype=float)

    rot_ok = np.logical_and(np.isfinite(rot_start_deg),
                            np.isfinite(rot_stop_deg))
    rot_ok = np.logical_and(rot_ok, min_rot_deg <= rot_start_deg)
    rot_ok = np.logical_and(rot_ok, rot_start_deg <= max_rot_deg)
    rot_ok = np.logical_and(rot_ok, min_rot_deg <= rot_stop_deg)
    rot_ok = np.logical_and(rot_ok, rot_stop_deg <= max_rot_deg)

    if not is_array:
        rot_ok = rot_ok[0]
    return rot_ok


def calc_optimal_rotation(left_start_deg, left_stop_deg,
                          right_start_deg, right_stop_deg,
                          cur_rot_deg, min_rot_deg, max_rot_deg):
    """Find optimal rotation, while checking against limits.

    Parameters
    ----------
    left_start_deg : float array of float, NaNs ok
        Rotation possibility 1 start value(s)

    left_stop_deg : float or array of float, NaNs ok
        Rotation possibility 1 stop value(s)

    right_start_deg : float or array of float, NaNs ok
        Rotation possibility 2 start value(s)

    right_stop_deg : float or array of float, NaNs ok
        Rotation possibility 2 stop value(s)

    cur_rot_deg : float
        Current rotation value

    min_rot_deg : float
        Minimum rotation value

    max_rot_deg : float
        Maximum rotation value

    Returns
    -------
    rot_start, rot_stop : start and stop rotation values
        floats if rotation is allowed, NaN otherwise
    """
    left_ok = check_rotation_limits(left_start_deg, left_stop_deg,
                                    min_rot_deg, max_rot_deg)
    right_ok = check_rotation_limits(right_start_deg, right_stop_deg,
                                     min_rot_deg, max_rot_deg)

    is_array = isinstance(left_start_deg, np.ndarray)
    if not is_array:
        left_start_deg = np.array([left_start_deg], dtype=float)
        left_stop_deg = np.array([left_stop_deg], dtype=float)

    res_start = np.full_like(left_start_deg, np.nan)
    res_stop = np.full_like(left_stop_deg, np.nan)
    idx = np.arange(len(res_start), dtype=int)

    both_ok = np.logical_and(left_ok, right_ok)
    if np.any(both_ok):
        delta_l = np.fabs(cur_rot_deg - left_start_deg[both_ok])
        delta_r = np.fabs(cur_rot_deg - right_start_deg[both_ok])
        favor_l = delta_l < delta_r
        res_start[both_ok] = np.where(favor_l,
                                      left_start_deg[both_ok],
                                      right_start_deg[both_ok])
        res_stop[both_ok] = np.where(favor_l,
                                     left_stop_deg[both_ok],
                                     right_stop_deg[both_ok])

    just_left_ok = np.logical_and(left_ok, np.logical_not(right_ok))
    if np.any(just_left_ok):
        res_start[just_left_ok] = left_start_deg[just_left_ok]
        res_stop[just_left_ok] = left_stop_deg[just_left_ok]

    just_right_ok = np.logical_and(np.logical_not(left_ok), right_ok)
    if np.any(just_right_ok):
        res_start[just_right_ok] = right_start_deg[just_right_ok]
        res_stop[just_right_ok] = right_stop_deg[just_right_ok]

    if not is_array:
        # extract scalars
        res_start, res_stop = res_start[0], res_stop[0]

    return np.array([res_start, res_stop])


def is_north_az(az_deg):
    """Return True if azimuth is in 'north' range.

    Parameters
    ----------
    az_deg: float
        azimuth for target (N == 0 deg)

    Returns
    -------
    tf : bool
        True if azimuth is in the North

    """
    az = normalize_angle(az_deg, limit='half')
    return np.abs(az) < 90.0


def calc_possible_azimuths(dec_deg, az_start_deg, az_stop_deg, obs_lat_deg,
                           az_min_deg=-270.0, az_max_deg=+270.0):
    """Calculate possible azimuth moves.

    Parameters
    ----------
    dec_deg : float
        Declination of target in degrees

    az_start_deg: float
        azimuth for target at start of observation (N == 0 deg)

    az_stop_deg: float
        azimuth for target at stop of observation (N == 0 deg, end of exposure)

    obs_lat_deg: float
        Observers latitude in degrees

    az_min_deg : float (optional, defaults to -270.0)
        Minimum azimuth position

    az_max_deg : float (optional, defaults to +270.0)
        Maximum azimuth position

    Returns
    -------
    az_choices : list of (float, float) tuples
        List of possible azimuth start and stops in Subaru (S==0 deg) coordinates
    """
    # convert to Subaru azimuths in the range -180 to +180
    az_start_deg = normalize_angle(az_start_deg, limit='half', ang_offset=-180)
    az_stop_deg = normalize_angle(az_stop_deg, limit='half', ang_offset=-180)

    # Determine if the object is in the south or crosses the zenith
    traverses_south = (dec_deg < obs_lat_deg) and \
        (az_stop_deg > -90.0 and az_start_deg < 90.0)

    # Compute both motion paths
    # delta = signed_delta(az_start_deg % 360, az_stop_deg % 360)
    delta = normalize_angle(az_stop_deg, limit='full') - \
        normalize_angle(az_start_deg, limit='full')

    # First candidate: direct motion
    first_path = (az_start_deg, az_start_deg + delta)

    # Second candidate: alternate path (opposite direction)
    az_start2 = calc_alternate_angle(az_start_deg)
    second_path = (az_start2, az_start2 + delta)

    # If target crosses into the south, there is only one possible az move
    if traverses_south:
        candidates = [(az_start_deg, az_stop_deg)]

    else:
        candidates = [first_path, second_path]

    # Filter paths within az move limits
    result = [(start, stop) for start, stop in candidates
              if (az_min_deg <= start <= az_max_deg and
                  az_min_deg <= stop <= az_max_deg)]
    return result


def calc_rotator_angle(pang_deg, pa_deg, flip=False, ins_delta=0.0):
    """Calculate the instrument rotator offset.

    NOTE: DOES NOT NORMALIZE THE ANGLES

    Parameters
    ----------
    pang_deg : float or array of float
        Parallactic angle for target(s) at a certain time

    pa_deg : float or array of float
        The desired position angle(s) in degrees

    flip : bool (optional, defaults to False)
        Whether the image is flipped or not (depends on foci)

    ins_delta : float (optional, defaults to 0.0)
        Instrument mounting offset to apply

    Returns
    -------
    rot_deg, off_deg : tuple of (float, float)
        The rotator value and offset angle for this observation
    """
    if flip:
        # non-mirror image, such as foci Cs, or NsOpt w/ImR
        pa_deg = -pa_deg

    # rotator_angle = parallactic_angle + position_angle
    rot_deg = pang_deg + pa_deg + ins_delta

    return rot_deg, pa_deg + ins_delta


def unwrap_angle(ref_angle_deg, angle_deg):
    """Unwrap `angle_deg` relative to `ref_angle_deg` to minimize discontinuity."""
    delta_deg = (angle_deg - ref_angle_deg + 180) % 360 - 180
    return ref_angle_deg + delta_deg


def compute_rotator_angles(pang_start_deg, pang_stop_deg, pa_deg,
                           az_start_deg, az_stop_deg,
                           flip=False, ins_delta=0.0):
    """
    Compute the rotator start and stop angles.

    Parameters
    ----------
    pang_deg_start : float or array of float
        Parallactic angle for target(s) at start of observation

    pang_deg_stop : float or array of float
        Parallactic angle for target(s) at stop of observation (end of exposure)

    pa_deg : float or array of float
        The desired position angle(s) in degrees

    az_start_deg: float
        azimuth for target at start of observation (N == 0 deg)

    az_stop_deg: float
        azimuth for target at stop of observation (N == 0 deg, end of exposure)

    flip : bool (optional, defaults to False)
        Whether the image is flipped or not (depends on foci)

    ins_delta : float (optional, defaults to 0.0)
        Instrument mounting offset to apply

    Returns
    -------
    rot_res : tuple of (float, float, float)
        A tuple of the rotator start angle, stop angle and offset angle
    """
    # Compute raw rotator positions
    rot_start, off_deg = calc_rotator_angle(pang_start_deg, pa_deg, flip=flip,
                                            ins_delta=ins_delta)
    rot_end, _na = calc_rotator_angle(pang_stop_deg, pa_deg, flip=flip,
                                      ins_delta=ins_delta)
    rot_start = normalize_angle(rot_start, limit=None)

    # Detect zenith crossing
    crossed_zenith = is_north_az(az_start_deg) != is_north_az(az_stop_deg)
    # Apply 180 deg flip if needed
    add_180 = np.multiply(crossed_zenith, 180.0)
    rot_end = unwrap_angle(rot_start, rot_end + add_180)
    rot_end = normalize_angle(rot_end, limit=None)

    return rot_start, rot_end, off_deg


def calc_possible_rotations(pang_start_deg, pang_stop_deg, pa_deg, ins_name,
                            az_start_deg, az_stop_deg):
    """Calculate the possible instrument rotations.

    Parameters
    ----------
    pang_deg_start : float or array of float
        Parallactic angle for target(s) at start of observation

    pang_deg_stop : float or array of float
        Parallactic angle for target(s) at stop of observation (end of exposure)

    pa_deg : float or array of float
        The desired position angle(s) in degrees

    ins_name : str
        Instrument name

    az_start_deg: float
        azimuth for target at start of observation (N == 0 deg)

    az_stop_deg: float
        azimuth for target at stop of observation (N == 0 deg, end of exposure)

    Returns
    -------
    possible_rots : array of (float, float)
        The rotator offset angles for this parallactic angle

    NOTE: the possibilities are not guaranteed to be achievable.
    They should be further checked against limits.
    """
    ins_delta = mount_offsets.get(ins_name, 0.0)
    ins_flip = mount_flip.get(ins_name, False)

    left_start_deg, left_stop_deg, left_offset_deg = \
        compute_rotator_angles(pang_start_deg, pang_stop_deg,
                               pa_deg, az_start_deg, az_stop_deg,
                               flip=ins_flip, ins_delta=ins_delta)
    rot_diff = left_stop_deg - left_start_deg

    right_start_deg = calc_alternate_angle(left_start_deg)
    right_stop_deg = right_start_deg + rot_diff
    right_offset_deg = calc_alternate_angle(left_offset_deg)

    return np.array([(left_start_deg, left_stop_deg, left_offset_deg),
                     (right_start_deg, right_stop_deg, right_offset_deg)])
