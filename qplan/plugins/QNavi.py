#
# QNavi.py -- build schedule plugin
#
# E. Jeschke
#

import os
from collections import OrderedDict
from datetime import timedelta, datetime

# 3rd party imports
import yaml

from ginga.misc.Bunch import Bunch
from ginga.gw import Widgets

# local imports
from qplan.plugins import PlBase
from qplan import entity

# Gen2 imports
have_gen2 = False
try:
    from g2cam.status.client import StatusClient
    from g2cam.status.common import STATNONE, STATERROR
    have_gen2 = True

except ImportError:
    pass


class QNavi(PlBase.Plugin):

    def __init__(self, controller):
        super().__init__(controller)

        self.slot = None
        self.stobj = None
        self.w = Bunch()

        # TODO: get from Gen2
        self.filters = ['auto', 'g', 'r2', 'i2', 'z', 'Y']
        self.seeings = ['auto', '0.8', '1.0', '1.3', '1.6', '100']
        self.transparencies = ['auto', '0.7', '0.4', '0.1', '0.0']
        # define a 1 hour slot length
        # TODO: how to figure out just what this should be?
        self.slot_length = 60.0 * 60.0

        # these are updated by fetch_gen2_status()
        self.cur_filter = 'g'
        self.cur_az = -90.0
        self.cur_el = 89.0
        self.cur_seeing = 1.0
        self.cur_transparency = 0.7
        self.cur_plan = '(NONE)'

        prefs = self.controller.get_preferences()
        self.settings = prefs.create_category('plugin_QNavi')
        self.settings.add_defaults(gen2_status_host='localhost',
                                   gen2_status_user=None,
                                   gen2_status_pass=None,
                                   plan_folder='.')
        self.settings.load(onError='silent')

        self.model.add_callback('qc-plan-loaded', self._plan_loaded_cb)

    def build_gui(self, container):
        vbox = Widgets.VBox()
        vbox.set_border_width(4)
        vbox.set_spacing(2)

        hbox = Widgets.HBox()
        gr = Widgets.GridBox()
        gr.set_column_spacing(15)

        i = 0
        self.w.cur_filter = Widgets.Label(self.cur_filter)
        gr.add_widget(Widgets.Label('Cur Filter'), 0, i)
        gr.add_widget(self.w.cur_filter, 1, i)

        i += 1
        self.w.filter = Widgets.ComboBox()
        gr.add_widget(Widgets.Label('Filter'), 0, i)
        gr.add_widget(self.w.filter, 1, i)
        for name in self.filters:
            self.w.filter.append_text(name)
        self.w.filter.set_tooltip("Your choice of filter for HSC")

        i += 1
        self.w.cur_seeing = Widgets.Label(str(self.cur_seeing))
        gr.add_widget(Widgets.Label('Est Seeing'), 0, i)
        gr.add_widget(self.w.cur_seeing, 1, i)

        i += 1
        self.w.seeing = Widgets.ComboBox()
        gr.add_widget(Widgets.Label('Seeing'), 0, i)
        gr.add_widget(self.w.seeing, 1, i)
        for name in self.seeings:
            self.w.seeing.append_text(name)
        self.w.seeing.set_tooltip("Your choice of seeing")

        i += 1
        self.w.cur_transp = Widgets.Label(str(self.cur_transparency))
        gr.add_widget(Widgets.Label('Est Transparency'), 0, i)
        gr.add_widget(self.w.cur_transp, 1, i)

        i += 1
        self.w.trans = Widgets.ComboBox()
        gr.add_widget(Widgets.Label('Transparency'), 0, i)
        gr.add_widget(self.w.trans, 1, i)
        for name in self.transparencies:
            self.w.trans.append_text(name)
        self.w.trans.set_tooltip("Your choice of sky transparency")

        i += 1
        self.w.cur_plan = Widgets.Label(self.cur_plan)
        gr.add_widget(Widgets.Label('Cur Plan'), 0, i)
        gr.add_widget(self.w.cur_plan, 1, i)

        i += 1
        self.w.choose_plan = Widgets.Button('Load Plan')
        gr.add_widget(Widgets.Label(''), 0, i)
        gr.add_widget(self.w.choose_plan, 1, i)
        self.w.choose_plan.set_tooltip("Load a queue coordinator's plan")
        self.w.choose_plan.add_callback('activated', self.load_plan_cb)

        hbox.add_widget(gr, stretch=0)
        hbox.add_widget(Widgets.Label(''), stretch=1)
        vbox.add_widget(hbox)

        hbox = Widgets.HBox()

        fr = Widgets.Frame("Possible OBs")

        self.tree1 = Widgets.TreeView(sortable=True,
                                      use_alt_row_color=True,
                                      selection='single')
        self.tree1.add_callback('selected', self.select_ob_cb)
        fr.set_widget(self.tree1)
        hbox.add_widget(self.tree1, stretch=1)

        vbx2 = Widgets.VBox()
        vbx2.set_border_width(4)
        vbx2.set_spacing(6)

        btn = Widgets.Button("Get OBs")
        btn.set_tooltip("Find OBs that can execute NOW")
        btn.add_callback('activated', self.find_executable_obs_cb)
        vbx2.add_widget(btn, stretch=0)

        # add stretch spacer
        vbx2.add_widget(Widgets.Label(''), stretch=1)

        hbox.add_widget(vbx2, stretch=0)

        vbox.add_widget(hbox, stretch=1)
        container.add_widget(vbox, stretch=1)

    def start(self):
        gen2_pass = self.settings.get('gen2_status_pass')
        if gen2_pass is not None:
            self.create_status_client()

    def find_executable_obs_cb(self, widget):

        self.tree1.clear()
        self.view.update_pending()

        if have_gen2 and self.stobj is not None:
            gen2_pass = self.settings.get('gen2_status_pass')
            if gen2_pass is not None:
                self.fetch_gen2_status()

        # get a handle to the control panel plugin
        cp = self.view.get_plugin('cp')
        use_db = cp.w.use_qdb.get_state()
        cp.update_scheduler(use_db=use_db)

        sdlr = self.model.get_scheduler()
        now = datetime.now(tz=sdlr.timezone)
        date_s = now.strftime("%Y-%m-%d")
        # for testing...
        date_s = '2022-04-28'
        time_b = now.strftime("%H-%M-%S")
        try:
            time_start = sdlr.site.get_date("%s %s" % (date_s, time_b))
        except Exception as e:
            errmsg = 'Error parsing start date/time:: {}\n'.format(str(e))
            errmsg += "\n".join([e.__class__.__name__, str(e)])
            self.logger.error(errmsg)
            self.controller.gui_do(self.controller.show_error, errmsg, raisetab=True)
            return

        # get the string for the date of observation in HST, which is what
        # is used in the Schedule table
        if time_start.hour < 9:
            date_obs_local = (time_start - timedelta(hours=10)).strftime("%Y-%m-%d")
        else:
            date_obs_local = time_start.strftime("%Y-%m-%d")
        self.logger.info("observation date (local) is '{}'".format(date_obs_local))

        # find the record in the schedule table that matches our date;
        # we need to get the list of filters and so on from it
        rec = None
        for _rec in sdlr.schedule_recs:
            if _rec.date == date_obs_local:
                rec = _rec
                break
        if rec is None:
            errmsg = "Can't find a record in the Schedule table matching '{}'".format(date_obs_local)
            self.logger.error(errmsg)
            self.controller.gui_do(self.controller.show_error, errmsg, raisetab=True)
            return

        data = Bunch(rec.data)

        # override some items from Schedule table
        _filter = self.w.filter.get_text().strip()
        if _filter == 'auto':
            _filter = self.cur_filter
        data.cur_filter = _filter

        seeing = self.w.seeing.get_text().strip()
        if seeing == 'auto':
            data.seeing = self.cur_seeing
        else:
            data.seeing = float(seeing)

        transp = self.w.trans.get_text().strip()
        if transp == 'auto':
            data.transparency = self.cur_transparency
        else:
            data.transparency = float(transp)

        data.cur_az = self.cur_az
        data.cur_el = self.cur_el

        slot = entity.Slot(time_start, self.slot_length, data=data)
        self.slot = slot
        good, bad = sdlr.find_executable_obs(slot)

        tree_dict = OrderedDict()

        # Table header with units
        columns = [('Best', 'index'),
                   ('Program', 'program'),
                   ('OB Code', 'ob_code'),
                   ('Priority', 'priority'),
                   ('Grade', 'grade'),
                   ('Prep', 'prep'),
                   ('On Source', 'time'),
                   ('Target', 'target'),
                   ('Filter', 'filter'),
                   ('Delay', 'delay'),
                   ('Reason', 'reason')]

        self.tree1.setup_table(columns, 1, 'index')

        # This is to get around table widget not sorting numbers properly
        i_fmt = '{{0:0{0}d}}'.format(len(str(len(good))))

        # Table contents
        i = 1
        for rec in good:
            i_str = i_fmt.format(i)
            bnch = Bunch(index=i_str,
                         program=rec.ob.program.proposal,
                         ob_code=rec.ob.name,
                         priority=rec.ob.priority,
                         grade=rec.ob.program.grade,
                         prep="%.2f" % (rec.prep_sec / 60.0),
                         time="%.2f" % (rec.ob.total_time / 60.0),
                         target=rec.ob.target.name,
                         filter=rec.ob.inscfg.filter,
                         delay=rec.delay_sec / 60.0,
                         _group=good,
                         _rec=rec,
                         reason='OK')
            tree_dict[i_str] = bnch
            i += 1

        self.tree1.set_tree(tree_dict)

        self.tree1.set_optimal_column_widths()

    def select_ob_cb(self, widget, s_dct):
        sdlr = self.model.get_scheduler()
        dcts = list(s_dct.values())
        if len(dcts) == 0:
            # selection cleared
            sdlr.clear_schedules()
            return

        info = dcts[0]['_rec']
        #print(info)

        schedule = sdlr.slot_to_schedule(self.slot, info)

        # set a name into the schedule to be retrieved in Report plugin
        name = "{}.{}".format(info.ob.program.proposal, info.ob.name)
        schedule.data.ope_name = name

        self.model.select_schedule(schedule)

    def fetch_gen2_status(self):
        # Fetch current filter, Az, El from Gen2 status service and
        # update first row in schedule sheet. Also, update start time.
        try:
            result = {'FITS.HSC.FILTER': 0, 'TSCS.AZ': 0, 'TSCS.EL': 0,
                      'FITS.HSC.SEEING': 0, 'FITS.HSC.TRANSPARENCY': 0}
            self.stobj.fetch(result)
            #print(result)
        except Exception as e:
            self.logger.error('Unexpected error in update_current_conditions_cb: %s' % str(e))
            return

        self.logger.info('From Gen2 current HSC filter %s Az %f El %f' % (result['FITS.HSC.FILTER'], result['TSCS.AZ'], result['TSCS.EL']))

        cur_filter = result['FITS.HSC.FILTER']
        if cur_filter not in (STATNONE, STATERROR, '0'):
            # Filter name special cases
            if 'HSC-' in cur_filter:
                cur_filter = cur_filter.replace('HSC-', '')
            if cur_filter == 'Y':
                cur_filter = 'y'
            if 'NB0' in cur_filter:
                cur_filter = cur_filter.replace('NB0', 'NB')
            if 'IB0' in cur_filter:
                cur_filter = cur_filter.replace('IB0', 'IB')
            # Set all 'NB' and 'IB' filters to lower-case
            if ('NB' in cur_filter) or ('IB' in cur_filter):
                cur_filter = cur_filter.lower()
            self.logger.info('Current filter %s' % (cur_filter))
            self.cur_filter = cur_filter
        self.w.cur_filter.set_text(cur_filter)

        # TODO: these will change to whatever the rolling average is
        self.w.cur_seeing.set_text(str(result['FITS.HSC.SEEING']))
        self.w.cur_transp.set_text(str(result['FITS.HSC.TRANSPARENCY']))

        if result['TSCS.AZ'] not in (STATNONE, STATERROR):
            cur_az = '%8.2f' % result['TSCS.AZ']
            cur_az = cur_az.strip()
            self.cur_az = cur_az

        if result['TSCS.EL'] not in (STATNONE, STATERROR):
            cur_el = '%8.2f' % result['TSCS.EL']
            cur_el = cur_el.strip()
            self.cur_el = cur_el

        # Compensate for Subaru's funky az reading
        az, el = (float(cur_az) - 180.0) % 360.0, float(cur_el)
        slew_plt = self.view.get_plugin('SlewChart')
        slew_plt.set_telescope_position(az, el)

    def create_status_client(self):
        gen2_host = self.settings.get('gen2_status_host')
        gen2_user = self.settings.get('gen2_status_user')
        gen2_pass = self.settings.get('gen2_status_pass')

        self.stobj = StatusClient(gen2_host,
                                  username=gen2_user, password=gen2_pass)
        self.stobj.reconnect()

    def load_plan_cb(self, w):
        cp = self.view.get_plugin('programstab')
        cp.load_plan_cb(w)

    def _plan_loaded_cb(self, model, plan_name):
        self.cur_plan = plan_name
        self.w.cur_plan.set_text(plan_name)
        self.tree1.clear()
