from __future__ import print_function
#
# Report.py -- Report plugin
#
# Eric Jeschke (eric@naoj.org)
#
import time
import os
import re
from io import BytesIO, StringIO
from datetime import timedelta

from ginga.gw import Widgets
from ginga.misc import Bunch

from qplan import qsim
from qplan.plugins import PlBase, HSC
import six

class Report(PlBase.Plugin):

    def __init__(self, model, view, controller, logger):
        super(Report, self).__init__(model, view, controller, logger)

        self.schedules = {}
        self.cur_schedule = None

        sdlr = self.model.get_scheduler()
        sdlr.add_callback('schedule-added', self.new_schedule_cb)
        sdlr.add_callback('schedule-cleared', self.clear_schedule_cb)

        model.add_callback('schedule-selected', self.show_schedule_cb)

        self.captions = (('Make OPE', 'button'),
                    )
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

        w, b = Widgets.build_info(self.captions, orientation='vertical')
        self.w = b

        b.make_ope.add_callback('activated', self.make_ope_cb)

        self.vbox.add_widget(w, stretch=0)

        self.gui_up = True

    def make_ope_cb(self, w):

        try:
            ope_buf = self.make_ope()

            top_w = Widgets.TopLevel()
            vbox = Widgets.VBox()
            vbox.set_border_width(2)
            vbox.set_spacing(2)

            tw = Widgets.TextArea(wrap=False)
            vbox.add_widget(tw, stretch=1)

            hbox = Widgets.HBox()
            btn = Widgets.Button('Close')
            hbox.add_widget(btn, stretch=0)
            save_as = Widgets.Button('Save As')
            hbox.add_widget(save_as, stretch=0)
            ope_name = "Queue-" + time.strftime("%Y%m%d-%H%M%S",
                                                time.localtime()) + ".ope"
            path = os.path.join(os.environ['HOME'], "Procedure", ope_name)
            ent = Widgets.TextEntry('path')
            ent.set_text(path)
            hbox.add_widget(ent, stretch=1)
            #hbox.add_widget(Widgets.Label(''), stretch=1)
            hbox.cfg_expand(0x8, 0x124)
            vbox.add_widget(hbox, stretch=0)

            save_as.add_callback('activated',
                                 lambda w: self.save_as_cb(ope_buf, ent))

            top_w.set_widget(vbox)
            btn.add_callback('activated', lambda w: top_w.delete())
            top_w.add_callback('close', lambda *args: top_w.delete())

            tw.set_text(ope_buf)
            top_w.resize(700, 900)
            # TODO: better title
            top_w.set_title("Generated OPE file")

            top_w.show()

        except Exception as e:
            self.logger.error("Error creating OPE file: %s" % (str(e)))

        return True


    def make_ope(self):

        oblist = self._get_selected_obs()
        targets = self._get_targets(oblist)

        try:
            converter = HSC.Converter(self.logger)

            # buffer for OPE output
            if six.PY2:
                out_f = BytesIO()
            else:
                out_f = StringIO()

            # write preamble
            converter.write_ope_header(out_f, targets)

            # convert each OB
            for ob in oblist:
                converter.ob_to_ope(ob, out_f)

            # write postscript
            converter.write_ope_trailer(out_f)

            # here's the OPE file
            ope_buf = out_f.getvalue()
            self.logger.debug("Conversion produced:\n" + ope_buf)

            return ope_buf

        except Exception as e:
            self.logger.error("Error making OPE file: %s" % (str(e)))


    def save_as_cb(self, ope_buf, ent_w):

        filepath = ent_w.get_text().strip()
        try:
            with open(filepath, 'w') as out_f:
                out_f.write(ope_buf)

        except Exception as e:
            self.logger.error("Error writing OB file: %s" % (str(e)))

        return True


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
        sdlr = self.model.get_scheduler()
        t = start_time.astimezone(sdlr.timezone)
        ndate = t.strftime("%Y-%m-%d")
        filters = ', '.join(schedule.data.filters)

        if six.PY2:
            out_f = BytesIO()
        else:
            out_f = StringIO()
        out_f.write("--- NIGHT OF %s --- filters: %s\n" % (
            ndate, filters))
        out_f.write("Queue prepared at: %s\n" % (
            time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())))
        out_f.write("%-16.16s  %-8.8s  %-10.10s %12.12s  %5.5s %7.7s %-10.10s %-6.6s  %3.3s  %s\n" % (
            'Date', 'ObsBlk', 'Code', 'Program', 'Rank', 'Time',
            'Target', 'Filter', 'AM', 'Comment'))

        targets = {}
        for slot in schedule.slots:

            t = slot.start_time.astimezone(sdlr.timezone)
            date = t.strftime("%Y-%m-%d %H:%M")
            ob = slot.ob
            if ob != None:
                t_prog = slot.start_time + timedelta(0, ob.total_time)
                comment = ob.comment
                if not ob.derived:
                    # not an OB generated to serve another OB
                    key = (ob.target.ra, ob.target.dec)
                    targets[key] = ob.target

                out_f.write("%-16.16s  %-8.8s  %-10.10s %12.12s  %5.2f %7.2f %-10.10s %-6.6s  %3.1f  %s\n" % (
                    date, str(ob), ob.name, ob.program, ob.program.rank,
                    ob.total_time / 60, ob.target.name,
                    ob.inscfg.filter, ob.envcfg.airmass,
                    comment))
            else:
                out_f.write("%-16.16s  %-8.8s\n" % (date, str(ob)))

        out_f.write("\n")
        time_avail = (schedule.stop_time - schedule.start_time).total_seconds() / 60.0
        waste = res.time_waste_sec / 60.0
        out_f.write("%d targets  %d filter exch  Time: avail=%.2f sched=%.2f unsched=%.2f min\n" % (
            len(targets), res.num_filter_exchanges, time_avail, (time_avail - waste), waste))
        out_f.write("\n")

        self.schedules[schedule] = Bunch.Bunch(report=out_f.getvalue())
        out_f.close()

        return True

    def new_schedule_cb(self, sdlr, schedule):
        self.add_schedule(schedule)
        return True

    def clear_schedule_cb(self, sdlr):
        self.cur_schedule = None
        if self.gui_up:
            # NOTE: this needs to be a gui_call!
            self.view.gui_call(self.tw.set_text, '')
        return True

    def get_ob(self, obkey):
        for slot in self.cur_schedule.slots:
            ob = slot.ob
            if (ob is not None) and (ob.id == obkey):
                return ob
        print(("%s not found!" % obkey))
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

    def _get_targets(self, oblist):
        targets = set([])
        for ob in oblist:
            targets.add(ob.target)
        return targets


#END
