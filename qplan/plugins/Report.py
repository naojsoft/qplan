#
# Report.py -- Report plugin
#
#  E. Jeschke
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

# Gen2 import
have_gen2 = False
try:
    from g2base.remoteObjects import remoteObjects as ro
    have_gen2 = True

except ImportError:
    pass

class Report(PlBase.Plugin):

    def __init__(self, controller):
        super(Report, self).__init__(controller)

        self.schedules = {}
        self.cur_schedule = None

        sdlr = self.model.get_scheduler()
        sdlr.add_callback('schedule-added', self.new_schedule_cb)
        sdlr.add_callback('schedule-cleared', self.clear_schedule_cb)

        self.model.add_callback('schedule-selected', self.show_schedule_cb)

        self.w = Bunch.Bunch()
        self.svcname = 'integgui0'
        self.ig = None
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

        vbox.add_widget(self.tw, stretch=4)

        hbox = Widgets.HBox()
        btn = Widgets.Button('Make OPE')
        btn.add_callback('activated', self.make_ope_cb)
        btn.set_tooltip("Make and examine an OPE file for this schedule")
        btn.set_enabled(False)
        self.w.btn_make_ope = btn
        hbox.add_widget(btn)
        btn = Widgets.Button('Exec integgui2')
        btn.add_callback('activated', self.exec_integgui2_cb)
        btn.set_tooltip("Make an OPE file and send/open in integgui2")
        btn.set_enabled(False)
        self.w.btn_exec_integgui2 = btn
        hbox.add_widget(btn)
        btn = Widgets.Button('Save Report')
        btn.add_callback('activated', self.save_report_cb)
        btn.set_tooltip("Save contents as a text file")
        btn.set_enabled(False)
        self.w.btn_save_report = btn
        hbox.add_widget(btn)

        hbox.add_widget(Widgets.Label(''), stretch=1)
        vbox.add_widget(Widgets.Label(''), stretch=1)
        vbox.add_widget(hbox, stretch=0)

        container.add_widget(vbox, stretch=1)
        self.gui_up = True

    def start(self):
        if have_gen2:
            ro.init()
            self.ig = ro.remoteObjectProxy(self.svcname)

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

            ope_name = self.get_ope_name()
            output_dir = self.controller.output_dir
            if output_dir is None:
                output_dir = os.path.join(os.environ['HOME'], "Procedure",
                                          "Queue")
            path = os.path.join(output_dir, ope_name)
            ent = Widgets.TextEntry('path')
            ent.set_text(path)
            hbox.add_widget(ent, stretch=1)
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

    def get_ope_name(self):
        ope_name = "Queue-" + time.strftime("%Y%m%d-%H%M%S",
                                            time.localtime()) + ".ope"
        name = self.cur_schedule.data.get('ope_name', None)
        if name is not None:
            ope_name = name + ".ope"

        return ope_name

    def make_ope(self):

        oblist = self._get_obs(use_selection=False)
        targets = self._get_targets(oblist)

        try:
            converter = HSC.Converter(self.logger)

            # buffer for OPE output
            out_f = StringIO()
            out = converter._mk_out(out_f)

            # write preamble
            converter.write_ope_header(out, targets)

            # convert each OB
            for ob in oblist:
                converter.ob_to_ope(ob, out)

            # write postscript
            converter.write_ope_trailer(out)

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


    def exec_integgui2_cb(self, w):
        try:
            ope_buf = self.make_ope()

            ope_name = self.get_ope_name()
            output_dir = self.controller.output_dir
            if output_dir is None:
                output_dir = os.path.join(os.environ['HOME'], "Procedure",
                                          "Queue")
            filepath = os.path.join(output_dir, ope_name)

            with open(filepath, 'w') as out_f:
                out_f.write(ope_buf)

            self.logger.info('Report wrote OPE file to {}'.format(filepath))

            # Notify integgui2
            if self.ig is not None:
                self.ig.load_page(filepath)
            else:
                self.logger.info('Gen2 not loaded - cannot send OPE file to integgui')

        except Exception as e:
            self.logger.error("Error creating OPE file: %s" % (str(e)))

    def set_text(self, text):
        # TODO: figure out why we have to keep setting the font
        # after the text is cleared
        self.tw.set_font(self.font)
        self.tw.set_text(str(text))
        self.w.btn_make_ope.set_enabled(True)
        self.w.btn_save_report.set_enabled(True)
        if have_gen2:
            self.w.btn_exec_integgui2.set_enabled(True)

    def save_report_cb(self, w):
        def _save_rpt(path):
            text_buf = self.tw.get_text()

            with open(path, 'w') as out_f:
                out_f.write(text_buf)

        dialog_w = Widgets.SaveDialog(title="Save Report")
        dialog_w.show()

        path = dialog_w.get_path()
        dialog_w.hide()
        dialog_w.deleteLater()
        if path is None:
            return

        self.view.error_wrap(_save_rpt, path)
        return

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

        out_f = StringIO()

        out_f.write("--- NIGHT OF %s --- filters: %s\n" % (
            ndate, filters))
        out_f.write("Queue prepared at: %s\n" % (
            time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())))
        out_f.write("%-16.16s  %-10.10s %12.12s  %5.5s  %5.5s %7.7s %-10.10s %-6.6s  %4.4s  %4.4s  %3.3s  %s\n" % (
            'Date', 'ObsBlk', 'Program', 'Grade', 'Rank', 'Time',
            'Target', 'Filter', 'See', 'Tran', 'AM', 'Comment'))

        scored_sum = 0.0
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

                out_f.write("%-16.16s  %-10.10s %12.12s  %5.5s  %5.2f %7.2f %-10.10s %-6.6s  %4.2f  %4.2f  %3.1f  %s\n" % (
                    date, ob.name, ob.program, ob.program.grade, ob.program.rank,
                    ob.total_time / 60, ob.target.name,
                    getattr(ob.inscfg, 'filter', 'none'),
                    ob.envcfg.seeing, ob.envcfg.transparency,
                    ob.envcfg.airmass, comment))

                # this is Terai-san's scored sum request
                if ob.program.grade.upper() in ('A', 'B'):
                    scored_sum += float(ob.program.rank) * (ob.total_time / 60)
            else:
                out_f.write("%-16.16s  %-10.10s\n" % (date, str(ob)))

        out_f.write("\n")
        time_avail = (schedule.stop_time - schedule.start_time).total_seconds() / 60.0
        waste = res.time_waste_sec / 60.0
        out_f.write("%d targets  %d filter exch  Time: avail=%.2f sched=%.2f unsched=%.2f min\n" % (
            len(targets), res.num_filter_exchanges, time_avail, (time_avail - waste), waste))
        out_f.write("rank * on_source time: %.2f\n" % (scored_sum))
        out_f.write("\n")

        self.schedules[schedule] = Bunch.Bunch(report=out_f.getvalue())
        out_f.close()

        return True

    def new_schedule_cb(self, sdlr, schedule):
        self.add_schedule(schedule)
        return True

    def clear_schedule_cb(self, sdlr):
        self.cur_schedule = None
        def _no_schedule():
            self.tw.set_text('')
            self.w.btn_make_ope.set_enabled(False)
            self.w.btn_exec_integgui2.set_enabled(False)
            self.w.btn_save_report.set_enabled(False)
        if self.gui_up:
            # NOTE: this needs to be a gui_call!
            self.view.gui_call(_no_schedule)
        return True

    def get_ob(self, obkey):
        for slot in self.cur_schedule.slots:
            ob = slot.ob
            if (ob is not None) and (ob.id == obkey):
                return ob
        print(("%s not found!" % obkey))
        raise KeyError(obkey)

    def _get_obs(self, use_selection=False):
        # NOTE: use_selection must be False
        assert use_selection is False
        ob_list = []
        for slot in self.cur_schedule.slots:
            ob = slot.ob
            if ob is not None:
                ob_list.append(ob)
        return ob_list

    def _get_targets(self, oblist):
        targets = set([])
        for ob in oblist:
            targets.add(ob.target)
        return targets


#END
