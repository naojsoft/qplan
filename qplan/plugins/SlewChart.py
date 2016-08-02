#
# SlewChart.py -- Slew chart plugin
#
# Eric Jeschke (eric@naoj.org)
#
from datetime import datetime

from ginga.misc import Bunch
from ginga.gw import Widgets, Plot

from qplan.plugins import PlBase
from qplan.plots.polarsky import AZELPlot
from qplan import common


class SlewChart(PlBase.Plugin):

    def __init__(self, model, view, controller, logger):
        super(SlewChart, self).__init__(model, view, controller, logger)

        self.schedules = {}
        self.initialized = False

        sdlr = self.model.get_scheduler()
        sdlr.add_callback('schedule-cleared', self.clear_schedule_cb)
        sdlr.add_callback('schedule-added', self.new_schedule_cb)
        model.add_callback('schedule-selected', self.show_schedule_cb)

        # the solar system objects
        self.ss = [ common.moon, common.sun,
                    #common.mercury, common.venus,
                    #common.mars, common.jupiter, common.saturn,
                    #common.uranus, common.neptune, common.pluto,
                    ]
        self.ss_colors = [ 'white', 'yellow', 'orange', 'lightgreen', 'red',
                           'white', 'turquoise', 'salmon', 'plum' ]

    def build_gui(self, container):

        self.plot = AZELPlot(600, 600, logger=self.logger)

        canvas = Plot.PlotWidget(self.plot, width=600, height=600)

        container.set_margins(2, 2, 2, 2)
        container.set_spacing(4)

        container.add_widget(canvas, stretch=1)


    def show_schedule_cb(self, model, schedule):
        try:
            info = self.schedules[schedule]

        except KeyError:
            return True

        if not self.initialized:
            self.plot.setup()
            self.initialized = True

        # make slew plot
        self.logger.debug("plotting slew map")
        self.view.gui_do(self.plot.clear)

        # plot a subset of the targets
        idx = int((self.controller.idx_tgt_plots / 100.0) * len(info.targets))
        num_tgts = self.controller.num_tgt_plots
        targets = info.targets[idx:idx+num_tgts]
        self.view.gui_do(self.plot.plot_coords, targets)

        # plot the current location of solar system objects
        sdlr = model.get_scheduler()
        site = sdlr.site
        dt = datetime.now(site.tz_local)
        self.view.gui_do(self.plot.plot_targets, site,
                         self.ss, dt, self.ss_colors)

        return True

    def add_schedule(self, schedule):
        target_list = []
        i = 0
        sdlr = self.model.get_scheduler()

        for slot in schedule.slots:

            ob = slot.ob
            if ob != None:
                if not ob.derived:
                    # not an OB generated to serve another OB
                    key = (ob.target.ra, ob.target.dec)
                    info = ob.target.calc(sdlr.site, slot.start_time)

                    i += 1
                    #txt = "%d [%s]" % (i, ob.target.name)
                    txt = "%d" % (i)
                    target_list.append((info.az_deg, info.alt_deg, txt))

        self.schedules[schedule] = Bunch.Bunch(targets=target_list)
        return True

    def new_schedule_cb(self, sdlr, schedule):
        self.add_schedule(schedule)
        return True

    def clear_schedule_cb(self, sdlr):
        #self.view.gui_call(self.plot.clear)
        return True


#END
