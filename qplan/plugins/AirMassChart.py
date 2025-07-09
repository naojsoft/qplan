#
# AirMassChart.py -- AirMass chart plugin
#
#  E. Jeschke
#
from datetime import timedelta

from ginga.gw import Plot
from ginga.misc import Bunch

from qplan.plugins import PlBase
from qplan.plots.airmass import AltitudePlot


class AirMassChart(PlBase.Plugin):

    def __init__(self, controller):
        super(AirMassChart, self).__init__(controller)

        self.schedules = {}
        self.initialized = False

        # Set preferred timezone for plot
        #self.tz = tz.UTC

        sdlr = self.model.get_scheduler()
        self.tz = sdlr.timezone
        sdlr.add_callback('schedule-cleared', self.clear_schedule_cb)
        sdlr.add_callback('schedule-added', self.new_schedule_cb)

        self.model.add_callback('schedule-selected', self.show_schedule_cb)

    def build_gui(self, container):

        self.plot = AltitudePlot(700, 500, logger=self.logger)

        plot_w = Plot.PlotWidget(self.plot, width=700, height=500)

        container.set_margins(2, 2, 2, 2)
        container.set_spacing(4)
        container.add_widget(plot_w, stretch=1)

    def show_schedule_cb(self, qmodel, schedule):
        try:
            info = self.schedules[schedule]

            if not self.initialized:
                self.plot.setup()
                self.initialized = True

            if info.num_tgts == 0:
                self.logger.debug("no targets for plotting airmass")
                self.view.gui_call(self.plot.clear)
            else:
                self.logger.debug("plotting airmass")
                self.view.gui_call(self.plot.clear)
                site = info.site
                target_data = info.target_data

                # Plot a subset of the targets
                idx = int((self.controller.idx_tgt_plots / 100.0) * len(target_data))
                num_tgts = self.controller.num_tgt_plots
                target_data = target_data[idx:idx+num_tgts]

                self.view.error_wrap(self.plot.plot_altitude, site, target_data,
                                     self.tz)
            self.view.error_wrap(self.plot.draw)
        ## except KeyError:
        ##     pass
        except Exception as e:
            self.logger.error("Error plotting airmass: %s" % (str(e)))

        return True

    def add_schedule(self, schedule):
        self.logger.debug("adding schedule %s" % (schedule))

        start_time = schedule.start_time
        sdlr = self.model.get_scheduler()

        # if start time is after midnight, need to subtract a few hours
        # to get the correct day for the target positions
        if 0 <= start_time.hour <= 9:
            start_time = start_time - timedelta(hours=12)

        # calc noon on the day of observation in sdlr time zone
        ndate = start_time.strftime("%Y-%m-%d") + " 12:00:00"
        site = sdlr.site
        noon_time = site.get_date(ndate, timezone=sdlr.timezone)

        # plot period 15 minutes before sunset to 15 minutes after sunrise
        delta = 60*15
        start_time = site.sunset(noon_time) - timedelta(seconds=delta)
        stop_time = site.sunrise(start_time) + timedelta(seconds=delta)

        targets = []
        site.set_date(start_time)

        for slot in schedule.slots:
            ob = slot.ob
            if (ob is not None) and (not ob.derived):
                # not an OB generated to serve another OB
                # TODO: make sure targets are unique in pointing
                targets.append(ob.target)

        # make airmass plot
        num_tgts = len(targets)
        target_data = []
        lengths = []
        if num_tgts > 0:
            for tgt in targets:
                calc_res = site.get_target_info(tgt)
                target_data.append(Bunch.Bunch(calc_res=calc_res, target=tgt))
                lengths.append(len(calc_res))

        # clip all arrays to same length
        min_len = 0
        if len(lengths) > 0:
            min_len = min(lengths)
        # for il in target_data:
        #     il.history = il.history[:min_len]

        self.schedules[schedule] = Bunch.Bunch(site=site, num_tgts=num_tgts,
                                               target_data=target_data, length=min_len)

    def new_schedule_cb(self, qscheduler, schedule):
        self.add_schedule(schedule)

    def clear_schedule_cb(self, qscheduler):
        self.view.gui_call(self.plot.clear)
        self.logger.info("cleared plot")
        return True


#END
