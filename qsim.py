#! /usr/bin/env python
#
# qsim.py -- Observing Queue Planner
#
#  Eric Jeschke (eric@naoj.org)
#
import sys
from optparse import OptionParser
from datetime import datetime, timedelta
import pytz
import csv
import logging

# 3rd party imports
#from constraint import Problem
# for printing target trajectory graphs
#import observer

# Gen2 imports
import Bunch

# local imports
import misc
import constraints
import entity

version = "0.1.20140507"

LOG_FORMAT = '%(asctime)s | %(levelname)1.1s | %(filename)s:%(lineno)d | %(message)s'


# maximum rank for a program
max_rank = 10.0

# minimum slot size in sec
minimum_slot_size = 180.0
#minimum_slot_size = 10.0

def schedules_to_slots(slots, constraints, schedules):
    # define problem
    problem = Problem()
    problem.addVariable('slot', slots)
    problem.addVariable('schedule', schedules)

    # add constraints
    for name in dir(constraints):
        if name.startswith('cns_'):
            method = getattr(constraints, name)
            problem.addConstraint(method)

    # get possible solutions
    solutions = problem.getSolutions()
    
    # make inverse mapping of schedules to slots
    schmap = {}
    for soln in solutions:
        slot = soln['slot']
        if not slot in schmap:
            schmap[slot] = [ soln['ob'] ]
        else:
            schmap[slot].append(soln['ob'])

    return schmap


def obs_to_slots(slots, constraints, obs):
    # this version assumes fixed slots

    # define problem
    problem = Problem()
    problem.addVariable('slot', slots)
    problem.addVariable('ob', obs)

    # add constraints
    for name in dir(constraints):
        if name.startswith('cns_'):
            method = getattr(constraints, name)
            problem.addConstraint(method)

    # get possible solutions
    solutions = problem.getSolutions()
    
    # make inverse mapping of OBs to slots
    obmap = {}
    for soln in solutions:
        slot = soln['slot']
        if not slot in obmap:
            obmap[slot] = [ soln['ob'] ]
        else:
            obmap[slot].append(soln['ob'])

    return obmap


def obs_to_slots2(slots, site, obs):
    obmap = {}
    for slot in slots:
        obmap[slot] = []
        if slot.size() < minimum_slot_size:
            continue
        for ob in obs:
            # this OB OK for this slot at this site?
            if check_slot(site, slot, ob):
                obmap[slot].append(ob)
    #print obmap
    return obmap


def double_check_slot(site, slot, ob):
        
    # check if filter will be installed
    if not (ob.inscfg.filter in slot.data.filters):
        print "Failed: no filter match (%s): %s" % (
            ob.inscfg.filter, slot.data.filters)
        return False

    # Check whether OB will fit in this slot
    delta = (slot.stop_time - slot.start_time).total_seconds()
    if ob.total_time > delta:
        print "Failed: slot too short"
        return False
    return True

def check_slot(site, slot, ob):

    # check if filter will be installed
    if not (ob.inscfg.filter in slot.data.filters):
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

def check_slot2(site, prev_ob, slot, ob):

    # check if filter will be installed
    if not (ob.inscfg.filter in slot.data.filters):
        return (False, 0.0)

    # calculate cost of slew to this target
    prev_tgt = prev_ob.target
    cur_tgt = ob.target

    delta_alt, delta_az = prev_tgt.calc_separation_alt_az(cur_tgt)
    slew_time_sec = misc.calc_slew_time(delta_alt, delta_az)
    print "slew time for new ob is %f sec" % (slew_time_sec)

    # calculate cost of filter exchange
    filter_change_sec = 0.0
    if prev_ob.inscfg.filter != ob.inscfg.filter:
        # filter exchange necessary
        filter_change_sec = 15.0 * 60.0
        print "filter change time for new ob is %f sec" % (slew_time_sec)

    delay_sec = slew_time_sec + filter_change_sec
    print "total delay is %f sec" % (slew_time_sec)
    
    start_time = slot.start_time + timedelta(0, delay_sec)
    
    # Check whether OB will fit in this slot
    ## delta = (slot.stop_time - slot.start_time).total_seconds()
    ## if ob.total_time > delta:
    ##     return False

    min_el, max_el = ob.telcfg.get_el_minmax()

    # find the time that this object begins to be visible
    # TODO: figure out the best place to split the slot
    (obs_ok, t_start, t_stop) = site.observable(ob.target,
                                                start_time, slot.stop_time,
                                                min_el, max_el, ob.total_time,
                                                airmass=ob.envcfg.airmass)
    return obs_ok

def reserve_slot(site, slot, ob):
        
    # Check whether OB will fit in this slot
    delta = (slot.stop_time - slot.start_time).total_seconds()
    if ob.total_time > delta:
        print "HELLO!!!"
        
    min_el, max_el = ob.telcfg.get_el_minmax()

    # find the time that this object begins to be visible
    # TODO: figure out the best place to split the slot
    (obs_ok, t_start, t_stop) = site.observable(ob.target,
                                                slot.start_time, slot.stop_time,
                                                min_el, max_el, ob.total_time,
                                                airmass=ob.envcfg.airmass)
    assert obs_ok == True, \
           Exception("slot should have been observable!")

    (slot_b, slot_c, slot_d) = slot.split(t_start, ob.total_time)

    # Return any leftover slots from splitting this slot
    # by the OB
    res = []
    if slot_b != None:
        res.append(slot_b)
    if slot_d != None:
        res.append(slot_d)

    slot_c.set_ob(ob)
    return slot_c, res


def pick_ob(slot, okobs):
    # TODO: consider
    # - proximity to previous target
    # - change of filter or not
    # - moon illumination

    # sort OBs by rank
    sorted_obs = sorted(okobs, key=lambda ob: max_rank-ob.program.rank)

    # assign the highest ranked OB to this slot
    ob = sorted_obs[0]
    return ob


def make_schedule(schedule, site, empty_slots, constraints, oblist, logger):

    # find OBs that can fill the given slots
    #obmap = obs_to_slots(empty_slots, constraints, oblist)
    obmap = obs_to_slots2(empty_slots, site, oblist)

    new_slots = []
    assigned = []

    # for each large slot, find the highest ranked OB that can
    # fill that slot and assign it to the slot, possibly splitting
    # the slot
    for slot, okobs in obmap.items():
        ## print "double-checking objects"
        ## for ob in okobs:
        ##     if not double_check_slot(site, slot, ob):
        ##         raise Exception("%s check FAILED for slot %s" % (ob, slot))
        ##     else:
        ##         #print "%s check SUCCEEDED for slot %s" % (ob, slot)
        ##         pass

        logger.debug("considering slot %s" % (slot))
        # remove already assigned OBs
        for ob in assigned:
            if ob in okobs:
                okobs.remove(ob)
                
        if len(okobs) == 0:
            # no OB fits this slot
            schedule.insert_slot(slot)
            continue

        # examine and pick an ob for this slot
        ob = pick_ob(slot, okobs)
        assigned.append(ob)

        # remove OB from the leftover OBs
        oblist.remove(ob)

        dur = ob.total_time / 60.0
        logger.debug("assigning %s(%.2fm) to %s" % (ob, dur, slot))
        # add the new empty slots made by the leftover time
        # of assigning this OB to the slot
        aslot, split_slots = reserve_slot(site, slot, ob)
        schedule.insert_slot(aslot)
        logger.debug("leaving these=%s" % str(split_slots))
        new_slots.extend(split_slots)

    # recurse with new slots and leftover obs
    if len(oblist) == 0:
        # no OBs left to distribute
        for slot in new_slots:
            schedule.insert_slot(slot)

    elif len(new_slots) > 0:
        # fill new slots as best possible
        make_schedule(schedule, site, new_slots, constraints, oblist, logger)


def eval_schedule(schedule):

    current_filter = None
    num_filter_exchanges = 0
    
    for slot in schedule.slots:
        ob = slot.ob
        if ob == None:
            continue

        if ob.inscfg.filter != current_filter:
            num_filter_exchanges += 1
            current_filter = ob.inscfg.filter

    res = Bunch.Bunch(num_filter_exchanges=num_filter_exchanges)
    return res

            
def main(options, args):

    # Create top level logger.
    logger = logging.getLogger('datasink')
    logger.setLevel(logging.DEBUG)

    fmt = logging.Formatter(LOG_FORMAT)

    if options.logfile:
        fileHdlr  = logging.handlers.RotatingFileHandler(options.logfile,
                                                         maxBytes=options.loglimit,
                                                         backupCount=4)
        fileHdlr.setFormatter(fmt)
        fileHdlr.setLevel(options.loglevel)
        logger.addHandler(fileHdlr)
    # Add output to stderr, if requested
    if options.logstderr or (not options.logfile):
        stderrHdlr = logging.StreamHandler()
        stderrHdlr.setFormatter(fmt)
        stderrHdlr.setLevel(options.loglevel)
        logger.addHandler(stderrHdlr)

    logger.info("initializing")
    HST = entity.HST()
    timezone = pytz.timezone('US/Hawaii')

    site = entity.Observer('subaru',
                           longitude='-155:28:48.900',
                           latitude='+19:49:42.600',
                           elevation=4163,
                           pressure=615,
                           temperature=0,
                           timezone=HST)

    # read schedule
    logger.info("reading schedule and defining periods")
    schedule = misc.parse_schedule("schedule.csv")

    # -- Define fillable slots --
    schedules = []
    night_slots = []

    for tup in schedule:
        date_s, starttime_s, stoptime_s, filters, seeing, moon = tup
        
        night_start = site.get_date("%s %s" % (date_s, starttime_s))
        next_day = night_start + timedelta(0, 3600*14)
        next_day_s = next_day.strftime("%Y-%m-%d")
        night_stop = site.get_date("%s %s" % (next_day_s, stoptime_s))

        # associate available filters with this schedule
        data = Bunch.Bunch(filters=filters)
        schedules.append(entity.Schedule(night_start, night_stop,
                                         data=data))
        delta = (night_stop - night_start).total_seconds()
        night_slots.append(entity.Slot(night_start, delta,
                                       data=data))

    # read proposals
    logger.info("reading proposals")
    programs = misc.parse_proposals('programs.csv')
    # build a lookup table of programs -> OBs
    props = {}
    for key in programs:
        props[key] = Bunch.Bunch(pgm=programs[key], obs=[], obcount=0)

    # read observing blocks
    logger.info("reading observing blocks")
    oblist = []
    for propname in programs:
        oblist.extend(misc.parse_obs('%s.csv' % propname, programs))

    # check whether there are some OBs that cannot be scheduled
    logger.info("checking for unschedulable OBs on these nights")
    obmap = obs_to_slots2(night_slots, site, oblist)
    schedulable = set([])
    for obs in obmap.values():
        schedulable = schedulable.union(set(obs))
    unschedulable = set(oblist) - schedulable
    unschedulable = list(unschedulable)
    logger.info("there are %d unschedulable OBs" % (len(unschedulable)))

    logger.info("preparing to schedule")
    oblist = list(schedulable)

    # count OBs in each program
    for ob in oblist:
        pgmname = str(ob.program)
        props[pgmname].obs.append(ob)
        props[pgmname].obcount += 1

    unscheduled_obs = list(oblist)
    total_waste = 0.0

    logger.info("scheduling %d OBs (from %d programs) for %d nights" % (
        len(unscheduled_obs), len(programs), len(schedules)))
    
    for schedule in schedules:

        start_time = schedule.start_time
        stop_time  = schedule.stop_time
        delta = (stop_time - start_time).total_seconds()
        
        nslot = entity.Slot(start_time, delta, data=schedule.data)
        slots = [ nslot ]

        t = start_time.astimezone(timezone)
        ndate = t.strftime("%Y-%m-%d")
        outfile = ndate + '.txt'

        logger.info("scheduling night %s" % (ndate))

        obmap = obs_to_slots2(slots, site, unscheduled_obs)
        this_nights_obs = obmap[nslot]
        logger.info("%d OBs can be executed this night" % (
            len(this_nights_obs)))

        # optomize and rank schedules
        make_schedule(schedule, site, slots, constraints, this_nights_obs,
                      logger)

        res = eval_schedule(schedule)
        logger.info("flt exch=%d" % (res.num_filter_exchanges))

        with open(outfile, 'w') as out_f:
            out_f.write("--- NIGHT OF %s ---\n" % (ndate))
            out_f.write("%-16.16s  %-6.6s  %12.12s  %5.5s %7.7s %-6.6s  %3.3s  %s\n" % (
                'Date', 'ObsBlk', 'Program', 'Rank', 'Time', 'Filter', 'AM', 'Target'))

            targets = {}
            for slot in schedule.slots:

                t = slot.start_time.astimezone(timezone)
                date = t.strftime("%Y-%m-%d %H:%M")
                ob = slot.ob
                if ob != None:
                    t_prog = slot.start_time + timedelta(0, ob.total_time)
                    out_f.write("%-16.16s  %-6.6s  %12.12s  %5.2f %7.2f %-6.6s  %3.1f  %s\n" % (
                        date, str(ob), ob.program, ob.program.rank,
                        ob.total_time / 60,
                        ob.inscfg.filter, ob.envcfg.airmass,
                        ob.target.name))
                    key = (ob.target.ra, ob.target.dec)
                    targets[key] = ob.target
                    unscheduled_obs.remove(ob)
                    props[str(ob.program)].obs.remove(ob)
                else:
                    out_f.write("%-16.16s  %-6.6s\n" % (date, str(ob)))

            out_f.write("\n")
            waste = schedule.get_waste() / 60.0
            out_f.write("%d targets  unscheduled: time=%.2f min\n" % (
                len(targets), waste))
            out_f.write("\n")
            total_waste += waste

        # obs = observer.Observer('subaru')
        # tgts = [ obs.target(tgt.name, tgt.ra, tgt.dec)
        #          for tgt in targets.values() ]
        # obs.almanac(ndate.replace('-', '/'))
        # #print obs.almanac_data
        # obs.airmass(*tgts)
        # #print obs.airmass_data
        # observer.plots.plot_airmass(obs, 'output-%s.png' % (ndate))

        logger.info("%d unscheduled OBs left" % (len(unscheduled_obs)))

    # print a summary
    num_obs = len(oblist)
    pct = float(num_obs - len(unscheduled_obs)) / float(num_obs)
    print "%5.2f %% of OBs scheduled" % (pct*100.0)

    if len(unschedulable) > 0:
        print ""
        print "%d OBs are not schedulable: %s" % (len(unschedulable), unschedulable)
        print ""
    
    completed, uncompleted = [], []
    for key in programs:
        bnch = props[key]
        if len(bnch.obs) == 0:
            completed.append(bnch)
        else:
            uncompleted.append(bnch)
            
    completed = sorted(completed, key=lambda bnch: max_rank - bnch.pgm.rank)
    uncompleted = sorted(uncompleted, key=lambda bnch: max_rank - bnch.pgm.rank)
    
    print "Completed programs"
    for bnch in completed:
        print "%-12.12s   %5.2f  %d/%d  100%%" % (str(bnch.pgm), bnch.pgm.rank,
                                                    bnch.obcount, bnch.obcount)
    
    print ""

    print "Uncompleted programs"
    for bnch in uncompleted:
        pct = float(bnch.obcount-len(bnch.obs)) / float(bnch.obcount) * 100.0
        print "%-12.12s   %5.2f  %d/%d  %5.2f%%" % (str(bnch.pgm), bnch.pgm.rank,
                                                    bnch.obcount-len(bnch.obs),
                                                    bnch.obcount, pct)
    print ""
    print "Total unscheduled time: %8.2f min" % (total_waste)
    
            
        

if __name__ == '__main__':

    usage = "usage: %prog [options]"
    optprs = OptionParser(usage=usage, version=('%%prog %s' % version))
    
    optprs.add_option("--debug", dest="debug", default=False,
                      action="store_true",
                      help="Enter the pdb debugger on main()")
    optprs.add_option("--log", dest="logfile", metavar="FILE",
                      help="Write logging output to FILE")
    optprs.add_option("--loglevel", dest="loglevel", metavar="LEVEL",
                      type="int", default=logging.INFO,
                      help="Set logging level to LEVEL")
    optprs.add_option("--profile", dest="profile", action="store_true",
                      default=False,
                      help="Run the profiler on main()")
    optprs.add_option("--slot-start", dest="slot_start", default=None,
                      help="Define the start of the slot ('YYYY-MM-DD HH:MM')")
    optprs.add_option("--slot-end", dest="slot_end", default=None,
                      help="Define the end of the slot ('YYYY-MM-DD HH:MM')")
    optprs.add_option("--stderr", dest="logstderr", default=False,
                      action="store_true",
                      help="Copy logging also to stderr")
    (options, args) = optprs.parse_args(sys.argv[1:])

    if len(args) != 0:
        optprs.error("incorrect number of arguments")


    # Are we debugging this?
    if options.debug:
        import pdb

        pdb.run('main(options, args)')

    # Are we profiling this?
    elif options.profile:
        import profile

        print "%s profile:" % sys.argv[0]
        profile.run('main(options, args)')

    else:
        main(options, args)


# END
