#! /usr/bin/env python
#
# qsim.py -- Observing Queue Planner
#
#  Eric Jeschke (eric@naoj.org)
#
from datetime import timedelta
import time

# Gen2 imports
from ginga.misc import Bunch

# local imports
import misc
#import constraints
import entity


# maximum rank for a program
max_rank = 10.0

# minimum slot size in sec
minimum_slot_size = 60.0
#minimum_slot_size = 10.0

# telescope parked position
parked_az_deg = -90.0
parked_alt_deg = 90.0

# Subaru defines a dark night as one that is 2-3 days before or
# after a new moon (0%).  Since a half moon (50%)occurs just 7 days
# prior to a new moon, we can roughly calculate a dark night as
# being < 25% illumination
dark_night_moon_pct_limit = 0.25


def filterchange_ob(ob, total_time):
    new_ob = entity.OB(program=ob.program, target=ob.target,
                       telcfg=ob.telcfg,
                       inscfg=ob.inscfg, envcfg=ob.envcfg,
                       total_time=total_time)
    new_ob.comment = "Filter change for %s" % (ob)
    return new_ob

        
def longslew_ob(prev_ob, ob, total_time):
    if prev_ob == None:
        inscfg = entity.SPCAMConfiguration(filter=None)
    else:
        inscfg = prev_ob.inscfg
    new_ob = entity.OB(program=ob.program, target=ob.target,
                       telcfg=ob.telcfg,
                       inscfg=inscfg, envcfg=ob.envcfg,
                       total_time=total_time)
    new_ob.comment = "Long slew for %s" % (ob)
    return new_ob

        
def delay_ob(ob, total_time):
    new_ob = entity.OB(program=ob.program, target=ob.target,
                       telcfg=ob.telcfg,
                       inscfg=ob.inscfg, envcfg=ob.envcfg,
                       total_time=total_time)
    new_ob.comment = "Delay for %s visibility" % (ob)
    return new_ob

        
def precheck_slot(site, slot, ob):

    # check if filter will be installed
    if not (ob.inscfg.filter in slot.data.filters):
        return False

    # check if this slot can take this category
    if not ob.program.category in slot.data.categories:
        return False

    # Check whether OB will fit in this slot
    ## delta = (slot.stop_time - slot.start_time).total_seconds()
    ## if ob.total_time > delta:
    ##     return False

    min_el, max_el = ob.telcfg.get_el_minmax()

    # find the time that this object begins to be visible
    # TODO: figure out the best place to split the slot
    (obs_ok, t_start, t_stop) = site.observable(ob.target,
                                                slot.start_time, slot.stop_time,
                                                min_el, max_el, ob.total_time,
                                                airmass=ob.envcfg.airmass)
    return obs_ok

def obs_to_slots(slots, site, obs):
    obmap = {}
    for slot in slots:
        key = str(slot)
        obmap[key] = []
        if slot.size() < minimum_slot_size:
            continue
        for ob in obs:
            # this OB OK for this slot at this site?
            if precheck_slot(site, slot, ob):
                obmap[key].append(ob)

    return obmap


def check_slot(site, prev_slot, slot, ob):

    start_time = time.time()
    res = Bunch.Bunch(ob=ob)
    
    # check if filter will be installed
    if not (ob.inscfg.filter in slot.data.filters):
        res.setvals(obs_ok=False, reason="Filter '%s' not installed" % (
            ob.inscfg.filter))
        return res

    # check if this slot can take this category
    if not ob.program.category in slot.data.categories:
        res.setvals(obs_ok=False,
                    reason="Slot cannot take category '%s'" % (
            ob.program.category))
        return res

    # check seeing on the slot is acceptable to this ob
    if (slot.data.seeing > ob.envcfg.seeing):
        res.setvals(obs_ok=False,
                    reason="Seeing (%f > %f) not acceptable" % (
            slot.data.seeing, ob.envcfg.seeing))
        return res

    # check sky condition on the slot is acceptable to this ob
    if ob.envcfg.sky == 'clear':
        if slot.data.skycond != 'clear':
            res.setvals(obs_ok=False,
                        reason="Sky condition '%s' not acceptable ('%s' specified)" % (
                slot.data.skycond, ob.envcfg.sky))
            return res
    elif ob.envcfg.sky == 'cirrus':
        if slot.data.skycond == 'any':
            res.setvals(obs_ok=False,
                        reason="Sky condition '%s' not acceptable ('%s' specified)" % (
                slot.data.skycond, ob.envcfg.sky))
            return res

    split1_time = time.time()
    c1 = ob.target.calc(site, slot.start_time)
    split2_time = time.time()

    # if observer specified a moon phase, check it now
    if ob.envcfg.moon == 'dark':
        ## print "moon pct=%f moon alt=%f moon_sep=%f" % (
        ##     c1.moon_pct, c1.moon_alt, c1.moon_sep)
        if c1.moon_pct > dark_night_moon_pct_limit:
            res.setvals(obs_ok=False,
                        reason="Moon illumination=%f not acceptable" % (
                c1.moon_pct))
            return res

    # TODO: check moon separation from target here
    
    filterchange = False
    filterchange_sec = 0.0
    prev_ob = None

    # calculate cost of slew to this target
    if (prev_slot == None) or (prev_slot.ob == None):
        # no previous target--calculate cost from telescope parked position
        delta_alt, delta_az = parked_alt_deg - c1.alt_deg, parked_az_deg - c1.az_deg

        filterchange = True

    else:
        c0 = prev_slot.ob.target.calc(site, slot.start_time)
        delta_alt, delta_az = c0.alt_deg - c1.alt_deg, c0.az_deg - c1.az_deg
        prev_ob = prev_slot.ob
        
    #print "print delta alt,az=%f,%f sec" % (delta_alt, delta_az)
    slew_sec = misc.calc_slew_time(delta_az, delta_alt)
    #print "slew time for new ob is %f sec" % (slew_sec)

    split3_time = time.time()

    # calculate cost of filter exchange
    if filterchange or (prev_slot.ob.inscfg.filter != ob.inscfg.filter):
        # filter exchange necessary
        filterchange = True
        filterchange_sec = ob.inscfg.calc_filter_change_time()
    #print "filter change time for new ob is %f sec" % (filterchange_sec)

    # add up total preparation time for new OB
    prep_sec = slew_sec + filterchange_sec
    #print "total delay is %f sec" % (prep_sec)

    # adjust slot start time
    start_time = slot.start_time + timedelta(0, prep_sec)
    
    # Check whether OB will fit in this slot
    ## delta = (slot.stop_time - slot.start_time).total_seconds()
    ## if ob.total_time > delta:
    ##     return False

    min_el, max_el = ob.telcfg.get_el_minmax()

    split4_time = time.time()

    # find the time that this object begins to be visible
    # TODO: figure out the best place to split the slot
    (obs_ok, t_start, t_stop) = site.observable(ob.target,
                                                start_time, slot.stop_time,
                                                min_el, max_el, ob.total_time,
                                                airmass=ob.envcfg.airmass)

    split5_time = time.time()
    # TODO: time dump here

    if not obs_ok:
        res.setvals(obs_ok=False,
                    reason="Time or visibility of target")
        return res

    # calculate delay until we could actually start observing the object
    # in this slot
    delay_sec = (t_start - start_time).total_seconds()

    stop_time = t_start + timedelta(0, ob.total_time)
    res.setvals(obs_ok=obs_ok, prev_ob=prev_ob,
                prep_sec=prep_sec, slew_sec=slew_sec,
                delta_az=delta_az, delta_alt=delta_alt,
                filterchange=filterchange,
                filterchange_sec=filterchange_sec,
                start_time=t_start, stop_time=stop_time,
                delay_sec=delay_sec)
    return res


def eval_schedule(schedule):

    current_filter = None
    num_filter_exchanges = 0
    time_waste_sec = 0.0
    
    for slot in schedule.slots:
        ob = slot.ob
        # TODO: fix up a more solid check for delays
        if (ob == None) or ob.comment.startswith('Delay'):
            delta = (slot.stop_time - slot.start_time).total_seconds()
            time_waste_sec += delta
            continue

        if ob.inscfg.filter != current_filter:
            num_filter_exchanges += 1
            current_filter = ob.inscfg.filter

    res = Bunch.Bunch(num_filter_exchanges=num_filter_exchanges,
                      time_waste_sec=time_waste_sec)
    return res
            

# END
