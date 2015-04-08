#
# SlewChart.py -- Slew chart plugin
# 
# Eric Jeschke (eric@naoj.org)
#
from datetime import datetime

from PyQt4 import QtGui, QtCore
from matplotlib.backends.backend_qt4agg import \
     FigureCanvasQTAgg as FigureCanvas, \
     NavigationToolbar2QTAgg as NavigationToolbar
from ginga.misc import Bunch

import PlBase
from plots.polarsky import AZELPlot
import common

class SlewChartCanvas(FigureCanvas):
    def __init__(self, figure, parent=None):

        FigureCanvas.__init__(self, figure)
        self.setParent(parent)

        self.w = 500
        self.h = 500
        
        FigureCanvas.setSizePolicy(self, QtGui.QSizePolicy.Expanding,
                                   QtGui.QSizePolicy.Expanding)
        FigureCanvas.updateGeometry(self)

    def minimumSizeHint(self):
        return QtCore.QSize(self.w, self.h)

    def sizeHint(self):
         return QtCore.QSize(self.w, self.h)
  

class SlewChart(PlBase.Plugin):

    def __init__(self, model, view, controller, logger):
        super(SlewChart, self).__init__(model, view, controller, logger)

        self.schedules = {}
        self.initialized = False
        
        model.add_callback('schedule-added', self.new_schedule_cb)
        model.add_callback('schedule-selected', self.show_schedule_cb)

        # the solar system objects
        self.ss = [ common.moon, common.sun, common.mercury, common.venus,
                    common.mars, common.jupiter, common.saturn,
                    common.uranus, common.neptune, common.pluto ]
        self.ss_colors = [ 'white', 'yellow', 'orange', 'lightgreen', 'red',
                           'white', 'turquoise', 'salmon', 'plum' ]

    def build_gui(self, container):

        self.plot = AZELPlot(6, 6)

        canvas = SlewChartCanvas(self.plot.get_figure())

        layout = QtGui.QVBoxLayout()
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(4)
        container.setLayout(layout)

        layout.addWidget(canvas, stretch=1)

        ## win = container.window()
        ## toolbar = NavigationToolbar(canvas, win)
        ## layout.addWidget(toolbar, stretch=0)
        
        
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
        site = model.site
        print("getting current time")
        dt = datetime.now(site.tz_local)
        self.view.gui_do(self.plot.plot_targets, site,
                         self.ss, dt, self.ss_colors)
        
        return True

    def add_schedule(self, schedule):
        target_list = []
        i = 0
        for slot in schedule.slots:

            ob = slot.ob
            if ob != None:
                if not ob.derived:
                    # not an OB generated to serve another OB
                    key = (ob.target.ra, ob.target.dec)
                    info = ob.target.calc(self.model.site, slot.start_time)

                    i += 1
                    txt = "%d [%s]" % (i, ob.target.name)
                    target_list.append((info.az_deg, info.alt_deg, txt))

        self.schedules[schedule] = Bunch.Bunch(targets=target_list)
        return True

    def new_schedule_cb(self, model, schedule):
        self.add_schedule(schedule)
        return True

        
#END
