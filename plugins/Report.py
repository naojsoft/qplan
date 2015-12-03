#
# Report.py -- Report plugin
#
# Eric Jeschke (eric@naoj.org)
#
import time
import re
import StringIO
from datetime import timedelta

from ginga.gw import Widgets
import PlBase

from ginga.misc import Bunch

import qsim


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
        self.font = self.view.get_font('Courier', 12)
        tw.set_font(self.font)
        self.tw = tw

        vbox.add_widget(self.tw, stretch=1)

        container.add_widget(vbox, stretch=1)

        self.gui_up = True

    def set_text(self, text):
        # TODO: figure out why we have to keep setting the font
        # after the text is cleared
        self.tw.set_font(self.font)
        self.tw.set_text(str(text))

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
        out_f.write("%-16.16s  %-6.6s  %-10.10s %12.12s  %5.5s %7.7s %-10.10s %-6.6s  %3.3s  %s\n" % (
            'Date', 'ObsBlk', 'Code', 'Program', 'Rank', 'Time',
            'Target', 'Filter', 'AM', 'Comment'))

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
                    key = (ob.target.ra, ob.target.dec)
                    targets[key] = ob.target

                out_f.write("%-16.16s  %-6.6s  %-10.10s %12.12s  %5.2f %7.2f %-10.10s %-6.6s  %3.1f  %s\n" % (
                    date, str(ob), ob.name, ob.program, ob.program.rank,
                    ob.total_time / 60, ob.target.name,
                    ob.inscfg.filter, ob.envcfg.airmass,
                    comment))
            else:
                out_f.write("%-16.16s  %-6.6s\n" % (date, str(ob)))

        out_f.write("\n")
        time_avail = (schedule.stop_time - schedule.start_time).total_seconds() / 60.0
        waste = res.time_waste_sec / 60.0
        out_f.write("%d targets  %d filter exch  Time: avail=%.2f sched=%.2f unsched=%.2f min\n" % (
            len(targets), res.num_filter_exchanges, time_avail, (time_avail - waste), waste))
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

            # find the end of line if selection doesn't
            # end on a line
            length, end = len(buf), end - 1
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


#END
