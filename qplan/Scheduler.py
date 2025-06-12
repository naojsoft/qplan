#
# Scheduler.py -- Observing Queue Scheduler
#
#  E. Jeschke
#
import time
from datetime import timedelta
import numpy
from io import StringIO

# 3rd party imports
from ginga.misc import Callback, Bunch

# local imports
from . import entity
from . import qsim
from .util import qsort, dates
from .util.eph_cache import EphemerisCache

# maximum rank for a program
max_rank = 10.0

# time (sec) beyond which we breakout a slew into it's own OB
slew_breakout_limit = 3.0 * 60.0


class Scheduler(Callback.Callbacks):

    def __init__(self, logger, observer):
        Callback.Callbacks.__init__(self)

        self.logger = logger

        self.site = observer
        self.timezone = observer.tz_local
        self.eph_cache = EphemerisCache(logger, precision_minutes=5)

        # these are the main data structures used to schedule
        self.oblist = []
        self.schedule_recs = []
        self.programs = dict()
        self.apriori_info = dict()
        self.sch_params = Bunch.Bunch(limit_filter=None, allow_delay=True,
                                      slew_breakout_limit=slew_breakout_limit)

        # for schedule_all() method
        self.schedules = []
        self.completed = []
        self.uncompleted = []
        self.unschedulable = []

        # FOR SCALING PURPOSES ONLY, define maximums
        # (see cmp_res() )
        self.max_slew = 20*60.0          # max slew (sec)
        self.max_rot = 20*60.0           # max rotation (sec)
        self.max_rank = 10.0             # max rank
        self.max_delay = 60*60*10.0      # max wait for visibility (sec)
        self.max_filterchange = 35*60.0  # max filter exchange time (sec)

        # define weights (see cmp_res() method)
        self.weights = Bunch.Bunch(w_rank=0.3, w_delay=0.2,
                                   w_slew=0.2, w_priority=0.1,
                                   w_filterchange=0.3, w_qcp=0.0)

        # For callbacks
        for name in ('schedule-cleared', 'schedule-added', 'schedule-completed',):
            self.enable_callback(name)

        # if set to false, will not remove OBs scheduled for a night
        # and they may be rescheduled
        self.remove_scheduled_obs = True

    def set_weights(self, weights):
        self.weights.update(weights)

    def set_programs_info(self, info, ignore_pgm_skip_flag=False):
        self.programs = {}
        # Note: if the ignore_pgm_skip_flag is set to True, then we
        # don't pay attention to the "skip" flag in the Programs sheet
        # and thus include all programs that are in the Programs
        # sheet. Otherwise, we do pay attention to the "skip" flag and
        # ignore all Programs that have the "skip" flag set.
        for key, rec in info.items():
            if ignore_pgm_skip_flag or not rec.skip:
                self.programs[key] = rec

    def set_oblist_info(self, info):
        self.oblist = info

    def set_schedule_info(self, info):
        # Set our schedule_recs attribute to the supplied data
        # structure.
        self.schedule_recs = info

    def set_apriori_program_info(self, info):
        """
        This is where information about programs is stored for the purposes
        of scheduling.  For example, the amount of time already spent observing
        each program (in executed OBs with "good" FQA).
        """
        self.apriori_info = info

    def set_scheduling_params(self, params):
        self.sch_params.update(params)

    def get_sched_time(self, prop, bnch, start_time):
        try:
            pgm = self.programs[prop]
            info = self.apriori_info[prop]
            # get intensive program information
            intensives = self.apriori_info.get('intensives', [])
            if prop in intensives:
                # intensive program: only update scheduled time by what
                # has been observed this semester
                sem = dates.get_semester_by_datetime(start_time, self.timezone)
                bnch.update(dict(sched_time=info[f'sched_time_{sem}'],
                                 obcount=info[f'obcount_{sem}']))
            else:
                # normal program
                bnch.update(info)

        except KeyError:
            pass

    def _ob_code(self, ob):
        return "%s/%s" % (ob.program, ob.name)

    def cmp_res(self, res1, res2):
        """
        Compare two results from check_slot.

        Calculate a number based on the
        - slew time to target (weight: w_slew)
        - delay until target visible (weight: w_delay)
        - time lost (if any) having to change
             filters (weight: self.w_filterchange)
        - rank of the program (weight: w_rank)
        - queue coordinators priority for program (weight: w_qcp)

        LOWER NUMBERS ARE BETTER!
        """
        # TODO: turn this into a table-based iterative calculation,
        # where all factors and weights are parameterized.  Can this
        # be done without slowing it down significantly?
        wts = self.weights
        t1 = t2 = 0.0

        # slew time factor
        r1_slew = min(res1.slew_sec, self.max_slew) / self.max_slew
        t1 += wts.w_slew * r1_slew
        r2_slew = min(res2.slew_sec, self.max_slew) / self.max_slew
        t2 += wts.w_slew * r2_slew

        # delay time factor
        r1_delay = min(res1.delay_sec, self.max_delay) / self.max_delay
        t1 += wts.w_delay * r1_delay
        r2_delay = min(res2.delay_sec, self.max_delay) / self.max_delay
        t2 += wts.w_delay * r2_delay

        # filter exchange time factor
        r1_filter = (min(res1.filterchange_sec, self.max_filterchange) /
                     self.max_filterchange)
        t1 += wts.w_filterchange * r1_filter
        r2_filter = (min(res2.filterchange_sec, self.max_filterchange) /
                    self.max_filterchange)
        t2 += wts.w_filterchange * r2_filter

        # program rank factor
        r1_rank = min(res1.ob.program.rank, self.max_rank) / self.max_rank
        # invert because higher rank should make a lower number
        r1_rank = 1.0 - r1_rank
        t1 += wts.w_rank * r1_rank
        r2_rank = min(res2.ob.program.rank, self.max_rank) / self.max_rank
        r2_rank = 1.0 - r2_rank
        t2 += wts.w_rank * r2_rank

        # queue coordinator priority
        t1 += wts.w_qcp * res1.ob.program.qc_priority
        t2 += wts.w_qcp * res2.ob.program.qc_priority

        if res1.ob.program == res2.ob.program:
            # for OBs in the same program, factor in PI's OB priority
            t1 += wts.w_priority * res1.ob.priority
            t2 += wts.w_priority * res2.ob.priority

        res = int(numpy.sign(t1 - t2))
        ## self.logger.debug("%s : %f   %s : %f" % (
        ##     self._ob_code(res1.ob), t1, self._ob_code(res2.ob), t2))
        return res

    def eval_slot(self, schedule, slot, site, oblist):

        # evaluate each OB against this slot
        results = map(lambda ob: qsim.check_slot(site, schedule, slot, ob, self.eph_cache,
                                                 limit_filter=self.sch_params.limit_filter,
                                                 allow_delay=self.sch_params.allow_delay),
                           oblist)

        # filter out unobservable OBs
        good = list(filter(lambda res: res.obs_ok, results))
        bad = list(filter(lambda res: not res.obs_ok, results))

        # sort according to desired criteria
        # NOTE: we cannot use python's built in sort with this comparison
        # function, even using functools.cmp_to_key (!) It does not give
        # correct results!!
        good = qsort.qsort(good, cmp_fn=self.cmp_res)

        return good, bad

    def fill_schedule(self, schedule, site, oblist, props):
        """Fill a schedule for observations.

        Fill the schedule `schedule` for observations from site `site` using
        observation blocks from `oblist` with OB<->proposal index `props`.

        Parameters
        ----------
        schedule : `~qplan.entity.Schedule` object
            The schedule to be filled

        site : `~qplan.util.calcpos.Observer` object
            The object representing the observing site

        oblist : list of `~qplan.entity.OB` objects
            A list of observation block objects that *may* be observable

        props : dict
            A dict of information about proposals

        Returns
        -------
        unused : list of OBs from `oblist` that were NOT scheduled
        """
        # check all available OBs against this slot and remove those
        # that cannot be used in this schedule a priori (e.g. wrong instrument, etc.)
        usable, cantuse, results = qsim.check_schedule_invariant(site, schedule, oblist)
        for ob in cantuse:
            res = results[ob]
            ob_id = self._ob_code(res.ob)
            self.logger.debug("rejected %s (%s) because: %s" % (
                res.ob, ob_id, res.reason))

        # make a visibility map, and reject OBs that are not visible
        # during this night for long enough to meet the exposure times
        # NOTE: this should populate the eph_cache for the night
        usable, bad, obmap = qsim.check_night_visibility(site, schedule, usable,
                                                         self.eph_cache)
        cantuse.extend(bad)
        for ob in bad:
            res = obmap[str(ob)]
            ob_id = self._ob_code(res.ob)
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

            # evaluate this slot against the available OBs
            # with knowledge of the previous slot
            self.logger.debug("considering slot %s" % (slot))
            good, bad = self.eval_slot(schedule, slot, site, oblist)

            # remove OBs that can't work in the slot and explain why
            for res in bad:
                ob = res.ob
                ob_id = self._ob_code(ob)
                self.logger.debug("rejected %s (%s) because: %s" % (
                    ob, ob_id, res.reason))
                cantuse.append(ob)
                oblist.remove(ob)

            # insert top slot/ob into the schedule
            found_one = False
            for idx, res in enumerate(good):
                ob = res.ob
                ob_id = self._ob_code(ob)
                # check whether this proposal has exceeded its allotted time
                # if we schedule this OB
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

            # expand slot and OB into schedule
            self.ob_slot_into_schedule(schedule, slot, res)

            # finally, remove this OB from the list
            oblist.remove(ob)

        # return list of unused OBs
        oblist.extend(cantuse)
        return oblist

    def ob_slot_into_schedule(self, schedule, slot, res):

        ob = res.ob
        dur = ob.total_time / 60.0

        # a derived ob to setup the overall OB
        new_ob = ob.setup_ob()
        _xx, s_slot, slot = slot.split(slot.start_time, new_ob.total_time)
        s_slot.set_ob(new_ob)
        schedule.insert_slot(s_slot)

        # if a filter change is required, insert a separate OB for that
        if res.filterchange:
            _xx, f_slot, slot = slot.split(slot.start_time,
                                           res.filterchange_sec)
            new_ob = ob.filterchange_ob(res.filterchange_sec)
            f_slot.set_ob(new_ob)
            schedule.insert_slot(f_slot)

        # if a delay is required, insert a separate OB for that
        # NOTE: sometimes very small delays are recorded--we basically
        # ignore inserting any delay ob for anything less than 2 sec
        if res.delay_sec > 2.0:
            _xx, d_slot, slot = slot.split(slot.start_time,
                                           res.delay_sec)
            new_ob = ob.delay_ob(res.delay_sec)
            d_slot.set_ob(new_ob)
            schedule.insert_slot(d_slot)

        slew_sec = res.slew_sec
        remaining_time = slew_sec + ob.total_time

        # if a long slew is required, insert a separate OB for that
        self.logger.debug("slew time for selected object is %.1f sec" % (
            slew_sec))
        if slew_sec > self.sch_params.slew_breakout_limit:
            _xx, s_slot, slot = slot.split(slot.start_time, slew_sec)
            new_ob = ob.longslew_ob(slew_sec)
            s_slot.set_ob(new_ob)
            schedule.insert_slot(s_slot)
            remaining_time = ob.total_time

        # this is the actual science target ob
        self.logger.debug("assigning %s(%.2fm) to %s" % (
            self._ob_code(ob), dur, slot))
        _xx, a_slot, slot = slot.split(slot.start_time, remaining_time)
        a_slot.set_ob(ob)
        schedule.insert_slot(a_slot)

        # a derived ob to shutdown the overall OB
        new_ob = ob.teardown_ob()
        _xx, q_slot, slot = slot.split(slot.start_time, new_ob.total_time)
        q_slot.set_ob(new_ob)
        schedule.insert_slot(q_slot)

        # remember "current values" in schedule for evaluating next slot
        cur_filter = getattr(ob.inscfg, 'filter', None)
        # NOTE: these may not be defined if it is a dome == 'CLOSED'
        az_stop = res.get('az_stop', qsim.parked_az_deg)
        alt_stop = res.get('alt_stop', qsim.parked_alt_deg)
        rot_stop = res.get('rot_stop', qsim.parked_rot_deg)
        schedule.data.setvals(cur_az=az_stop, cur_el=alt_stop,
                              cur_rot=rot_stop, cur_filter=cur_filter)

    def schedule_all(self):

        self.schedules = []
        self.completed = []
        self.uncompleted = []
        self.unschedulable = []
        self.props = {}
        self.make_callback('schedule-cleared')

        # -- Define fillable slots --
        schedules = []
        night_slots = []
        site = self.site

        # measure performance of scheduling
        t_t1 = time.time()

        for rec in self.schedule_recs:
            if rec.skip:
                continue

            night_start = site.get_date("%s %s" % (rec.date, rec.starttime))

            # rec.date is supplied in schedule.xlsx as the local date
            # for the start of the observing night. If rec.starttime
            # is after midnight, we have to adjust night_start
            # to reflect the correct date.
            if 0 <= night_start.hour <= 9:
                night_start += timedelta(days=1)

            # Assume that stoptime is on the day specified by
            # rec.date, but advance date to next day day if resulting
            # end time is less than the start time
            night_stop = site.get_date("%s %s" % (rec.date, rec.stoptime))
            if night_stop < night_start:
                night_stop += timedelta(days=1)

            # associate available filters and other items with this schedule
            schedules.append(entity.Schedule(night_start, night_stop,
                                             data=rec.data))
            delta = (night_stop - night_start).total_seconds()
            night_slots.append(entity.Slot(night_start, delta,
                                           data=rec.data))

        # check whether there are some OBs that cannot be scheduled
        self.logger.info("checking for unschedulable OBs on these nights from %d OBs" % (len(self.oblist)))
        obmap = qsim.obs_to_slots(self.logger, night_slots, site,
                                  self.oblist, self.eph_cache)

        self.logger.debug('OB MAP')
        for key in obmap:
            self.logger.debug("-- %s --" % key)
            self.logger.debug(str(obmap[key]))
            self.logger.debug("--------")

        schedulable = set([])
        for obs in obmap.values():
            schedulable = schedulable.union(set(obs))
        unschedulable = set(self.oblist) - schedulable
        unschedulable = list(unschedulable)
        self.logger.info("there are %d unschedulable OBs" % (len(unschedulable)))

        self.logger.info("preparing to schedule")
        oblist = list(schedulable)

        # build a lookup table of programs -> OBs
        props = self.props
        total_program_time = 0.0
        for propname in self.programs:
            total_time = self.programs[propname].total_time

            props[propname] = Bunch.Bunch(pgm=self.programs[propname],
                                          obs=[], unschedulable=[],
                                          obcount=0, sched_time=0.0,
                                          total_time=total_time)
            # get time already spent working on this program
            self.get_sched_time(propname, props[propname], night_start)

            total_program_time += total_time

        # count OBs in each program
        total_ob_time = 0.0
        for ob in self.oblist:
            pgmname = str(ob.program)
            ob_key = (pgmname, ob.name)
            props[pgmname].obs.append(ob_key)
            props[pgmname].obcount += 1
            obtime_w_overhead = ob.acct_time
            total_ob_time += obtime_w_overhead

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
        t_t2 = time.time()

        for schedule in schedules:

            start_time = schedule.start_time
            stop_time  = schedule.stop_time
            delta = (stop_time - start_time).total_seconds()
            total_avail += delta / 60.0

            t = start_time.astimezone(self.timezone)
            ndate = t.strftime("%Y-%m-%d")
            #outfile = os.path.join(output_dir, ndate + '.txt')

            self.logger.info("scheduling night %s" % (ndate))

            ## this_nights_obs = unscheduled_obs
            # sort to force deterministic scheduling if the same
            # files are reloaded
            this_nights_obs = sorted(unscheduled_obs, key=str)

            # optomize and rank schedules
            self.fill_schedule(schedule, site, this_nights_obs, props)

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
                        if self.remove_scheduled_obs:
                            unscheduled_obs.remove(ob)
                        pgmname = str(ob.program)
                        ob_key = (pgmname, ob.name)
                        props[pgmname].obs.remove(ob_key)

            waste = res.time_waste_sec / 60.0
            total_waste += waste

            self.logger.info("%d unscheduled OBs left" % (len(unscheduled_obs)))

        t_elapsed = time.time() - t_t2
        self.logger.info("%.2f sec for 2nd part" % (t_elapsed))
        t_elapsed = time.time() - t_t1
        self.logger.info("%.2f sec to schedule all" % (t_elapsed))

        # print a summary
        out_f = StringIO()
        num_obs = len(oblist)
        pct = 0.0
        if num_obs > 0:
            pct = float(num_obs - len(unscheduled_obs)) / float(num_obs)
        out_f.write("%5.2f %% of schedulable OBs scheduled\n" % (pct*100.0))

        self.unschedulable = unschedulable
        if len(unschedulable) > 0:
            out_f.write("\n")
            out_f.write("%d OBs are not schedulable:\n" % (len(unschedulable)))
            ## unschedulable.sort(cmp=lambda ob1, ob2: cmp(ob1.program.proposal,
            ##                                             ob2.program.proposal))

            for ob in unschedulable:
                pgmname = str(ob.program)
                props[pgmname].unschedulable.append(ob)
                out_f.write("%s (%s)\n" % (ob.name, pgmname))
            out_f.write("\n")

        self.unschedulable = unschedulable
        completed, uncompleted = [], []
        for pgmname in self.programs:
            bnch = props[pgmname]
            if (bnch.sched_time >= bnch.total_time or
                len(bnch.obs + bnch.unschedulable) == 0):
                completed.append(bnch)
            else:
                uncompleted.append(bnch)

        # sort by rank
        self.completed = sorted(completed,
                                key=lambda bnch: max_rank - bnch.pgm.rank)
        self.uncompleted = sorted(uncompleted,
                                  key=lambda bnch: max_rank - bnch.pgm.rank)

        self.make_callback('schedule-completed',
                           self.completed, self.uncompleted, self.schedules)

        if len(self.completed) == 0:
            out_f.write("No completed programs\n")
        else:
            out_f.write("Completed programs\n")
            for bnch in self.completed:
                ex_time_hrs = bnch.sched_time / 3600.0
                tot_time_hrs = bnch.total_time / 3600.0
                out_f.write("%-12.12s   %5.2f  %d/%d  %.2f/%.2f hrs\n" % (
                    str(bnch.pgm), bnch.pgm.rank,
                    bnch.obcount-len(bnch.obs + bnch.unschedulable), bnch.obcount,
                    ex_time_hrs, tot_time_hrs))

        out_f.write("\n")

        if len(self.uncompleted) == 0:
            out_f.write("No uncompleted programs\n")
        else:
            out_f.write("Uncompleted programs\n")
            for bnch in self.uncompleted:
                ex_time_hrs = bnch.sched_time / 3600.0
                tot_time_hrs = bnch.total_time / 3600.0
                pct = ex_time_hrs / tot_time_hrs * 100.0
                uncompleted_s = str(list(map(lambda ob_key: ob_key[1],
                                             props[str(bnch.pgm)].obs)))

                out_f.write("%-12.12s   %5.2f  %d/%d  %.2f/%.2f hrs  %5.2f%%  %s\n" % (
                    str(bnch.pgm), bnch.pgm.rank,
                    bnch.obcount-len(bnch.obs), bnch.obcount,
                    ex_time_hrs, tot_time_hrs, pct,
                    uncompleted_s))

        out_f.write("\n")
        out_f.write("Total time: avail=%8.2f sched=%8.2f unsched=%8.2f min\n" % (total_avail, (total_avail - total_waste), total_waste))
        self.summary_report = out_f.getvalue()
        out_f.close()
        self.logger.info(self.summary_report)


    def find_executable_obs(self, slot):

        t1 = time.time()

        # check whether there are some OBs that cannot be scheduled
        self.logger.info("checking for unschedulable OBs on these nights from %d OBs" % (len(self.oblist)))
        obmap = qsim.obs_to_slots(self.logger, [slot], self.site,
                                  self.oblist)

        self.logger.debug('OB MAP')
        for key in obmap:
            self.logger.debug("-- %s --" % key)
            self.logger.debug(str(obmap[key]))
            self.logger.debug("--------")

        schedulable = set([])
        for obs in obmap.values():
            schedulable = schedulable.union(set(obs))
        unschedulable = set(self.oblist) - schedulable
        unschedulable = list(unschedulable)
        self.logger.info("there are %d unschedulable OBs" % (len(unschedulable)))

        oblist = list(schedulable)

        #length = (slot.stop_time - slot.start_time).total_seconds()
        schedule = entity.Schedule(slot.start_time, slot.stop_time,
                                   data=slot.data)
        schedule.insert_slot(slot)
        # check all available OBs against this slot and remove those
        # that cannot be used in this schedule a priori (e.g. wrong instrument, etc.)
        self.logger.info("checking invariants in slot")
        usable, cantuse, results = qsim.check_schedule_invariant(self.site,
                                                                 schedule, oblist)
        self.logger.info("{} OBs excluded by invariants".format(len(cantuse)))

        # Don't think we need this step because we already checked for
        # visibility in the obs_to_slots() above!
        ## self.logger.info("checking visibility of targets in slot")
        ## usable, notvisible, obmap = qsim.check_night_visibility(self.site,
        ##                                                         schedule, usable)
        ## self.logger.info("{} OBs not visible in this slot".format(len(notvisible)))

        self.logger.info("evaluating slot for {} viable OBs".format(len(usable)))
        good, bad = self.eval_slot(None, slot, self.site, usable)

        # Remove any OBs that would make us run over the program's granted
        # time
        self.logger.info("removing any OBs that would exceed program award time")
        props = {}
        for key in self.programs:
            total_time = self.programs[key].total_time

            props[key] = Bunch.Bunch(pgm=self.programs[key], obs=[],
                                     obcount=0, sched_time=0.0,
                                     total_time=total_time)
            # get time already spent working on this program
            self.get_sched_time(key, props[key], slot.start_time)

        #print(props)
        for idx, res in enumerate(list(good)):
            ob = res.ob
            ob_id = self._ob_code(ob)
            # check whether this proposal has exceeded its allotted time
            # if we schedule this OB
            acct_time = ob.acct_time
            key = str(ob.program)
            prop_total = props[key].sched_time + acct_time
            if prop_total > props[key].total_time:
                errmsg = "rejected {} ({}) because adding it would exceed program allotted time".format(str(ob), ob_id)
                self.logger.warning(errmsg)
                res.obs_ok = False
                res.reason = errmsg
                bad.append(res)
                good.remove(res)

        self.logger.info("total time: %.4f sec" % (time.time() - t1))
        return good, bad


    ## def select_schedule(self, schedule):
    ##     self.selected_schedule = schedule
    ##     self.make_callback('schedule-selected', schedule)

    def clear_schedules(self):
        self.schedules = []
        self.make_callback('schedule-cleared')

    def slot_to_schedule(self, slot, info):
        self.schedules = []
        self.make_callback('schedule-cleared')

        schedule = entity.Schedule(slot.start_time, slot.stop_time,
                                   data=slot.data)

        try:
            self.ob_slot_into_schedule(schedule, slot, info)

        except Exception as e:
            self.logger.error("Error filling slot: {}".format(e), exc_info=True)
            return

        self.schedules.append(schedule)
        self.make_callback('schedule-added', schedule)

        return schedule

# END
