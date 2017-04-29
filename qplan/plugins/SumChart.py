#
# SumChart.py -- Summary chart plugin
#
# Russell Kackley (rkackley@naoj.org)
#
from qtpy import QtCore
from qtpy import QtWidgets as QtGui
from ginga.gw import Plot

from qplan.plots import summary as ps
from qplan.plugins import PlBase

class BaseSumChart(PlBase.Plugin):

    def __init__(self, controller):
        super(BaseSumChart, self).__init__(controller)

        self.initialized = False

        sdlr = self.model.get_scheduler()
        sdlr.add_callback('schedule-completed', self.schedule_completed_cb)

    def schedule_completed_cb(self, sdlr, completed, uncompleted, schedules):
        self.logger.debug('schedule_completed_cb called')

class NightSumChart(BaseSumChart):
    # Night summary chart showing activities planned for the night

    def build_gui(self, container):

        self.plot = ps.NightSumPlot(800, 600, logger=self.logger)
        canvas = Plot.PlotWidget(self.plot)

        container.set_margins(2, 2, 2, 2)
        container.set_spacing(4)
        container.add_widget(canvas, stretch=1)

    def schedule_completed_cb(self, model, completed, uncompleted, schedules):
        self.logger.debug('schedule_completed_cb called')
        self.view.gui_call(self.plot.clear)
        self.view.gui_do(self.plot.plot, schedules)

class ProposalSumChart(BaseSumChart):
    # Proposal summary chart showing percentage of completed and
    # uncompleted OB's for each proposal

    def build_gui(self, container):

        self.plot = ps.ProposalSumPlot(800, 600, logger=self.logger)
        canvas = Plot.PlotWidget(self.plot)

        container.set_margins(2, 2, 2, 2)
        container.set_spacing(4)
        container.add_widget(canvas, stretch=1)

    def schedule_completed_cb(self, model, completed, uncompleted, schedules):
        self.logger.debug('schedule_completed_cb called')
        self.view.gui_call(self.plot.clear)
        self.view.error_wrap(self.plot.plot, completed, uncompleted)

class SchedSumChart(BaseSumChart):
    # Schedule summary chart showing number of minutes scheduled and
    # unscheduled for each night

    def build_gui(self, container):

        self.plot = ps.ScheduleSumPlot(800, 600, logger=self.logger)
        canvas = Plot.PlotWidget(self.plot)

        container.set_margins(2, 2, 2, 2)
        container.set_spacing(4)
        container.add_widget(canvas, stretch=1)

    def schedule_completed_cb(self, model, completed, uncompleted, schedules):
        self.logger.debug('schedule_completed_cb called')
        self.view.gui_call(self.plot.clear)
        self.view.error_wrap(self.plot.plot, schedules)

class SemesterSumChart(BaseSumChart):
    # Semester summary chart showing percentage of time allocated to
    # each proposal and also the percentage of unscheduled time

    def build_gui(self, container):

        self.plot = ps.SemesterSumPlot(800, 600, logger=self.logger)
        canvas = Plot.PlotWidget(self.plot)

        container.set_margins(2, 2, 2, 2)
        container.set_spacing(4)
        container.add_widget(canvas, stretch=1)

    def schedule_completed_cb(self, sldr, completed, uncompleted, schedules):
        self.logger.debug('schedule_completed_cb called')
        self.view.gui_call(self.plot.clear)
        self.view.error_wrap(self.plot.plot, sldr, completed, uncompleted, schedules)
