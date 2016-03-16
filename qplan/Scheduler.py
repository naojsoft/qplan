#! /usr/bin/env python
#
# Scheduler.py -- Observing Queue Scheduler
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
import common
import qsim

# maximum rank for a program
max_rank = 10.0

# time (sec) beyond which we breakout a slew into it's own OB
slew_breakout_limit = 30.0


class Scheduler(Callback.Callbacks):

    def __init__(self, logger):
        Callback.Callbacks.__init__(self)

        self.logger = logger

        self.site = common.subaru
        # TODO: encapsulate this
        HST = entity.HST()
        #self.timezone = pytz.timezone('US/Hawaii')
        self.timezone = HST

        # these are the main data structures used to schedule
        self.oblist = []
        self.schedule_recs = []
        self.programs = {}

        # FOR SCALING PURPOSES ONLY, define maximums
        # (see cmp_res() )
        self.max_slew = 20*60.0          # max slew (sec)
        self.max_rank = 10.0             # max rank
        self.max_delay = 60*60*10.0      # max wait for visibility (sec)
        self.max_filterchange = 35*60.0  # max filter exchange time (sec)

        # define weights (see cmp_res() method)
        self.weights = Bunch.Bunch(w_rank=0.3, w_delay=0.2,
                                   w_slew=0.2, w_priority=0.1,
                                   w_filterchange = 0.3)

        # For callbacks
        for name in ('schedule-cleared', 'schedule-added', 'schedule-completed',):
            self.enable_callback(name)

    def set_weights(self, weights):
        self.weights = weights

    def set_programs_info(self, info):
        self.programs = {}
        for key, rec in info.items():
            if not rec.skip:
                self.programs[key] = rec

    def set_oblist_info(self, info):
        self.oblist = info

    def set_schedule_info(self, info):
        # Set our schedule_recs attribute to the supplied data
        # structure.
        self.schedule_recs = info

    def cmp_res(self, res1, res2):
        """
        Compare two results from check_slot.

        Calculate a number based on the
        - slew time to target (weight: w_slew)
        - delay until target visible (weight: w_delay)
        - time lost (if any) having to change
             filters (weight: self.w_filterchange)
        - rank of the program (weight: w_rank)

        LOWER NUMBERS ARE BETTER!
        """
        wts = self.weights

        r1_slew = min(res1.slew_sec, self.max_slew) / self.max_slew
        r1_delay = min(res1.delay_sec, self.max_delay) / self.max_delay
        r1_filter = min(res1.filterchange_sec, self.max_filterchange) / \
                    self.max_filterchange
        r1_rank = min(res1.ob.program.rank, self.max_rank) / self.max_rank
        # invert because higher rank should make a lower number
        r1_rank = 1.0 - r1_rank
        t1 = ((wts.w_slew * r1_slew) + (wts.w_delay * r1_delay) +
              (wts.w_filterchange * r1_filter) + (wts.w_rank * r1_rank))

        r2_slew = min(res2.slew_sec, self.max_slew) / self.max_slew
        r2_delay = min(res2.delay_sec, self.max_delay) / self.max_delay
        r2_filter = min(res2.filterchange_sec, self.max_filterchange) / \
                    self.max_filterchange
        r2_rank = min(res2.ob.program.rank, self.max_rank) / self.max_rank
        r2_rank = 1.0 - r2_rank
        t2 = ((wts.w_slew * r2_slew) + (wts.w_delay * r2_delay) +
              (wts.w_filterchange * r2_filter) + (wts.w_rank * r2_rank))

        if res1.ob.program == res2.ob.program:
            # for OBs in the same program, factor in priority
            t1 += wts.w_priority * res1.ob.priority
            t2 += wts.w_priority * res2.ob.priority

        res = int(numpy.sign(t1 - t2))
        return res


    def eval_slot(self, prev_slot, slot, site, oblist):

        # evaluate each OB against this slot
        results = map(lambda ob: qsim.check_slot(site, prev_slot, slot, ob),
                      oblist)

        # filter out unobservable OBs
        good = filter(lambda res: res.obs_ok, results)
        bad = filter(lambda res: not res.obs_ok, results)

        # sort according to desired criteria
        good.sort(cmp=self.cmp_res)

        return good, bad


    def fill_night_schedule(self, schedule, site, oblist, props):

        cantuse = []

        # check all available OBs against this slot and remove those
        # that cannot be used a priori
        usable = []
        for ob in oblist:
            res = qsim.check_schedule_invariant(site, schedule, ob)
            if res.obs_ok:
                usable.append(ob)
            else:
                cantuse.append(ob)
                ob_id = "%s/%s" % (res.ob.program, res.ob.name)
                self.logger.debug("rejected %s (%s) because: %s" % (
                    res.ob, ob_id, res.reason))

        # reassign usable OBs
        oblist = usable

        # make a visibility map, and reject OBs that are not visible
        # during this night
        usable = []
        obmap = {}
        for ob in oblist:
            res = qsim.check_night_visibility(site, schedule, ob)
            if res.obs_ok:
                usable.append(ob)
                # record visibility window
                obmap[str(ob)] = res
            else:
                cantuse.append(ob)
                ob_id = "%s/%s" % (res.ob.program, res.ob.name)
                self.logger.debug("rejected %s (%s) because: %s" % (
                    res.ob, ob_id, res.reason))

        # reassign usable OBs
        oblist = usable

        done = False
        while not done:
            # give GUI thread a chance to run
            #time.sleep(0.0001)

            slot = schedule.next_free_slot()
            if slot == None:
                self.logger.debug("no more empty slots")
                break

            if len(oblist) == 0:
                self.logger.debug("no more unassigned OBs")
                # insert empty time
                schedule.insert_slot(slot)
                continue

            # assign filters and other configuration details to new slot
            slot.data = schedule.data

            # get the previous slot to this one
            prev_slot = schedule.get_previous(slot)

            # evaluate this slot against the available OBs
            # with knowledge of the previous slot
            self.logger.debug("considering slot %s" % (slot))
            good, bad = self.eval_slot(prev_slot, slot, site, oblist)

            # remove OBs that can't work in the slot and explain why
            for res in bad:
                ob = res.ob
                ob_id = "%s/%s" % (ob.program, ob.name)
                self.logger.debug("rejected %s (%s) because: %s" % (
                    ob, ob_id, res.reason))
                cantuse.append(ob)
                oblist.remove(ob)

            # insert top slot/ob into the schedule
            found_one = False
            for res in good:
                ob = res.ob
                ob_id = "%s/%s" % (ob.program, ob.name)
                # check whether this proposal has exceeded its allotted time
                # if we schedule this OB
                # NOTE: charge them for any delay time, filter exch time, etc?
                # currently: no
                #obtime = (ob.time_stop - ob.time_start).total_seconds()
                obtime = ob.total_time
                acct_time = ob.acct_time
                prop_total = props[str(ob.program)].sched_time + acct_time
                if prop_total > props[str(ob.program)].total_time:
                    self.logger.debug("rejected %s (%s) because it would exceed program allotted time" % (
                        ob, ob_id))
                    cantuse.append(ob)
                    oblist.remove(ob)
                    continue

                found_one = True
                break

            # no OBs fit the slot?
            if not found_one:
                self.logger.debug("can't find any OBs to fit slot %s" % (
                    slot))
                # insert empty time
                schedule.insert_slot(slot)
                continue

            # account this scheduled time to the program
            props[str(ob.program)].sched_time += acct_time
            dur = ob.total_time / 60.0

            ob_change_sec = 1.0
            _xx, s_slot, slot = slot.split(slot.start_time, ob_change_sec)
            new_ob = qsim.setup_ob(ob, ob_change_sec)
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

            # is there an SDSS calibration target?
            if ob.target.sdss_calib is not None:
                time_add_sec = res.calibration_sec + res.slew_sec
                _xx, f_slot, slot = slot.split(slot.start_time,
                                               time_add_sec)
                sdss_target = ob.target.sdss_calib
                new_ob = qsim.calibration_ob(ob, sdss_target,
                                             time_add_sec)
                f_slot.set_ob(new_ob)
                schedule.insert_slot(f_slot)

                slew_sec = res.slew2_sec
            else:
                slew_sec = res.slew_sec

            ## # if a long slew is required, insert a separate OB for that
            ## self.logger.debug("slew time for selected object is %.1f sec (deltas: %f, %f)" % (
            ##     res.slew_sec, res.delta_az, res.delta_alt))
            ## if res.slew_sec > slew_breakout_limit:
            ##     _xx, s_slot, slot = slot.split(slot.start_time,
            ##                                    res.slew_sec)
            ##     new_ob = qsim.longslew_ob(res.prev_ob, ob, res.slew_sec)
            ##     s_slot.set_ob(new_ob)
            ##     schedule.insert_slot(s_slot)

            self.logger.debug("assigning %s(%.2fm) to %s" % (ob, dur, slot))
            _xx, a_slot, slot = slot.split(slot.start_time, ob.total_time)
            a_slot.set_ob(ob)
            schedule.insert_slot(a_slot)
            oblist.remove(ob)

        # return list of unused OBs
        oblist.extend(cantuse)
        return oblist


    def schedule_all(self):

        self.make_callback('schedule-cleared')

        # -- Define fillable slots --
        schedules = []
        night_slots = []
        site = self.site

        # measure performance of scheduling
        t_t1 = time.time()

        for rec in self.schedule_recs:
            night_start = site.get_date("%s %s" % (rec.date, rec.starttime))
            next_day = night_start + timedelta(0, 3600*14)
            next_day_s = next_day.strftime("%Y-%m-%d")
            # Assume that stoptime is on the next day, but revert to same
            # day if resulting end time is less than the start time
            night_stop = site.get_date("%s %s" % (rec.date, rec.stoptime))
            if night_stop < night_start:
                night_stop = site.get_date("%s %s" % (next_day_s, rec.stoptime))

            # associate available filters and other items with this schedule
            schedules.append(entity.Schedule(night_start, night_stop,
                                             data=rec.data))
            delta = (night_stop - night_start).total_seconds()
            night_slots.append(entity.Slot(night_start, delta,
                                           data=rec.data))

        # check whether there are some OBs that cannot be scheduled
        self.logger.info("checking for unschedulable OBs on these nights from %d OBs" % (len(self.oblist)))
        obmap = qsim.obs_to_slots(self.logger, night_slots, site,
                                  self.oblist)
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
        total_program_time = 0
        for key in self.programs:
            total_time = self.programs[key].total_time
            props[key] = Bunch.Bunch(pgm=self.programs[key], obs=[],
                                     obcount=0, sched_time=0.0,
                                     total_time=total_time)
            total_program_time += total_time

        # count OBs in each program
        total_ob_time = 0
        for ob in self.oblist:
            pgmname = str(ob.program)
            props[pgmname].obs.append(ob)
            props[pgmname].obcount += 1
            # New policy is not to charge any overhead to the client,
            # including readout time
            obtime_no_overhead = ob.inscfg.exp_time * ob.inscfg.num_exp
            total_ob_time += obtime_no_overhead

        unscheduled_obs = list(oblist)
        total_avail = 0.0
        total_waste = 0.0

        # Note oversubscribed time
        self.logger.info("total program time=%d  total ob time=%d" % (
            total_program_time, total_ob_time))
        diff = total_ob_time - total_program_time
        if diff > 0:
            hrs = float(diff) / 3600.0
            self.logger.info("oversubscribed by %.2f hours" % (hrs))
        elif diff < 0:
            hrs = float(-diff) / 3600.0
            self.logger.info("undersubscribed by %.2f hours" % (hrs))

        self.logger.info("scheduling %d OBs (from %d programs) for %d nights" % (
            len(unscheduled_obs), len(self.programs), len(schedules)))

        for schedule in schedules:

            start_time = schedule.start_time
            stop_time  = schedule.stop_time
            delta = (stop_time - start_time).total_seconds()
            total_avail += delta / 60.0

            nslot = entity.Slot(start_time, delta, data=schedule.data)
            slots = [ nslot ]

            t = start_time.astimezone(self.timezone)
            ndate = t.strftime("%Y-%m-%d")
            #outfile = os.path.join(output_dir, ndate + '.txt')

            self.logger.info("scheduling night %s" % (ndate))

            ## this_nights_obs = unscheduled_obs
            # sort to force deterministic scheduling if the same
            # files are reloaded
            this_nights_obs = sorted(unscheduled_obs,
                                     cmp=lambda ob1, ob2: cmp(str(ob1), str(ob2)))

            # optomize and rank schedules
            self.fill_night_schedule(schedule, site, this_nights_obs, props)

            res = qsim.eval_schedule(schedule)

            self.schedules.append(schedule)
            self.make_callback('schedule-added', schedule)

            targets = {}
            target_list = []
            for slot in schedule.slots:

                ob = slot.ob
                if ob != None:
                    if not ob.derived:
                        # not an OB generated to serve another OB
                        key = (ob.target.ra, ob.target.dec)
                        targets[key] = ob.target
                        unscheduled_obs.remove(ob)
                        props[str(ob.program)].obs.remove(ob)

            waste = res.time_waste_sec / 60.0
            total_waste += waste

            self.logger.info("%d unscheduled OBs left" % (len(unscheduled_obs)))

        t_elapsed = time.time() - t_t1
        self.logger.info("%.2f sec to schedule all" % (t_elapsed))

        # print a summary
        out_f = StringIO.StringIO()
        num_obs = len(oblist)
        pct = 0.0
        if num_obs > 0:
            pct = float(num_obs - len(unscheduled_obs)) / float(num_obs)
        out_f.write("%5.2f %% of OBs scheduled\n" % (pct*100.0))

        if len(unschedulable) > 0:
            out_f.write("\n")
            out_f.write("%d OBs are not schedulable:\n" % (len(unschedulable)))
            ## unschedulable.sort(cmp=lambda ob1, ob2: cmp(ob1.program.proposal,
            ##                                             ob2.program.proposal))

            for ob in unschedulable:
                out_f.write("%s (%s)\n" % (ob.name, ob.program.proposal))
            out_f.write("\n")

        completed, uncompleted = [], []
        for key in self.programs:
            bnch = props[key]
            if len(bnch.obs) == 0:
                completed.append(bnch)
            else:
                uncompleted.append(bnch)

        completed = sorted(completed,
                           key=lambda bnch: max_rank - bnch.pgm.rank)
        uncompleted = sorted(uncompleted,
                             key=lambda bnch: max_rank - bnch.pgm.rank)

        self.make_callback('schedule-completed',
                           completed, uncompleted, self.schedules)

        out_f.write("Completed programs\n")
        for bnch in completed:
            out_f.write("%-12.12s   %5.2f  %d/%d  100%%\n" % (
                str(bnch.pgm), bnch.pgm.rank,
                bnch.obcount, bnch.obcount))

        out_f.write("\n")

        out_f.write("Uncompleted programs\n")
        for bnch in uncompleted:
            pct = float(bnch.obcount-len(bnch.obs)) / float(bnch.obcount) * 100.0
            uncompleted_s = ", ".join(map(lambda ob: ob.name, props[str(bnch.pgm)].obs))

            out_f.write("%-12.12s   %5.2f  %d/%d  %5.2f%%  [%s]\n" % (
                str(bnch.pgm), bnch.pgm.rank,
                bnch.obcount-len(bnch.obs), bnch.obcount, pct,
                uncompleted_s))
        out_f.write("\n")
        out_f.write("Total time: avail=%8.2f sched=%8.2f unsched=%8.2f min\n" % (total_avail, (total_avail - total_waste), total_waste))
        self.summary_report = out_f.getvalue()
        out_f.close()
        self.logger.info(self.summary_report)


    def select_schedule(self, schedule):
        self.selected_schedule = schedule
        self.make_callback('schedule-selected', schedule)

# END
