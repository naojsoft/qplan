#! /usr/bin/env python
#
# qsim.py -- Observing Queue Planner
#
#  Eric Jeschke (eric@naoj.org)
#
import sys
from optparse import OptionParser
from datetime import datetime, timedelta
import csv

# 3rd party imports
#from constraint import Problem

# Gen2 imports
import Bunch

# local imports
import misc
import constraints
import entity

version = "0.1.20140507"

# maximum rank for a program
max_rank = 10.0


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


def double_check_slot(site, slot, ob):
        
    # Check whether OB will fit in this slot
    delta = (slot.stop_time - slot.start_time).total_seconds()
    if ob.total_time > delta:
        return False
    return True

def check_slot(site, slot, ob):

    # check if filter will be installed
    if not (ob.inscfg.filter in slot.data.filters):
        return (False, None)

    # Check whether OB will fit in this slot
    ## delta = (slot.stop_time - slot.start_time).total_seconds()
    ## if ob.total_time > delta:
    ##     return (False, None)

    min_el, max_el = ob.telcfg.get_el_minmax()

    # find the time that this object begins to be visible
    # TODO: figure out the best place to split the slot
    (obs_ok, start) = site.observable(ob.target,
                                      slot.start_time, slot.stop_time,
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
    (obs_ok, start) = site.observable(ob.target,
                                      slot.start_time, slot.stop_time,
                                      min_el, max_el, ob.total_time,
                                      airmass=ob.envcfg.airmass)
    assert obs_ok == True, \
           Exception("slot should have been observable!")

    (slot_b, slot_c, slot_d) = slot.split(start, ob.total_time)

    # Return any leftover slots from splitting this slot
    # by the OB
    res = []
    if slot_b != None:
        res.append(slot_b)
    if slot_d != None:
        res.append(slot_d)
        
    return slot_c, res


def make_schedule(slot_asns, site, empty_slots, constraints, oblist):

    # find OBs that can fill the given (large) slots
    #obmap = obs_to_slots(empty_slots, constraints, oblist)

    obmap = {}
    for slot in empty_slots:
        obmap[slot] = []
        for ob in oblist:
            # this OB OK for this slot at this site?
            if check_slot(site, slot, ob):
                obmap[slot].append(ob)
    #print obmap

    new_slots = []
    leftover_obs = list(oblist)
    assigned = []

    # for each large slot, find the highest ranked OB that can
    # fill that slot and assign it to the slot, possibly splitting
    # the slot
    for slot, okobs in obmap.items():
        print "double-checking objects"
        for ob in okobs:
            if not double_check_slot(site, slot, ob):
                print "%s check FAILED for slot %s" % (ob, slot)
            else:
                #print "%s check SUCCEEDED for slot %s" % (ob, slot)
                pass

        print "considering slot %s" % (slot)
        # remove already assigned OBs
        for ob in assigned:
            if ob in okobs:
                okobs.remove(ob)
                
        if len(okobs) == 0:
            # no OB fits this slot
            slot_asns.append((slot, None))
            continue

        # sort possible obs for this slot by rank
        # TODO: consider
        # - proximity to previous target
        # - change of filter or not
        sorted_obs = sorted(okobs, key=lambda ob: max_rank-ob.program.rank)

        # assign the highest ranked OB to this slot
        ob = sorted_obs[0]
        assigned.append(ob)

        # remove OB from the leftover OBs
        leftover_obs.remove(ob)

        dur = ob.total_time / 60.0
        print "assigning %s(%.2fm) to %s" % (ob, dur, slot)
        # add the new empty slots made by the leftover time
        # of assigning this OB to the slot
        aslot, split_slots = reserve_slot(site, slot, ob)
        slot_asns.append((aslot, ob))
        print "leaving these=%s" % str(split_slots)
        new_slots.extend(split_slots)

    # recurse with new slots and leftover obs
    if len(leftover_obs) == 0:
        # no OBs left to distribute
        slot_asns.extend([(slot, None) for slot in new_slots])

    elif len(new_slots) > 0:
        # fill new slots as best possible
        make_schedule(slot_asns, site, new_slots, constraints, leftover_obs)

        
def main(options, args):

    HST = entity.HST()

    site = entity.Observer('subaru',
                           longitude='-155:28:48.900',
                           latitude='+19:49:42.600',
                           elevation=4163,
                           pressure=615,
                           temperature=0,
                           timezone=HST)

    # read schedule
    schedule = misc.parse_schedule("schedule.csv")

    # -- Define fillable slots --
    night_slots = []

    for date_s, starttime_s, stoptime_s, filters in schedule:
        night_start = site.get_date("%s %s" % (date_s, starttime_s))
        next_day = night_start + timedelta(0, 3600*14)
        next_day_s = next_day.strftime("%Y-%m-%d")
        night_stop = site.get_date("%s %s" % (next_day_s, stoptime_s))

        duration = int((night_stop - night_start).total_seconds())
        # associate available filters with this slot
        data = Bunch.Bunch(filters=filters)
        night_slots.append(entity.Slot(night_start, duration,
                                       data=data))

    # read proposals
    programs = misc.parse_proposals('programs.csv')

    # read observing blocks
    oblist = []
    for propname in programs:
        oblist.extend(misc.parse_obs('%s.csv' % propname, programs))

    schedule = []
    
    # optomize and rank schedules
    make_schedule(schedule, site, night_slots, constraints, oblist)

    # sort result
    schedule = sorted(schedule, key=lambda tup: tup[0].start_time)

    print "%-10.10s %-5.5s  %-6.6s  %12.12s  %5.5s %-6.6s  %3s  %3.3s  %s" % (
        'Date', 'Slot', 'ObsBlk', 'Program', 'Rank', 'Filter', 'Wst',
        'AM', 'Target')

    targets = {}
    total_waste = 0.0
    for slot, ob in schedule:
        if ob != None:
            date = slot.start_time.strftime("%Y-%m-%d")
            t_prog = slot.start_time + timedelta(0, ob.total_time)
            t_waste = (slot.stop_time - t_prog).total_seconds() // 60
            print "%-10.10s %-5.5s  %-6.6s  %12.12s  %5.2f %-6.6s  %3d  %3.1f  %s" % (
                date, str(slot), str(ob), ob.program, ob.program.rank,
                ob.inscfg.filter, t_waste, ob.envcfg.airmass,
                ob.target.name)
            key = (ob.target.ra, ob.target.dec)
            targets[key] = ob.target
        else:
            print "%-5.5s  %-6.6s" % (str(slot), str(ob))
            t_waste = (slot.stop_time - slot.start_time).total_seconds()
            total_waste += t_waste / 60.0

    print "%d targets  unscheduled=%.2f min" % (len(targets), total_waste)

    import observer
    obs = observer.Observer('subaru')
    tgts = [ obs.target(tgt.name, tgt.ra, tgt.dec)
             for tgt in targets.values() ]
    obs.almanac(night_start.strftime('%Y/%m/%d'))
    #print obs.almanac_data
    obs.airmass(*tgts)
    #print obs.airmass_data
    observer.plots.plot_airmass(obs, 'output.png')
    

if __name__ == '__main__':

    usage = "usage: %prog [options]"
    optprs = OptionParser(usage=usage, version=('%%prog %s' % version))
    
    optprs.add_option("--debug", dest="debug", default=False,
                      action="store_true",
                      help="Enter the pdb debugger on main()")
    optprs.add_option("--filters", dest="filters", default=None,
                      help="Comma-separated list of available filters")
    optprs.add_option("--night-length", dest="night_length", default=10.5,
                      type="float", metavar="HOURS",
                      help="Define the night length in HOURS")
    optprs.add_option("--night-start", dest="night_start", default=None,
                      help="Define the start of the night ('YYYY-MM-DD HH:MM')")
    optprs.add_option("--profile", dest="profile", action="store_true",
                      default=False,
                      help="Run the profiler on main()")
    optprs.add_option("--slot-length", dest="slot_length", default=30,
                      type="int", metavar="MINUTES",
                      help="Define the slot length in MINUTES")
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
