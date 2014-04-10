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
from constraint import Problem

# Gen2 imports
import Bunch

# local imports
import misc
import constraints
import entity

version = "20140409"


def obs_to_slots(slots, constraints, obs):

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

   
def make_schedules(obmap, slots):

    schedules = []

    schedule = []
    used = []
    for slot in slots:
        try:
            # Can't use an OB more than once, so keep track of used
            # ones and don't select them
            chosen = None
            for ob in obmap[slot]:
                if not ob in used:
                    used.append(ob)
                    chosen = ob
                    break
            schedule.append((slot, chosen))
            
        except KeyError:
            # No OB fits this slot
            schedule.append((slot, None))

    schedules.append(schedule)
    return schedules


def main(options, args):

    HST = entity.HST()

    observer = entity.Observer('subaru',
                               longitude='-155:28:48.900',
                               latitude='+19:49:42.600',
                               elevation=4163,
                               pressure=615,
                               temperature=0,
                               timezone=HST)
    
    # list of all available filters
    # key: bb == broadband, nb == narrowband
    if options.filters:
        spcam_filters = set(options.filters.split())
    else:
        spcam_filters = set(["B", "V", "Rc", "Ic", "g'", "r'", "i'", "z'", "Y"])

    # -- Define fillable slots --
    # when does the night start (hr, min)
    if options.night_start != None:
        night_start = observer.get_date(options.night_start)
    else:
        # default: tonight 7pm
        now = datetime.now()
        time_s = now.strftime("%Y-%m-%d 19:00")
        night_start = observer.get_date(time_s)

    # how long is the night (in minutes)
    night_length_mn = int(options.night_length * 60)

    # what is the minimum slot length (in seconds)
    min_slot_length_sc = options.slot_length * 60

    night_slots = misc.make_slots(night_start, night_length_mn,
                                  min_slot_length_sc)

    # define constraints 
    cns = constraints.Constraints(observer=observer,
                                  available_filters=spcam_filters)
    
    # read proposals
    programs = misc.parse_proposals('programs.csv')

    # read observing blocks
    obs = []
    for propname in programs:
        obs.extend(misc.parse_obs('%s.csv' % propname, programs))

    # find possible solutions of OB -> SLOT
    obmap = obs_to_slots(night_slots, cns, obs)
    #print solutions

    # optomize and rank schedules
    schedules = make_schedules(obmap, night_slots)

    schedule = schedules[0]
    print "%-5.5s  %-6.6s  %12.12s  %5.5s %-6.6s  %3s  %3.3s  %s" % (
        'Slot', 'ObsBlk', 'Program', 'Rank', 'Filter', 'Wst',
        'AM', 'Target')

    targets = {}
    for slot, ob in schedule:
        if ob != None:
            t_prog = slot.start_time + timedelta(0, ob.total_time)
            t_waste = (slot.stop_time - t_prog).total_seconds() // 60
            print "%-5.5s  %-6.6s  %12.12s  %5.2f %-6.6s  %3d  %3.1f  %s" % (
                str(slot), str(ob), ob.program, ob.program.rank,
                ob.filter, t_waste, ob.airmass, ob.target.name)
            key = (ob.target.ra, ob.target.dec)
            targets[key] = ob.target
        else:
            print "%-5.5s  %-6.6s" % (str(slot), str(ob))

    print "%d targets" % (len(targets))

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
