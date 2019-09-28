#
# Builder.py -- build schedule plugin
#
# Eric Jeschke (eric@naoj.org)
#

import os
from collections import OrderedDict
from datetime import timedelta, datetime

# ginga imports
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


class Builder(PlBase.Plugin):

    def __init__(self, controller):
        super(Builder, self).__init__(controller)

        self.show_bad = False
        self.slot = None
        self.stobj = None
        self.w = Bunch()

        prefs = self.controller.get_preferences()
        self.settings = prefs.create_category('plugin_Builder')
        self.settings.add_defaults(gen2_status_host='localhost',
                                   gen2_status_user=None,
                                   gen2_status_pass=None)
        self.settings.load(onError='silent')

    def build_gui(self, container):
        vbox = Widgets.VBox()
        vbox.set_border_width(4)
        vbox.set_spacing(2)

        gr = Widgets.GridBox()
        gr.set_column_spacing(4)

        i = 0
        ## self.w.observer = Widgets.TextEntry()
        ## self.w.observer.set_length(12)
        ## gr.add_widget(Widgets.Label('Observer'), 0, i)
        ## gr.add_widget(self.w.observer, 1, i)
        ## self.w.observer.set_tooltip("Name of observer doing this observation")
        ## self.w.observer.set_text("Nobody")

        ## i += 1
        self.w.date = Widgets.TextEntry()
        self.w.date.set_length(12)
        gr.add_widget(Widgets.Label('Local date'), 0, i)
        gr.add_widget(self.w.date, 1, i)
        self.w.date.set_tooltip("Local date at beginning of interval")

        i += 1
        self.w.start_time = Widgets.TextEntry()
        self.w.start_time.set_length(8)
        gr.add_widget(Widgets.Label('Start Time'), 0, i)
        gr.add_widget(self.w.start_time, 1, i)
        self.w.start_time.set_tooltip("Local time for interval")

        i += 1
        self.w.len_time = Widgets.TextEntry()
        self.w.len_time.set_length(8)
        gr.add_widget(Widgets.Label('Length (min)'), 0, i)
        gr.add_widget(self.w.len_time, 1, i)
        self.w.len_time.set_text('70')
        self.w.len_time.set_tooltip("Length of interval in MINUTES")

        i += 1
        self.w.az = Widgets.TextEntry()
        self.w.az.set_length(8)
        gr.add_widget(Widgets.Label('Az'), 0, i)
        gr.add_widget(self.w.az, 1, i)
        self.w.az.set_text('-90.0')
        self.w.az.set_tooltip("Current azimuth of telescope")

        i += 1
        self.w.el = Widgets.TextEntry()
        self.w.el.set_length(8)
        gr.add_widget(Widgets.Label('El'), 0, i)
        gr.add_widget(self.w.el, 1, i)
        self.w.el.set_text('89.9')
        self.w.el.set_tooltip("Current elevation of telescope")

        i += 1
        self.w.filter = Widgets.TextEntry()
        self.w.filter.set_length(5)
        gr.add_widget(Widgets.Label('Filter'), 0, i)
        gr.add_widget(self.w.filter, 1, i)
        self.w.filter.set_text('g')
        self.w.filter.set_tooltip("Currently installed filter for HSC")

        i += 1
        self.w.seeing = Widgets.TextEntry()
        self.w.seeing.set_length(5)
        gr.add_widget(Widgets.Label('Seeing'), 0, i)
        gr.add_widget(self.w.seeing, 1, i)
        self.w.seeing.set_text('1.0')
        self.w.seeing.set_tooltip("Current best estimate of seeing")

        i += 1
        self.w.trans = Widgets.TextEntry()
        self.w.trans.set_length(5)
        gr.add_widget(Widgets.Label('Transparency'), 0, i)
        gr.add_widget(self.w.trans, 1, i)
        self.w.trans.set_text('0.85')
        self.w.trans.set_tooltip("Current best estimate of sky transparency")

        i += 1
        btn = Widgets.Button('Update')
        btn.add_callback('activated', self.update_cb)
        btn.set_tooltip("Update time, current pointing and active filter")
        gr.add_widget(btn, 1, i)

        i += 1
        gr.add_widget(Widgets.Label(''), 1, i, stretch=4)

        vbox.add_widget(gr)

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

        ## cb = Widgets.CheckBox("Show bad")
        ## cb.set_tooltip("Include OBs that cannot execute now")
        ## cb.add_callback('activated', self._toggle_show_bad)
        ## vbx2.add_widget(cb, stretch=0)

        btn = Widgets.Button("Get OBs")
        btn.set_tooltip("Find OBs that can execute within the period")
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

        # get a handle to the control panel plugin
        cp = self.view.get_plugin('cp')
        use_db = cp.w.use_qdb.get_state()
        cp.update_scheduler(use_db=use_db)

        date_s = self.w.date.get_text().strip()

        sdlr = self.model.get_scheduler()
        # TODO: this won't work! Once it is past midnight local date
        # won't match correct record
        rec = None
        for _rec in sdlr.schedule_recs:
            if _rec.date == date_s:
                rec = _rec
                break
        if rec is None:
            # probably should be an error message here instead!
            rec = sdlr.schedule_recs[0]

        time_b = self.w.start_time.get_text().strip()
        len_s = self.w.len_time.get_text().strip()
        try:
            time_start = sdlr.site.get_date("%s %s" % (date_s, time_b))
        except Exception as e:
            errmsg = 'Error parsing start date/time:: {}\n'.format(str(e))
            errmsg += "\n".join([e.__class__.__name__, str(e)])
            self.logger.error(errmsg)
            self.controller.gui_do(self.controller.show_error, errmsg, raisetab=True)
            return

        slot_length = max(0.0, float(len_s) * 60.0)

        data = Bunch(rec.data)
        # override some items from Schedule table
        data.cur_filter = self.w.filter.get_text().strip()
        data.cur_az = float(self.w.az.get_text().strip())
        data.cur_el = float(self.w.el.get_text().strip())
        data.seeing = float(self.w.seeing.get_text().strip())
        data.transparency = float(self.w.trans.get_text().strip())

        slot = entity.Slot(time_start, slot_length, data=data)
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

        if self.show_bad:
            for rec in bad:
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
                             _group=bad,
                             _rec=rec,
                             reason='NG: ' + rec.reason)
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

    def _toggle_show_bad(self, w, tf):
        self.show_bad = tf

    def update_cb(self, w):

        sdlr = self.model.get_scheduler()

        now = datetime.now(tz=sdlr.timezone)
        self.w.date.set_text(now.strftime('%Y-%m-%d'))
        self.w.start_time.set_text(now.strftime('%H:%M:%S'))

        if have_gen2 and self.stobj is not None:
            gen2_pass = self.settings.get('gen2_status_pass')
            if gen2_pass is not None:
                self.fetch_gen2_status()

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
            self.w.filter.set_text(cur_filter)

        if result['TSCS.AZ'] not in (STATNONE, STATERROR):
            cur_az = '%8.2f' % result['TSCS.AZ']
            cur_az = cur_az.strip()
            self.w.az.set_text(cur_az)

        if result['TSCS.EL'] not in (STATNONE, STATERROR):
            cur_el = '%8.2f' % result['TSCS.EL']
            cur_el = cur_el.strip()
            self.w.el.set_text(cur_el)

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

#END
