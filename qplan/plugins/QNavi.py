#
# QNavi.py -- night OB scheduler plugin
#
# T. Terai
# E. Jeschke
#

import os
from collections import OrderedDict
from datetime import timedelta, datetime

# 3rd party imports
import yaml

from ginga.misc.Bunch import Bunch
from ginga.gw import Widgets

# Gen2 imports
have_gen2 = False
try:
    from g2cam.status.common import STATNONE, STATERROR
    have_gen2 = True

except ImportError:
    pass

# local imports
from qplan.plugins import PlBase
from qplan import entity


class QNavi(PlBase.Plugin):

    def __init__(self, controller):
        super().__init__(controller)

        self.slot = None
        # status fetch object shared with Builder
        self.stobj = None
        self.w = Bunch()

        # TODO: static list of all filters, or get from Schedule, or
        # get installed list from Gen2
        self.filters = ['auto', 'g', 'r2', 'i2', 'z', 'y', 'NB400', 'NB430']
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
        self._no_plan = '(NONE)'
        self.cur_plan = self._no_plan

        prefs = self.controller.get_preferences()
        self.settings = prefs.create_category('plugin_QNavi')
        self.settings.add_defaults(test_date=None, test_time=None,
                                   plan_folder='.')
        self.settings.load(onError='silent')

        self.model.add_callback('qc-plan-loaded', self._plan_loaded_cb)

        self.timer_interval = 30.0
        self.timer = self.view.make_timer()
        self.timer.add_callback('expired', self._timer_cb)

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
        gr.add_widget(Widgets.Label('Calc Seeing'), 0, i)
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
        gr.add_widget(Widgets.Label('Calc Transp'), 0, i)
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
        builder = self.view.get_plugin('builder')
        gen2_pass = builder.settings.get('gen2_status_pass')
        if gen2_pass is not None:
            self.create_status_client()
            self.timer.set(5.0)

    def find_executable_obs_cb(self, widget):

        self.tree1.clear()
        self.view.update_pending()

        if self.cur_plan == self._no_plan:
            self.view.show_error("Please select a queue coordinator plan.")
            return

        if have_gen2 and self.stobj is not None:
            self.fetch_gen2_status()

        # check seeing is valid
        seeing = self.w.seeing.get_text().strip()
        if seeing == 'auto':
            seeing = self.w.cur_seeing.get_text().strip()
            try:
                seeing = float(seeing)
            except ValueError:
                self.view.show_error(f"{seeing} is not a valid seeing value; please select a seeing", raisetab=True)
                return
        else:
            seeing = float(seeing)

        # check transparency is valid
        transp = self.w.trans.get_text().strip()
        if transp == 'auto':
            transp = self.w.cur_transp.get_text().strip()
            try:
                transp = float(transp)
            except ValueError:
                self.view.show_error(f"{transp} is not a valid transparency value; please select a transparency", raisetab=True)
                return
        else:
            transp = float(transp)

        # get a handle to the control panel plugin
        cp = self.view.get_plugin('cp')
        sdlr = self.model.get_scheduler()

        date_s = self.settings.get('test_date', None)
        time_b = self.settings.get('test_time', None)
        now = datetime.now(tz=sdlr.timezone)
        if date_s is None:
            date_s = now.strftime("%Y-%m-%d")
        if time_b is None:
            time_b = now.strftime("%H-%M-%S")
        try:
            time_start = sdlr.site.get_date("%s %s" % (date_s, time_b))
        except Exception as e:
            errmsg = 'Error parsing start date/time:: {}\n'.format(str(e))
            errmsg += "\n".join([e.__class__.__name__, str(e)])
            self.logger.error(errmsg)
            self.view.gui_do(self.view.show_error, errmsg, raisetab=True)
            return

        # find the record in the schedule table that matches our date
        try:
            builder = self.view.get_plugin('builder')
            # NOTE: needed to make sure get_schedule_data works
            sdlr.set_schedule_info(cp.schedule_qf.schedule_info)
            data = builder.get_schedule_data(time_start)
        except Exception as e:
            errmsg = str(e)
            self.logger.error(errmsg)
            self.view.gui_do(self.view.show_error, errmsg, raisetab=True)
            return

        # check filter is valid
        _filter = self.w.filter.get_text().strip()
        if _filter == 'auto':
            # use currently installed filter if set to "auto"
            _filter = self.w.cur_filter.get_text().strip()

        if _filter not in data.filters:
            self.view.show_error(f"'{_filter}' not in installed filters; please select a different filter", raisetab=True)
            return

        use_db = cp.w.use_qdb.get_state()

        cp.update_scheduler(use_db=use_db,
                            limit_filter=_filter,
                            allow_delay=False)

        # override some items from Schedule table
        data.cur_filter = _filter
        data.seeing = seeing
        data.transparency = transp

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
        self.logger.info("status fetch result: {}".format(result))

        self.logger.info('From Gen2 current HSC filter %s Az %f El %f' % (result['FITS.HSC.FILTER'], result['TSCS.AZ'], result['TSCS.EL']))

        if self.view.is_gui_thread():
            self._update_current_values(result)
        else:
            self.view.gui_do(self._update_current_values, result)

    def _update_current_values(self, result):
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

        cur_az, cur_el = self.cur_az, self.cur_el

        if result['TSCS.AZ'] not in (STATNONE, STATERROR):
            self.cur_az = float(result['TSCS.AZ'])

        if result['TSCS.EL'] not in (STATNONE, STATERROR):
            self.cur_el = float(result['TSCS.EL'])

        # Compensate for Subaru's funky az reading
        az, el = (cur_az - 180.0) % 360.0, cur_el
        slew_plt = self.view.get_plugin('SlewChart')
        slew_plt.set_telescope_position(az, el)

    def create_status_client(self):
        # share status client with builder plugin
        builder = self.view.get_plugin('builder')
        builder.create_status_client()
        self.stobj = builder.stobj

    def load_plan_cb(self, w):
        try:
            cp = self.view.get_plugin('programstab')
        except KeyError:
            self.view.show_error("Has info been loaded from Control Panel?",
                                 raisetab=True)
            return
        cp.load_plan_cb(w)

    def _plan_loaded_cb(self, model, plan_name):
        self.cur_plan = plan_name
        self.w.cur_plan.set_text(plan_name)
        self.tree1.clear()

    def _timer_cb(self, timer):
        try:
            self.fetch_gen2_status()
        except Exception as e:
            # error message logged in fetch_gen2_status()
            pass

        timer.set(self.timer_interval)
