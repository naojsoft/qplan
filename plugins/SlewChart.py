#
# SlewChart.py -- Slew chart plugin
# 
# Eric Jeschke (eric@naoj.org)
#

from PyQt4 import QtGui, QtCore
from matplotlib.backends.backend_qt4agg import FigureCanvasQTAgg as FigureCanvas

import PlBase

from ginga.misc import Bunch
import azelplot as azelplot

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

    def build_gui(self, container):

        print "making figure"
        self.plot = azelplot.AZELPlot(6, 6)

        print "making canvas"
        canvas = SlewChartCanvas(self.plot.get_figure())

        layout = QtGui.QVBoxLayout()
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(4)
        container.setLayout(layout)

        layout.addWidget(canvas, stretch=1)
        print "GUI done"


    def show_schedule_cb(self, model, schedule):
        try:
            info = self.schedules[schedule]

            if not self.initialized:
                self.plot.setup()
                self.initialized = True
            
            # make slew plot
            self.logger.debug("plotting slew map")
            self.view.gui_do(self.plot.clear)
            self.view.gui_do(self.plot.plot_coords, info.targets)

        except KeyError:
            pass

        return True

    def add_schedule(self, schedule):
        target_list = []
        for slot in schedule.slots:

            ob = slot.ob
            if ob != None:
                if len(ob.comment) == 0:
                    # not an OB generated to serve another OB
                    key = (ob.target.ra, ob.target.dec)
                    info = ob.target.calc(self.model.site, slot.start_time)
                    target_list.append((info.az_deg, info.alt_deg,
                                        ob.target.name))

        self.schedules[schedule] = Bunch.Bunch(targets=target_list)
        return True

    def new_schedule_cb(self, model, schedule):
        self.add_schedule(schedule)
        return True

        
#END
