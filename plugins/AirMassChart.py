#
# AirMassChart.py -- AirMass chart plugin
# 
# Eric Jeschke (eric@naoj.org)
#

from PyQt4 import QtGui, QtCore
from matplotlib.backends.backend_qt4agg import FigureCanvasQTAgg as FigureCanvas
import matplotlib

import PlBase

from ginga.misc import Bunch
# for printing target trajectory graphs
import observer

class AirMassChartCanvas(FigureCanvas):
    def __init__(self, figure, parent=None):

        FigureCanvas.__init__(self, figure)
        self.setParent(parent)

        FigureCanvas.setSizePolicy(self, QtGui.QSizePolicy.Expanding,
                                   QtGui.QSizePolicy.Expanding)
        FigureCanvas.updateGeometry(self)

        self.w = 700
        self.h = 500
        
    def minimumSizeHint(self):
        return QtCore.QSize(self.w, self.h)

    def sizeHint(self):
         return QtCore.QSize(self.w, self.h)
  

class AirMassChart(PlBase.Plugin):

    def __init__(self, model, view, controller, logger):
        super(AirMassChart, self).__init__(model, view, controller, logger)

        self.schedules = {}
        
        model.add_callback('schedule-added', self.new_schedule_cb)
        model.add_callback('schedule-selected', self.show_schedule_cb)

    def build_gui(self, container):

        self.fig = matplotlib.figure.Figure((8, 8))
        self.canvas = AirMassChartCanvas(self.fig)

        layout = QtGui.QVBoxLayout()
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(4)
        container.setLayout(layout)

        layout.addWidget(self.canvas, stretch=1)

    def show_schedule_cb(self, qmodel, schedule):
        try:
            info = self.schedules[schedule]
            if info.num_tgts == 0:
                self.logger.debug("no targets for plotting airmass")
                self.view.gui_do(self.fig.clf)
            else:
                self.logger.debug("plotting airmass")
                self.view.gui_do(observer.plots.do_plot_airmass,
                                 info.obs, self.fig)
            self.view.gui_do(self.canvas.draw)
        except KeyError:
            pass

        return True

    def add_schedule(self, schedule):
        self.logger.debug("adding schedule %s" % (schedule))
        
        start_time = schedule.start_time
        t = start_time.astimezone(self.model.timezone)
        ndate = t.strftime("%Y/%m/%d")

        targets = []
        obs = observer.Observer('subaru')

        for slot in schedule.slots:

            ob = slot.ob
            if ob != None:
                if len(ob.comment) == 0:
                    # not an OB generated to serve another OB
                    tgt = ob.target
                    targets.append(obs.target(tgt.name, tgt.ra, tgt.dec))

        # make airmass plot
        num_tgts = len(targets)
        if num_tgts > 0:
            obs.almanac(ndate)
            #print obs.almanac_data
            obs.airmass(*targets)

        self.schedules[schedule] = Bunch.Bunch(obs=obs, num_tgts=num_tgts)

    def new_schedule_cb(self, qmodel, schedule):
        self.add_schedule(schedule)

#END
