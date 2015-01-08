#
# Report.py -- Report plugin
# 
# Eric Jeschke (eric@naoj.org)
#
import time
import re
import StringIO
from datetime import timedelta
import pickle

from PyQt4 import QtGui, QtCore
import PlBase

from ginga.misc import Bunch
from ginga.misc import Widgets
from ginga.qtw import QtHelp

import qsim
import SPCAM


class Report(PlBase.Plugin):

    def __init__(self, model, view, controller, logger):
        super(Report, self).__init__(model, view, controller, logger)

        self.schedules = {}
        self.cur_schedule = None
        
        model.add_callback('schedule-added', self.new_schedule_cb)
        model.add_callback('schedule-selected', self.show_schedule_cb)
        model.add_callback('schedule-cleared', self.clear_schedule_cb)

        self.gui_up = False

    def build_gui(self, container):

        vbox = Widgets.VBox()
        vbox.set_border_width(4)
        vbox.set_spacing(2)
        self.vbox = vbox

        tw = Widgets.TextArea(wrap=False, editable=False)
        #font = self.view.get_font("Courier", 12)
        font = QtGui.QFont("Courier", 12)
        tw.set_font(font)
        self.tw = tw
        
        vbox.add_widget(self.tw, stretch=1)

        captions = (('Send', 'button', 'Resolve', 'button'),
                    )
        w, b = Widgets.build_info(captions, orientation='vertical')
        self.w = b

        b.send.add_callback('activated', self.send_cb)
        b.resolve.add_callback('activated', self.resolve_cb)

        vbox.add_widget(w, stretch=0)

        layout = QtGui.QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        container.setLayout(layout)

        layout.addWidget(vbox.get_widget(), stretch=1)

        self.gui_up = True

    def set_text(self, text):
        # TODO: figure out why we have to keep setting the font
        # after the text is cleared
        #font = self.view.get_font("Courier", 12)
        font = QtGui.QFont("Courier", 12)
        self.tw.set_font(font)
        self.tw.set_text(str(text))
        ## self.tw.moveCursor(QtGui.QTextCursor.Start)
        ## self.tw.moveCursor(QtGui.QTextCursor.StartOfLine)
        ## self.tw.ensureCursorVisible()

    def show_schedule_cb(self, qmodel, schedule):
        try:
            self.cur_schedule = schedule
            info = self.schedules[schedule]

            if self.gui_up:
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
        out_f.write("Queue prepared at: %s\n" % (
            time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())))
        out_f.write("%-16.16s  %-6.6s  %-6.6s  %12.12s  %5.5s %7.7s %-6.6s  %3.3s  %s\n" % (
            'Date', 'ObsBlk', 'Status', 'Program', 'Rank', 'Time', 'Filter', 'AM', 'Comment'))

        targets = {}
        for slot in schedule.slots:

            t = slot.start_time.astimezone(self.model.timezone)
            date = t.strftime("%Y-%m-%d %H:%M")
            ob = slot.ob
            if ob != None:
                t_prog = slot.start_time + timedelta(0, ob.total_time)
                comment = ob.comment
                if not ob.derived:
                    # not an OB generated to serve another OB
                    comment = ob.target.name
                    key = (ob.target.ra, ob.target.dec)
                    targets[key] = ob.target

                out_f.write("%-16.16s  %-6.6s  %-6.6s  %12.12s  %5.2f %7.2f %-6.6s  %3.1f  %s\n" % (
                    date, str(ob), ob.status, ob.program, ob.program.rank,
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

    def clear_schedule_cb(self, qmodel):
        self.cur_schedule = None
        if self.gui_up:
            self.view.gui_do(self.tw.set_text, '')
        return True

    def get_ob(self, obkey):
        for slot in self.cur_schedule.slots:
            ob = slot.ob
            if (ob is not None) and (ob.id == obkey):
                return ob
        print("%s not found!" % obkey)
        raise KeyError(obkey)
        
    def _get_selected_obs(self):
        
        buf = self.tw.get_text()
        w = self.tw.get_widget()
        try:
            cursor = w.textCursor()
            start, end = cursor.selectionStart(), cursor.selectionEnd()

            # back up to beginning of line if selection doesn't
            # start from a line
            if (start > 0) and (buf[start-1] != '\n'):
                while buf[start-1] != '\n':
                    start -= 1
                    if start == 0:
                        break
                    
            # back up to beginning of line if selection doesn't
            # start from a line
            length = len(buf)
            if end >= length:
                end = length
            else:
                while buf[end] != '\n':
                    end += 1
                    if end >= length:
                        end = length
                        break

            selected = buf[start:end]
            selected = selected.encode('ascii', 'replace')

            # get the selected OBs
            oblist = []
            for line in selected.split('\n'):
                match = re.match(r'^\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}\s+(ob\w+)',
                                 line)
                if match:
                    obkey = match.group(1)
                    ob = self.get_ob(obkey)
                    oblist.append(ob)

            #print(oblist)
            return oblist
        
        except Exception as e:
            self.logger.error("Error selecting OBs: %s" % (str(e)))
            return []


    def send_cb(self, w):

        oblist = self._get_selected_obs()

        try:
            converter = SPCAM.Converter(self.logger)

            # buffer for OPE output
            out_f = StringIO.StringIO()

            # write preamble
            converter.write_ope_header(out_f)

            # convert each OB
            for ob in oblist:
                converter.ob_to_ope(ob, out_f)

            # here's the OPE file
            ope_buf = out_f.getvalue()
            print(ope_buf)

        except Exception as e:
            self.logger.error("Error sending OBs: %s" % (str(e)))

        return True


    def resolve_cb(self, w):
        oblist = self._get_selected_obs()

        try:
            obj = self.view.get_plugin('Resolution')
            obj.resolve_obs(oblist)

        except Exception as e:
            self.logger.error("Error resolving OBs: %s" % (str(e)))

        return True

#END
