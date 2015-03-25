#
# AirMassChart.py -- AirMass chart plugin
# 
# Eric Jeschke (eric@naoj.org)
#
from __future__ import print_function
from datetime import timedelta
#import pytz

from PyQt4 import QtGui, QtCore
from matplotlib.backends.backend_qt4agg import FigureCanvasQTAgg as FigureCanvas
import matplotlib

from ginga.misc import Bunch

import PlBase
from plots.airmass import plot_airmass


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
        # Set preferred timezone for plot
        #self.tz = pytz.utc
        self.tz = model.timezone
        
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
                self.view.gui_do(plot_airmass, self.fig, info, self.tz)
            self.view.gui_do(self.canvas.draw)
        ## except KeyError:
        ##     pass
        except Exception as e:
            self.logger.error("Error plotting airmass: %s" % (str(e)))

        return True

    def add_schedule(self, schedule):
        self.logger.debug("adding schedule %s" % (schedule))
        
        start_time = schedule.start_time
        t = start_time.astimezone(self.model.timezone)
        # if schedule starts after midnight, change start date to the
        # day before, this is due to the way the Observer module charts
        # airmass
        if 0 <= t.hour < 12:
            t -= timedelta(0, 3600*12)
        ndate = t.strftime("%Y/%m/%d")

        targets = []
        site = self.model.site
        site.set_date(start_time)

        for slot in schedule.slots:
            ob = slot.ob
            print((slot, ob))
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
                info_list = site.get_target_info(tgt)
                target_data.append(Bunch.Bunch(history=info_list, target=tgt))
                lengths.append(len(info_list))

        # clip all arrays to same length
        min_len = min(*lengths)
        for il in target_data:
            il.history = il.history[:min_len]

        self.schedules[schedule] = Bunch.Bunch(site=site, num_tgts=num_tgts,
                                               target_data=target_data)

    def new_schedule_cb(self, qmodel, schedule):
        self.add_schedule(schedule)


#END
