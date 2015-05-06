#
# SumChart.py -- Summary chart plugin
#
# Russell Kackley (rkackley@naoj.org)
#
from PyQt4 import QtGui, QtCore
import PlBase
from matplotlib.backends.backend_qt4agg import FigureCanvasQTAgg as FigureCanvas
import plots.summary as ps

class SumChartCanvas(FigureCanvas):
    def __init__(self, figure, parent=None):

        FigureCanvas.__init__(self, figure)
        self.setParent(parent)

        self.w = 700
        self.h = 500

        FigureCanvas.setSizePolicy(self, QtGui.QSizePolicy.Expanding,
                                   QtGui.QSizePolicy.Expanding)
        FigureCanvas.updateGeometry(self)

    def minimumSizeHint(self):
        return QtCore.QSize(self.w, self.h)

    def sizeHint(self):
        return QtCore.QSize(self.w, self.h)

class BaseSumChart(PlBase.Plugin):

    def __init__(self, model, view, controller, logger):
        super(BaseSumChart, self).__init__(model, view, controller, logger)

        self.initialized = False

        model.add_callback('schedule-completed', self.schedule_completed_cb)

    def schedule_completed_cb(self, model, completed, uncompleted, schedules):
        self.logger.debug('schedule_completed_cb called')

class NightSumChart(BaseSumChart):
    # Night summary chart showing activities planned for the night

    def build_gui(self, container):

        self.plot = ps.NightSumPlot(8, 6, logger=self.logger)

        canvas = SumChartCanvas(self.plot.get_figure())

        layout = QtGui.QVBoxLayout()
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(4)
        container.setLayout(layout)

        layout.addWidget(canvas, stretch=1)

    def schedule_completed_cb(self, model, completed, uncompleted, schedules):
        self.logger.debug('schedule_completed_cb called')
        self.view.gui_do(self.plot.clear)
        self.view.gui_do(self.plot.plot, schedules)

class ProposalSumChart(BaseSumChart):
    # Proposal summary chart showing percentage of completed and
    # uncompleted OB's for each proposal

    def build_gui(self, container):

        self.plot = ps.ProposalSumPlot(8, 6, logger=self.logger)

        canvas = SumChartCanvas(self.plot.get_figure())

        layout = QtGui.QVBoxLayout()
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(4)
        container.setLayout(layout)

        layout.addWidget(canvas, stretch=1)

    def schedule_completed_cb(self, model, completed, uncompleted, schedules):
        self.logger.debug('schedule_completed_cb called')
        self.view.gui_do(self.plot.clear)
        self.view.gui_do(self.plot.plot, completed, uncompleted)

class SchedSumChart(BaseSumChart):
    # Schedule summary chart showing number of minutes scheduled and
    # unscheduled for each night

    def build_gui(self, container):

        self.plot = ps.ScheduleSumPlot(8, 6, logger=self.logger)

        canvas = SumChartCanvas(self.plot.get_figure())

        layout = QtGui.QVBoxLayout()
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(4)
        container.setLayout(layout)

        layout.addWidget(canvas, stretch=1)

    def schedule_completed_cb(self, model, completed, uncompleted, schedules):
        self.logger.debug('schedule_completed_cb called')
        self.view.gui_do(self.plot.clear)
        self.view.gui_do(self.plot.plot, schedules)

class SemesterSumChart(BaseSumChart):
    # Semester summary chart showing percentage of time allocated to
    # each proposal and also the percentage of unscheduled time

    def build_gui(self, container):

        self.plot = ps.SemesterSumPlot(8, 6, logger=self.logger)

        canvas = SumChartCanvas(self.plot.get_figure())

        layout = QtGui.QVBoxLayout()
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(4)
        container.setLayout(layout)

        layout.addWidget(canvas, stretch=1)

    def schedule_completed_cb(self, model, completed, uncompleted, schedules):
        self.logger.debug('schedule_completed_cb called')
        self.view.gui_do(self.plot.clear)
        self.view.gui_do(self.plot.plot, schedules)
