#
# qsim.py -- Observing Queue Planner
#
#  E. Jeschke
#
from datetime import timedelta

# 3rd party imports
import numpy as np

# Gen2 imports
from ginga.misc import Bunch

# local imports
from . import misc
from .util.eph_cache import populate_periods_mp

# maximum rank for a program
max_rank = 10.0

# minimum slot size in sec
minimum_slot_size = 60.0
#minimum_slot_size = 10.0

# telescope parked position
parked_az_deg = -90.0
parked_alt_deg = 90.0
parked_rot_deg = 0.0

# Subaru defines a dark night as one that is 2-3 days before or
# after a new moon (0%).  Since a half moon (50%) occurs just 7 days
# prior to a new moon, we can roughly calculate a dark night as
# being < 25% illumination
dark_night_moon_pct_limit = 0.25


def obs_to_slots(logger, slots, site, oblist, eph_cache, check_moon=False,
                 check_env=False):
    # populate ephemeris cache for the period
    unique_targets = set([ob.target for ob in oblist])
    tgt_dct = {target: target for target in unique_targets}
    periods = [(slot.start_time, slot.stop_time) for slot in slots]
    #eph_cache.populate_periods(tgt_dct, site, periods, keep_old=True)
    populate_periods_mp(eph_cache, tgt_dct, site, periods, keep_old=True)

    obmap = {}
    for slot in slots:
        #eph_cache.clear_all()
        key = str(slot)
        obmap[key] = []
        if slot.size() < minimum_slot_size:
            continue
        results = check_slot(site, None, slot, oblist, eph_cache,
                             check_moon=check_moon, check_env=check_env)
        good_obs = [res.ob for res in results if res.obs_ok]
        obmap[key].extend(good_obs)

        bad = list(filter(lambda res: not res.obs_ok, results))
        for res in bad:
            ob = res.ob
            ob_id = "%s/%s" % (ob.program, ob.name)
            logger.debug("OB %s (%s) no good for slot because: %s" % (
                ob, ob_id, res.reason))

    return obmap


def check_schedule_invariant_one(site, schedule, ob):

    res = Bunch.Bunch(ob=ob, obs_ok=False, reason="No good reason!")

    # check if instrument will be installed
    if not (ob.inscfg.insname in schedule.data.instruments):
        res.setvals(obs_ok=False, reason="Instrument '%s' not installed" % (
            ob.inscfg.insname))
        return res

    # check if filter will be installed (affected instruments only)
    if not ob.inscfg.check_filter_installed(schedule.data.filters):
        res.setvals(obs_ok=False, reason="Filter '%s' not installed [%s]" % (
            ob.inscfg.filter, schedule.data.filters))
        return res

    # check if this schedule can take this category
    if not ob.program.category in schedule.data.categories:
        res.setvals(obs_ok=False,
                    reason="Slot cannot take category '%s'" % (
            ob.program.category))
        return res

    res.setvals(obs_ok=True)
    return res


def check_schedule_invariant(site, schedule, oblist):
    good, bad, results = [], [], {}
    # TODO: chance for vectorization
    for ob in oblist:
        res = check_schedule_invariant_one(site, schedule, ob)
        results[ob] = res
        if res.obs_ok:
            good.append(ob)
        else:
            bad.append(ob)

    return good, bad, results


def check_night_visibility_one(site, schedule, ob, eph_cache):

    res = Bunch.Bunch(ob=ob, obs_ok=False, reason="No good reason!")

    if schedule.data.dome != ob.telcfg.dome:
        res.setvals(obs_ok=False, reason="Dome status OB(%s) != schedule(%s)" % (
            ob.telcfg.dome, schedule.data.dome))
        return res

    if ob.telcfg.dome == 'closed':
        res.setvals(obs_ok=True, reason="Dome is closed and this matches OB")
        return res

    min_el_deg, max_el_deg = ob.telcfg.get_el_minmax()

    # is this target visible during this night, and when?

    (obs_ok, t_start, t_stop) = eph_cache.observable(ob.target, ob.target, site,
                                                     schedule.start_time,
                                                     schedule.stop_time,
                                                     min_el_deg, max_el_deg,
                                                     ob.total_time)

    if not obs_ok:
        res.setvals(obs_ok=False,
                    reason="Time or visibility of target")
        return res

    res.setvals(obs_ok=obs_ok, start_time=t_start, stop_time=t_stop)
    return res


def check_night_visibility(site, schedule, oblist, eph_cache):
    good, bad, results = [], [], {}
    for ob in oblist:
        res = check_night_visibility_one(site, schedule, ob, eph_cache)
        results[str(ob)] = res
        if res.obs_ok:
            good.append(ob)
        else:
            bad.append(ob)

    return good, bad, results


def check_moon_cond(eph_start, eph_stop, ob, res):
    """Check whether the moon is at acceptable darkness for this OB
    and an acceptable distance from the target.
    """
    # is this a dark night? check moon illumination
    is_dark_night = eph_start.moon_pct <= dark_night_moon_pct_limit

    desired_moon_sep = ob.envcfg.moon_sep

    # if the moon is down for entire exposure, override illumination
    # and consider this a dark night
    moon_is_down = False
    horizon_deg = 0.0   # change as necessary
    if (eph_start.moon_alt < horizon_deg) and (eph_stop.moon_alt < horizon_deg):
        moon_is_down = True

    # if observer specified a moon phase, check it now
    if ob.envcfg.moon == 'dark':
        if not (is_dark_night or moon_is_down):
            res.setvals(obs_ok=False,
                        reason="Moon illumination=%f not acceptable (alt 1=%.2f 2=%.2f" % (
                eph_start.moon_pct, eph_start.moon_alt, eph_stop.moon_alt))
            return False

    # NOTE: change in HSC queue policy regarding override (2021/02...EJ)
    # override the observer's desired separation if moon is below the horizon
    if (desired_moon_sep is not None) and moon_is_down:
        limit_sep = min(30.0, desired_moon_sep)
        desired_moon_sep = min(desired_moon_sep, limit_sep)
        if desired_moon_sep < ob.envcfg.moon_sep:
            res.setvals(override="overrode moon separation (%.2f) -> %.2f deg" % (
                ob.envcfg.moon_sep, desired_moon_sep))

    # if observer specified a moon separation from target, check it now
    if desired_moon_sep is not None:
        if ((eph_start.moon_sep < desired_moon_sep) or
            (eph_stop.moon_sep < desired_moon_sep)):
            res.setvals(obs_ok=False,
                        reason="Moon-target separation (%f,%f < %f) not acceptable" % (
                eph_start.moon_sep, eph_stop.moon_sep, desired_moon_sep))
            return False

    # moon looks good!
    return True


def check_slot(site, schedule, slot, oblist, eph_cache,
               check_moon=True, check_env=True, limit_filter=None, allow_delay=True):

    res_lst = []
    for ob in oblist:
        res = Bunch.Bunch(ob=ob, obs_ok=False, reason="No good reason!")

        # Check whether OB will fit in this slot
        delta = (slot.stop_time - slot.start_time).total_seconds()
        if ob.total_time > delta:
            res.setvals(obs_ok=False,
                        reason="Slot duration (%d) too short for OB (%d)" % (
                delta, ob.total_time))
            res_lst.append(res)
            continue

        # Check time limits on OB
        if (ob.envcfg.lower_time_limit is not None and
            ob.envcfg.lower_time_limit > slot.stop_time):
            res.setvals(obs_ok=False,
                        reason="Slot end time is before OB lower time limit")
            res_lst.append(res)
            continue

        if (ob.envcfg.upper_time_limit is not None and
            ob.envcfg.upper_time_limit < slot.start_time):
            res.setvals(obs_ok=False,
                        reason="Slot start time is after OB upper time limit")
            res_lst.append(res)
            continue

        # NOTE: these are now checked pre-scheduling for unschedulable OBs
        ## # check if instrument will be installed
        ## if not (ob.inscfg.insname in slot.data.instruments):
        ##     res.setvals(obs_ok=False, reason="Instrument '%s' not installed" % (
        ##         ob.inscfg.insname))
        ##     res_lst.append(res)
        ##     continue

        ## # check if filter will be installed
        ## if not ob.inscfg.check_filter_installed(slot.data.filters):
        ##     res.setvals(obs_ok=False, reason="Filter '%s' not installed [%s]" % (
        ##         ob.inscfg.filter, slot.data.filters))
        ##     res_lst.append(res)
        ##     continue

        ## # check if this slot can take this category
        ## if not ob.program.category in slot.data.categories:
        ##     res.setvals(obs_ok=False,
        ##                 reason="Slot cannot take category '%s'" % (
        ##         ob.program.category))
        ##     res_lst.append(res)
        ##     continue

        # if we are limiting the filter to a certain one
        if (limit_filter is not None and
            not ob.inscfg.check_filter_installed([limit_filter])):
            res.setvals(obs_ok=False,
                        reason="Filter (%s) does not match limit_filter (%s)" % (
                ob.inscfg.filter, limit_filter))
            res_lst.append(res)
            continue

        filterchange = False
        filterchange_sec = 0.0

        # get current filter
        if schedule is None:
            cur_filter = getattr(slot.data, 'cur_filter', None)

        else:
            cur_filter = schedule.data.get('cur_filter', None)

        # calculate cost of filter exchange
        if hasattr(ob.inscfg, 'filter') and cur_filter != ob.inscfg.filter:
            # filter exchange necessary
            filterchange = True
            filterchange_sec = ob.inscfg.calc_filter_change_time()

        # for adding up total preparation time for new OB
        prep_sec = filterchange_sec + ob.setup_time()

        # check dome status
        if slot.data.dome != ob.telcfg.dome:
            res.setvals(obs_ok=False, reason="Dome status OB(%s) != slot(%s)" % (
                ob.telcfg.dome, slot.data.dome))
            res_lst.append(res)
            continue

        start_time = slot.start_time + timedelta(seconds=prep_sec)

        if slot.data.dome == 'closed':
            # <-- dome closed

            stop_time = start_time + timedelta(seconds=ob.total_time)

            # Check whether OB will fit in this slot
            if slot.stop_time < stop_time:
                res.setvals(obs_ok=False, reason="Not enough time in slot")
                res_lst.append(res)
                continue

            res.setvals(obs_ok=True,
                        prep_sec=prep_sec, slew_sec=0.0,
                        filterchange=filterchange,
                        filterchange_sec=filterchange_sec,
                        start_time=start_time, stop_time=stop_time,
                        delay_sec=0.0)
            res_lst.append(res)
            continue

        # <-- dome open, need to check visibility and other criteria

        if check_env:
            # check seeing on the slot is acceptable to this ob
            if (slot.data.seeing > ob.envcfg.seeing):
                res.setvals(obs_ok=False,
                            reason="Seeing (%f > %f) not acceptable" % (
                    slot.data.seeing, ob.envcfg.seeing))
                res_lst.append(res)
                continue

            # check sky condition on the slot is acceptable to this ob
            if ob.envcfg.transparency is not None:
                if slot.data.transparency < ob.envcfg.transparency:
                    res.setvals(obs_ok=False,
                                reason="Transparency (%f < %f) not acceptable" % (
                        slot.data.transparency, ob.envcfg.transparency))
                    res_lst.append(res)
                    continue

        # get telescope position as left at the end of the previous slot
        if slot.data.cur_az is not None:
            # ... current telescope position
            cur_alt_deg, cur_az_deg = slot.data.cur_el, slot.data.cur_az
            cur_rot_deg = slot.data.cur_rot
        elif schedule.data.cur_az is not None:
            # ... current telescope position
            cur_alt_deg, cur_az_deg = schedule.data.cur_el, schedule.data.cur_az
            cur_rot_deg = schedule.data.cur_rot
        else:
            # ... parked position
            cur_alt_deg, cur_az_deg = parked_alt_deg, parked_az_deg
            cur_rot_deg = parked_rot_deg

        # get limits for telescope movements from telescope configuration
        min_el_deg, max_el_deg = ob.telcfg.get_el_minmax()
        min_az_deg, max_az_deg = ob.telcfg.get_az_minmax()
        min_rot_deg, max_rot_deg = ob.telcfg.get_rot_minmax()

        # Check whether OB will fit in this slot
        ## delta = (slot.stop_time - start_time).total_seconds()
        ## if ob.total_time > delta:
        ##     return False

        # find the time that this object begins to be visible
        # TODO: figure out the best place to split the slot
        (obs_ok, t_start, t_stop) = eph_cache.observable(ob.target, ob.target, site,
                                                         start_time, slot.stop_time,
                                                         min_el_deg, max_el_deg,
                                                         ob.total_time)

        if not obs_ok:
            res.setvals(obs_ok=False,
                        reason="Time or visibility of target")
            res_lst.append(res)
            continue

        # calculate delay until we could actually start observing the object
        # in this slot
        if ob.envcfg.lower_time_limit is not None:
            t_start = max(t_start, ob.envcfg.lower_time_limit)

        delay_sec = max(0.0, (t_start - start_time).total_seconds())

        # if we are disallowing any delays
        if not allow_delay and delay_sec > 0.0:
            res.setvals(obs_ok=False,
                        reason="no_delay==True and OB has a delay of %.4f sec" % (
                delay_sec))
            res_lst.append(res)
            continue

        # Calculate cost of slew to this target
        start_time = t_start
        eph_start = eph_cache.get_closest(ob.target, start_time)
        stop_time = start_time + timedelta(seconds=ob.total_time)
        eph_stop = eph_cache.get_closest(ob.target, stop_time)

        # calculate possible azimuth moves
        dec_deg = ob.target.dec
        obs_lat_deg = site.lat_deg

        az_choices = misc.calc_possible_azimuths(dec_deg, eph_start.az_deg,
                                                 eph_stop.az_deg, obs_lat_deg,
                                                 az_min_deg=min_az_deg,
                                                 az_max_deg=max_az_deg)
        if len(az_choices) == 0:
            res.setvals(obs_ok=False, reason="Azimuth would go past limit")
            res_lst.append(res)
            continue
        elif len(az_choices) == 1:
            az_start, az_stop = az_choices[0]
            if not misc.check_rotation_limits(az_start, az_stop,
                                              min_az_deg, max_az_deg):
                res.setvals(obs_ok=False, reason="Azimuth would go past limit")
                res_lst.append(res)
                continue
        elif len(az_choices) == 2:
            # calculate optimal azimuth move
            az1_start_deg, az1_stop_deg = az_choices[0]
            az2_start_deg, az2_stop_deg = az_choices[1]
            # NOTE: checks limits
            az_start, az_stop = misc.calc_optimal_rotation(az1_start_deg,
                                                           az1_stop_deg,
                                                           az2_start_deg,
                                                           az2_stop_deg,
                                                           cur_az_deg,
                                                           min_az_deg, max_az_deg)
            if np.nan in (az_start, az_stop):
                res.setvals(obs_ok=False, reason="Azimuth would go past limit")
                res_lst.append(res)
                continue

        # calculate optimal rotator position
        pa_deg = ob.inscfg.pa
        ins_name = ob.inscfg.insname
        rot_choices = misc.calc_possible_rotations(eph_start.pang_deg,
                                                   eph_stop.pang_deg,
                                                   pa_deg, ins_name,
                                                   eph_start.az_deg,
                                                   eph_stop.az_deg)
        rot1_start_deg, rot1_stop_deg, rot1_offset_deg = rot_choices[0]
        rot2_start_deg, rot2_stop_deg, rot2_offset_deg = rot_choices[1]
        rot_start, rot_stop = misc.calc_optimal_rotation(rot1_start_deg,
                                                         rot1_stop_deg,
                                                         rot2_start_deg,
                                                         rot2_stop_deg,
                                                         cur_rot_deg,
                                                         min_rot_deg, max_rot_deg)
        if np.isnan(rot_start) or np.isnan(rot_stop):
            res.setvals(obs_ok=False, reason="Rotator would go past limit")
            res_lst.append(res)
            continue

        # calculate slewing time to new target
        slew_sec = misc.calc_slew_time(cur_alt_deg, cur_az_deg, cur_rot_deg,
                                       eph_start.alt_deg, az_start, rot_start)

        prep_sec += slew_sec
        # adjust on-target start time to account for slewing/rotator
        start_time += timedelta(seconds=slew_sec)

        # calculate necessary stop time for exposures plus overheads
        stop_time = (start_time + timedelta(seconds=ob.total_time) +
                     timedelta(seconds=ob.teardown_time()))

        if ob.envcfg.upper_time_limit is not None:
            t_stop = min(ob.envcfg.upper_time_limit, t_stop)

        t_stop = min(t_stop, slot.stop_time)

        if t_stop < stop_time:
            res.setvals(obs_ok=False,
                        reason="Not enough time in slot after all prep/delay")
            res_lst.append(res)
            continue

        # check moon constraints between start and stop time
        if check_moon:
            eph_start = eph_cache.get_closest(ob.target, start_time)
            eph_stop = eph_cache.get_closest(ob.target, stop_time)
            obs_ok = check_moon_cond(eph_start, eph_stop, ob, res)
        else:
            obs_ok = True

        res.setvals(obs_ok=obs_ok,
                    prep_sec=prep_sec, slew_sec=slew_sec,
                    filterchange=filterchange,
                    filterchange_sec=filterchange_sec,
                    start_time=start_time, stop_time=stop_time,
                    az_start=az_start, az_stop=az_stop,
                    alt_start=eph_start.alt_deg, alt_stop=eph_stop.alt_deg,
                    rot_start=rot_start, rot_stop=rot_stop,
                    delay_sec=delay_sec)
        res_lst.append(res)

    return res_lst


def eval_schedule(schedule, current_filter=None):

    current_filter = current_filter
    num_filter_exchanges = 0
    time_waste_sec = 0.0
    proposal_total_time_sec = {}

    for slot in schedule.slots:
        ob = slot.ob
        # TODO: fix up a more solid check for delays
        if (ob is None) or ob.comment.startswith('Delay'):
            delta = (slot.stop_time - slot.start_time).total_seconds()
            time_waste_sec += delta
            continue
        else:
            propID = str(ob.program)
            if propID in proposal_total_time_sec:
                proposal_total_time_sec[propID] += ob.total_time
            else:
                proposal_total_time_sec[propID] = ob.total_time

        _filter = getattr(ob.inscfg, 'filter', None)
        if ((_filter is not None) and
            (ob.inscfg.filter != current_filter)):
            num_filter_exchanges += 1
            current_filter = ob.inscfg.filter

    res = Bunch.Bunch(num_filter_exchanges=num_filter_exchanges,
                      time_waste_sec=time_waste_sec,
                      proposal_total_time_sec=proposal_total_time_sec)
    return res


# END
