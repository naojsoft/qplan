#
# Report.py -- Report plugin
# 
# Eric Jeschke (eric@naoj.org)
#
import StringIO
from datetime import timedelta

from ginga.misc import Bunch
import qsim

from PyQt4 import QtGui, QtCore
import PlBase


class Report(PlBase.Plugin):

    def __init__(self, model, view, controller, logger):
        super(Report, self).__init__(model, view, controller, logger)

        self.schedules = {}
        
        model.add_callback('schedule-added', self.new_schedule_cb)
        model.add_callback('schedule-selected', self.show_schedule_cb)

    def build_gui(self, container):

        layout = QtGui.QVBoxLayout()
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(4)
        container.setLayout(layout)

        tw = QtGui.QTextEdit()
        tw.setReadOnly(True)
        tw.setLineWrapMode(QtGui.QTextEdit.NoWrap)
        font = QtGui.QFont("Courier", 12)
        tw.setFont(font)
        self.tw = tw
        
        layout.addWidget(self.tw, stretch=1)

    def set_text(self, text):
        self.tw.clear()
        self.tw.append(str(text))
        self.tw.moveCursor(QtGui.QTextCursor.Start)
        self.tw.moveCursor(QtGui.QTextCursor.StartOfLine)
        self.tw.ensureCursorVisible()

    def show_schedule_cb(self, qmodel, schedule):
        try:
            info = self.schedules[schedule]
            
            self.view.gui_do(self.set_text, info.report)

        except KeyError:
            pass


    def add_schedule(self, schedule):
        res = qsim.eval_schedule(schedule)

        start_time = schedule.start_time
        t = start_time.astimezone(self.model.timezone)
        ndate = t.strftime("%Y-%m-%d")
        filters = ', '.join(schedule.data.filters)

        out_f = StringIO.StringIO()
        out_f.write("--- NIGHT OF %s --- filters: %s\n" % (
            ndate, filters))
        out_f.write("%-16.16s  %-6.6s  %12.12s  %5.5s %7.7s %-6.6s  %3.3s  %s\n" % (
            'Date', 'ObsBlk', 'Program', 'Rank', 'Time', 'Filter', 'AM', 'Comment'))

        targets = {}
        for slot in schedule.slots:

            t = slot.start_time.astimezone(self.model.timezone)
            date = t.strftime("%Y-%m-%d %H:%M")
            ob = slot.ob
            if ob != None:
                t_prog = slot.start_time + timedelta(0, ob.total_time)
                comment = ob.comment
                if len(ob.comment) == 0:
                    # not an OB generated to serve another OB
                    comment = ob.target.name
                    key = (ob.target.ra, ob.target.dec)
                    targets[key] = ob.target

                out_f.write("%-16.16s  %-6.6s  %12.12s  %5.2f %7.2f %-6.6s  %3.1f  %s\n" % (
                    date, str(ob), ob.program, ob.program.rank,
                    ob.total_time / 60,
                    ob.inscfg.filter, ob.envcfg.airmass,
                    comment))
            else:
                out_f.write("%-16.16s  %-6.6s\n" % (date, str(ob)))

        out_f.write("\n")
        waste = res.time_waste_sec / 60.0
        out_f.write("%d targets  %d filter exch  unscheduled: time=%.2f min\n" % (
            len(targets), res.num_filter_exchanges, waste))
        out_f.write("\n")

        self.schedules[schedule] = Bunch.Bunch(report=out_f.getvalue())
        out_f.close()

        return True

    def new_schedule_cb(self, model, schedule):
        self.add_schedule(schedule)
        return True

#END
