#! /usr/bin/env python
#
# Model.py -- Observing Queue Planner Model
#
#  Eric Jeschke (eric@naoj.org)
#
import os
import time
from datetime import timedelta
import pytz
import numpy
import StringIO

# 3rd party imports
from ginga.misc import Callback, Bunch

# local imports
import misc
import entity
import qsim
import azelplot

# maximum rank for a program
max_rank = 10.0

# time (sec) beyond which we breakout a slew into it's own OB
slew_breakout_limit = 30.0


class QueueModel(Callback.Callbacks):
    
    def __init__(self, logger):
        Callback.Callbacks.__init__(self)

        self.logger = logger

        # TODO: encapsulate this
        HST = entity.HST()
        self.site = entity.Observer('subaru',
                                    longitude='-155:28:48.900',
                                    latitude='+19:49:42.600',
                                    elevation=4163,
                                    pressure=615,
                                    temperature=0,
                                    timezone=HST)

        self.timezone = pytz.timezone('US/Hawaii')

        self.oblist = []
        self.schedule_tups = []
        self.programs = {}

        # FOR SCALING PURPOSES ONLY, define maximums
        # (see cmp_res() )
        self.max_slew = 20*60.0          # max slew (sec)
        self.max_rank = 10.0             # max rank
        self.max_delay = 60*60*10.0      # max wait for visibility (sec)
        self.max_filterchange = 15*60.0  # max filter exchange time (sec)

        # define weights (see cmp_res() method)
        self.w_rank = 0.3
        self.w_delay = 0.2
        self.w_slew = 0.2
        self.w_priority = 0.1
        self.w_filterchange = 0.3

        # For callbacks
        for name in ('schedule-cleared', 'schedule-added', 'schedule-selected'):
            self.enable_callback(name)

    def set_programs(self, programs):
        self.programs = programs

    def set_oblist(self, oblist):
        self.oblist = oblist
        
    def set_schedule_info(self, info):
        self.schedule_tups = info

    def cmp_res(self, res1, res2):
        """
        Compare two results from check_slot.

        Calculate a number based on the
        - slew time to target (weight: self.w_slew)
        - delay until target visible (weight: self.w_delay)
        - time lost (if any) having to change
             filters (weight: self.w_filterchange)
        - rank of the program (weight: self.w_rank)

        LOWER NUMBERS ARE BETTER!
        """
        r1_slew = min(res1.slew_sec, self.max_slew) / self.max_slew
        r1_delay = min(res1.delay_sec, self.max_delay) / self.max_delay
        r1_filter = min(res1.filterchange_sec, self.max_filterchange) / \
                    self.max_filterchange
        r1_rank = min(res1.ob.program.rank, self.max_rank) / self.max_rank
        # invert because higher rank should make a lower number
        r1_rank = 1.0 - r1_rank
        t1 = ((self.w_slew * r1_slew) + (self.w_delay * r1_delay) +
              (self.w_filterchange * r1_filter) + (self.w_rank * r1_rank))

        r2_slew = min(res2.slew_sec, self.max_slew) / self.max_slew
        r2_delay = min(res2.delay_sec, self.max_delay) / self.max_delay
        r2_filter = min(res2.filterchange_sec, self.max_filterchange) / \
                    self.max_filterchange
        r2_rank = min(res2.ob.program.rank, self.max_rank) / self.max_rank
        r2_rank = 1.0 - r2_rank
        t2 = ((self.w_slew * r2_slew) + (self.w_delay * r2_delay) +
              (self.w_filterchange * r2_filter) + (self.w_rank * r2_rank))

        if res1.ob.program == res2.ob.program:
            # for OBs in the same program, factor in priority
            t1 += self.w_priority * res1.ob.priority
            t2 += self.w_priority * res2.ob.priority

        res = int(numpy.sign(t1 - t2))
        return res
    

    def eval_slot(self, prev_slot, slot, site, oblist):

        # evaluate each OB against this slot
        results = map(lambda ob: qsim.check_slot(site, prev_slot, slot, ob),
                      oblist)

        # filter out unobservable OBs
        results = filter(lambda res: res.obs_ok, results)

        # no observable OBs?
        if len(results) == 0:
            return None

        # sort according to desired criteria
        results.sort(cmp=self.cmp_res)

        return results[0]


    def fill_schedule(self, schedule, site, oblist):

        done = False
        oblist = list(oblist)   # work on a copy

        while not done:
            time.sleep(0.01)
            
            slot = schedule.next_free_slot()
            if slot == None:
                self.logger.debug("no more empty slots")
                break

            if len(oblist) == 0:
                self.logger.debug("no more unassigned OBs")
                # insert empty time
                schedule.insert_slot(slot)
                continue

            # assign filters configuration
            slot.data = schedule.data

            # get the previous slot to this one
            prev_slot = schedule.get_previous(slot)

            # evaluate this slot against the available OBs
            # with knowledge of the previous slot
            self.logger.debug("considering slot %s" % (slot))
            res = self.eval_slot(prev_slot, slot, site, oblist)

            # no OBs fit the slot?
            if res == None:
                self.logger.debug("can't find any OBs to fit slot %s" % (
                    slot))
                # insert empty time
                schedule.insert_slot(slot)
                continue

            # insert this slot/ob into the schedule
            ob = res.ob
            dur = ob.total_time / 60.0

            # if a long slew is required, insert a separate OB for that
            ## self.logger.debug("slew time for selected object is %.1f sec (deltas: %f, %f)" % (
            ##     res.slew_sec, res.delta_az, res.delta_alt))
            if res.slew_sec > slew_breakout_limit:
                _xx, s_slot, slot = slot.split(slot.start_time,
                                               res.slew_sec)
                new_ob = qsim.longslew_ob(res.prev_ob, ob, res.slew_sec)
                s_slot.set_ob(new_ob)
                schedule.insert_slot(s_slot)

            # if a filter change is required, insert a separate OB for that
            if res.filterchange:
                _xx, f_slot, slot = slot.split(slot.start_time,
                                               res.filterchange_sec)
                new_ob = qsim.filterchange_ob(ob, res.filterchange_sec)
                f_slot.set_ob(new_ob)
                schedule.insert_slot(f_slot)

            # if a delay is required, insert a separate OB for that
            if res.delay_sec > 0.0:
                _xx, d_slot, slot = slot.split(slot.start_time,
                                               res.delay_sec)
                new_ob = qsim.delay_ob(ob, res.delay_sec)
                d_slot.set_ob(new_ob)
                schedule.insert_slot(d_slot)

            self.logger.debug("assigning %s(%.2fm) to %s" % (ob, dur, slot))
            _xx, a_slot, slot = slot.split(slot.start_time, ob.total_time)
            a_slot.set_ob(ob)
            schedule.insert_slot(a_slot)
            oblist.remove(ob)

        # return list of unused OBs
        return oblist
       

    def schedule_all(self):

        self.make_callback('schedule-cleared')
        
        # -- Define fillable slots --
        schedules = []
        night_slots = []
        site = self.site

        for tup in self.schedule_tups:
            date_s, starttime_s, stoptime_s, filters, seeing, skycond = tup

            night_start = site.get_date("%s %s" % (date_s, starttime_s))
            next_day = night_start + timedelta(0, 3600*14)
            next_day_s = next_day.strftime("%Y-%m-%d")
            night_stop = site.get_date("%s %s" % (next_day_s, stoptime_s))

            # associate available filters with this schedule
            data = Bunch.Bunch(filters=filters, seeing=seeing,
                               skycond=skycond)
            schedules.append(entity.Schedule(night_start, night_stop,
                                             data=data))
            delta = (night_stop - night_start).total_seconds()
            night_slots.append(entity.Slot(night_start, delta,
                                           data=data))

        # check whether there are some OBs that cannot be scheduled
        self.logger.info("checking for unschedulable OBs on these nights")
        obmap = qsim.obs_to_slots(night_slots, site, self.oblist)
        schedulable = set([])
        for obs in obmap.values():
            schedulable = schedulable.union(set(obs))
        unschedulable = set(self.oblist) - schedulable
        unschedulable = list(unschedulable)
        self.logger.info("there are %d unschedulable OBs" % (len(unschedulable)))

        self.logger.info("preparing to schedule")
        oblist = list(schedulable)
        self.schedules = []

        # build a lookup table of programs -> OBs
        props = {}
        for key in self.programs:
            props[key] = Bunch.Bunch(pgm=self.programs[key], obs=[], obcount=0)

        # count OBs in each program
        for ob in oblist:
            pgmname = str(ob.program)
            props[pgmname].obs.append(ob)
            props[pgmname].obcount += 1

        unscheduled_obs = list(oblist)
        total_waste = 0.0

        self.logger.info("scheduling %d OBs (from %d programs) for %d nights" % (
            len(unscheduled_obs), len(self.programs), len(schedules)))

        for schedule in schedules:

            start_time = schedule.start_time
            stop_time  = schedule.stop_time
            delta = (stop_time - start_time).total_seconds()

            nslot = entity.Slot(start_time, delta, data=schedule.data)
            slots = [ nslot ]

            t = start_time.astimezone(self.timezone)
            ndate = t.strftime("%Y-%m-%d")
            #outfile = os.path.join(output_dir, ndate + '.txt')

            self.logger.info("scheduling night %s" % (ndate))

            obmap = qsim.obs_to_slots(slots, site, unscheduled_obs)
            this_nights_obs = obmap[str(nslot)]
            self.logger.info("%d OBs can be executed this night" % (
                len(this_nights_obs)))

            # optomize and rank schedules
            self.fill_schedule(schedule, site, this_nights_obs)

            res = qsim.eval_schedule(schedule)

            self.schedules.append(schedule)
            self.make_callback('schedule-added', schedule)
            
            targets = {}
            target_list = []
            for slot in schedule.slots:

                ob = slot.ob
                if ob != None:
                    if len(ob.comment) == 0:
                        # not an OB generated to serve another OB
                        key = (ob.target.ra, ob.target.dec)
                        targets[key] = ob.target
                        unscheduled_obs.remove(ob)
                        props[str(ob.program)].obs.remove(ob)

            waste = res.time_waste_sec / 60.0
            total_waste += waste

            self.logger.info("%d unscheduled OBs left" % (len(unscheduled_obs)))

        # print a summary
        out_f = StringIO.StringIO()
        num_obs = len(oblist)
        pct = float(num_obs - len(unscheduled_obs)) / float(num_obs)
        out_f.write("%5.2f %% of OBs scheduled\n" % (pct*100.0))

        if len(unschedulable) > 0:
            out_f.write("\n")
            out_f.write("%d OBs are not schedulable: %s\n" % (len(unschedulable), unschedulable))
            out_f.write("\n")

        completed, uncompleted = [], []
        for key in self.programs:
            bnch = props[key]
            if len(bnch.obs) == 0:
                completed.append(bnch)
            else:
                uncompleted.append(bnch)

        completed = sorted(completed, key=lambda bnch: max_rank - bnch.pgm.rank)
        uncompleted = sorted(uncompleted, key=lambda bnch: max_rank - bnch.pgm.rank)

        out_f.write("Completed programs\n")
        for bnch in completed:
            out_f.write("%-12.12s   %5.2f  %d/%d  100%%\n" % (str(bnch.pgm), bnch.pgm.rank,
                                                        bnch.obcount, bnch.obcount))

        out_f.write("\n")

        out_f.write("Uncompleted programs\n")
        for bnch in uncompleted:
            pct = float(bnch.obcount-len(bnch.obs)) / float(bnch.obcount) * 100.0
            out_f.write("%-12.12s   %5.2f  %d/%d  %5.2f%%\n" % (str(bnch.pgm), bnch.pgm.rank,
                                                        bnch.obcount-len(bnch.obs),
                                                        bnch.obcount, pct))
        out_f.write("\n")
        out_f.write("Total unscheduled time: %8.2f min\n" % (total_waste))
        self.summary_report = out_f.getvalue()
        out_f.close()
        self.logger.info(self.summary_report)
        

    def select_schedule(self, schedule):

        self.make_callback('schedule-selected', schedule)
        

# END
