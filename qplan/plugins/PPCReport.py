#
# PPCReport.py -- PPCReport plugin
#
#  E. Jeschke
#
import time
from datetime import timedelta

from ginga.gw import Widgets
from ginga.misc import Bunch

from qplan import qsim
from qplan.plugins import PlBase

import pandas as pd


class PPCReport(PlBase.Plugin):

    def __init__(self, controller):
        super().__init__(controller)

        self.schedules = {}
        self.cur_schedule = None

        sdlr = self.model.get_scheduler()
        sdlr.add_callback('schedule-added', self.new_schedule_cb)
        sdlr.add_callback('schedule-cleared', self.clear_schedule_cb)

        self.model.add_callback('schedule-selected', self.show_schedule_cb)

        self.columns = [('Time', 'datetime'),
                        ('PPC name', 'name'),
                        ('Exp time', 'exp_time'),
                        ('Total time', 'total_time'),
                        ('Priority', 'priority'),
                        ('RA', 'ra'), ('DEC', 'dec'),
                        ('PA', 'pa'),
                        ('Comment', 'comment')]
        self.w = Bunch.Bunch()
        self.gui_up = False

    def build_gui(self, container):

        vbox = Widgets.VBox()
        vbox.set_border_width(4)
        vbox.set_spacing(2)
        self.vbox = vbox

        self.w.ppc_tbl = Widgets.TreeView(auto_expand=True,
                                          selection='multiple',
                                          sortable=True,
                                          use_alt_row_color=True)
        self.w.ppc_tbl.setup_table(self.columns, 1, 'datetime')
        self.w.ppc_tbl.set_optimal_column_widths()
        vbox.add_widget(self.w.ppc_tbl, stretch=1)

        hbox = Widgets.HBox()
        btn = Widgets.Button('Write SFA table')
        btn.add_callback('activated', self.make_sfa_cb)
        btn.set_tooltip("Write an SFA table for this schedule")
        btn.set_enabled(False)
        self.w.btn_make_sfa = btn
        hbox.add_widget(btn)

        hbox.add_widget(Widgets.Label(''), stretch=1)
        #vbox.add_widget(Widgets.Label(''), stretch=1)
        vbox.add_widget(hbox, stretch=0)

        container.add_widget(vbox, stretch=1)
        self.gui_up = True

    def start(self):
        pass

    def make_sfa_cb(self, w):
        info = self.schedules[self.cur_schedule]
        table = info.table

        header = [col[0] for col in self.columns]
        data = [[table[name][key] for hdr, key in self.columns]
                for name in table.keys()]
        data.sort(key=lambda row: row[0])
        df = pd.DataFrame(data)

        out_name = self.get_sfa_name()
        try:
            df.to_csv(out_name, sep=',', header=header, index=False)

        except Exception as e:
            errmsg = f"couldn't write SFA file: {e}"
            self.logger.error(errmsg, exc_info=True)
            self.fv.show_error(errmsg)

        return True

    def get_sfa_name(self):
        sfa_name = "SFA-" + time.strftime("%Y%m%d-%H%M%S",
                                            time.localtime()) + ".csv"
        return sfa_name

    def show_schedule_cb(self, qmodel, schedule):
        try:
            self.cur_schedule = schedule
            info = self.schedules[schedule]

            def _have_schedule():
                self.w.ppc_tbl.set_tree(info.table)
                if len(info.table) > 0:
                    self.w.btn_make_sfa.set_enabled(True)

            if self.gui_up:
                # NOTE: this needs to be a gui_call!
                self.view.gui_call(_have_schedule)
        except KeyError:
            pass

    def add_schedule(self, schedule):
        # ??? needed
        res = qsim.eval_schedule(schedule)

        start_time = schedule.start_time
        sdlr = self.model.get_scheduler()
        t = start_time.astimezone(sdlr.timezone)
        ndate = t.strftime("%Y-%m-%d")
        table = dict()

        #out_f.write(f"--- NIGHT OF {ndate} ---")
        #out_f.write("Queue prepared at: %s\n" % (
        #    time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())))
        for slot in schedule.slots:
            row = dict()
            t = slot.start_time.astimezone(sdlr.timezone)
            ob = slot.ob
            if ob != None:
                t_prog = slot.start_time + timedelta(0, ob.total_time)
                row['comment'] = ob.comment
                row['name'] = ob.name
                row['datetime'] = t.strftime("%Y-%m-%d %H:%M:%S")
                for name in ['ra', 'dec', 'priority', 'exp_time',
                             'total_time', 'pa']:
                    row[name] = ''

                #print(ob.name, ob.derived, type(ob.name))
                if not ob.derived:
                    # not an OB generated to serve another OB
                    row['priority'] = ob.priority
                    row['exp_time'] = ob.inscfg.exp_time
                    row['total_time'] = ob.total_time
                    row['ra'] = ob.target.ra
                    row['dec'] = ob.target.dec
                    row['pa'] = ob.inscfg.pa
                if ob.name is not None:
                    table[ob.name] = row

        self.schedules[schedule] = Bunch.Bunch(table=table)

        return True

    def new_schedule_cb(self, sdlr, schedule):
        self.add_schedule(schedule)
        return True

    def clear_schedule_cb(self, sdlr):
        self.cur_schedule = None
        def _no_schedule():
            self.w.ppc_tbl.clear()
            self.w.btn_make_sfa.set_enabled(False)

        if self.gui_up:
            # NOTE: this needs to be a gui_call!
            self.view.gui_call(_no_schedule)
        return True
