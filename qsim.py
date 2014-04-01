#! /usr/bin/env python
#
# qsim.py -- Observing Queue Planner
#
#  Eric Jeschke (eric@naoj.org)
#
import sys
from optparse import OptionParser
from datetime import timedelta

# 3rd party imports
from constraint import Problem

# Gen2 imports
import Bunch

# local imports
import misc
from entity import Program, MSB, Slot, StaticTarget
import constraints

version = "20140326"


def msbs_to_slots(slots, constraints, msbs):

    # define problem
    problem = Problem()
    problem.addVariable('slot', slots)
    problem.addVariable('msb', msbs)

    # add constraints
    for name in dir(constraints):
        if name.startswith('cns_'):
            method = getattr(constraints, name)
            problem.addConstraint(method)

    # get possible solutions
    solutions = problem.getSolutions()
    
    # make inverse mapping of MSBs to slots
    msbmap = {}
    for soln in solutions:
        slot = soln['slot']
        if not slot in msbmap:
            msbmap[slot] = [ soln['msb'] ]
        else:
            msbmap[slot].append(soln['msb'])

    return msbmap

   
def make_schedules(msbmap, slots):

    schedules = []

    schedule = []
    for slot in slots:
        try:
            msbs = msbmap[slot]
            schedule.append((slot, msbs))
        except KeyError:
            schedule.append((slot, None))

    schedules.append(schedule)
    return schedules


def main(options, args):

    # list of all available filters
    # key: bb == broadband, nb == narrowband
    hsc_filters = set(['bb1', 'bb2', 'bb3', 'bb4', 'bb5', 'nb1' ])

    # -- Define fillable slots --
    # when does the night start (hr, min)
    night_start = misc.get_date("2014-03-28 19:00")

    # how long is the night (in minutes)
    night_length_mn = int(10.5 * 60)

    # what is the minimum slot length (in seconds)
    min_slot_length_sc = 30 * 60

    night_slots = misc.make_slots(night_start, night_length_mn,
                                  min_slot_length_sc)

    # -- Define constraints --
    cns = constraints.Constraints(available_filters=hsc_filters,
                                  start_time=night_start)
    
    # -- Define programs --
    programs = dict(
        o16011=Program('o16011', rank=1.0),
        o16101=Program('o16101', rank=1.0),
        o16110=Program('o16110', rank=1.0),
        o16210=Program('o16210', rank=1.0),
        o16211=Program('o16211', rank=1.0),
        o16250=Program('o16250', rank=1.0),
        )

    # -- Define MSBs --
    msbs = [
        MSB(programs['o16011'], filter='bb1',
            target=StaticTarget("vega", "18:36:56.3", "+38:47:01", "2000")),
        MSB(programs['o16101'], filter='nb1',
            target=StaticTarget("vega", "18:36:56.3", "+38:47:01", "2000")),
        MSB(programs['o16110'], filter='bb3',
            target=StaticTarget("vega", "18:36:56.3", "+38:47:01", "2000")),
        MSB(programs['o16210'], filter='bb1',
            target=StaticTarget("vega", "18:36:56.3", "+38:47:01", "2000")),
        MSB(programs['o16211'], filter='bb5',
            target=StaticTarget("vega", "18:36:56.3", "+38:47:01", "2000")),
        MSB(programs['o16250'], filter='nb2',
            target=StaticTarget("vega", "18:36:56.3", "+38:47:01", "2000")),
        ]

    # find possible solutions of MSB -> SLOT
    msbmap = msbs_to_slots(night_slots, cns, msbs)
    #print solutions

    # optomize and rank schedules
    schedules = make_schedules(msbmap, night_slots)

    schedule = schedules[0]
    for slot, msb in schedule:
        print str(slot), str(msb)
   

if __name__ == '__main__':

    usage = "usage: %prog [options]"
    optprs = OptionParser(usage=usage, version=('%%prog %s' % version))
    
    optprs.add_option("--debug", dest="debug", default=False,
                      action="store_true",
                      help="Enter the pdb debugger on main()")
    optprs.add_option("--profile", dest="profile", action="store_true",
                      default=False,
                      help="Run the profiler on main()")
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
