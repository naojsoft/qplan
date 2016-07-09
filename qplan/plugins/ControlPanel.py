#
# ControlPanel.py -- Controller plugin for operating scheduler
#
# Eric Jeschke (eric@naoj.org)
#

# stdlib imports
import os.path
import datetime

# ginga imports
from ginga.misc import Bunch
from ginga.gw import Widgets

# Gen2 imports
have_gen2 = False
try:
    import remoteObjects as ro
    from SOSS.status.common import STATNONE,STATERROR
    have_gen2 = True

except ImportError:
    pass

# local imports
import PlBase
from qplan import filetypes
import misc

have_qdb = False
try:
    from qplan import q_db, q_query
    from Gen2.db.db_config import qdb_addr
    import transaction
    have_qdb = True

except ImportError:
    pass


class ControlPanel(PlBase.Plugin):

    def __init__(self, model, view, controller, logger):
        super(ControlPanel, self).__init__(model, view, controller, logger)

        self.input_dir = "inputs"

        self.weights_qf = None
        self.schedule_qf = None
        self.programs_qf = None
        self.ob_qf_dict = None
        self.tgtcfg_qf_dict = None
        self.envcfg_qf_dict = None
        self.inscfg_qf_dict = None
        self.telcfg_qf_dict = None

        self.qdb = None
        self.qa = None
        self.qq = None

    def connect_qdb(self):
        # Set up Queue database access
        self.qdb = q_db.QueueDatabase(self.logger, qdb_addr)
        self.qa = q_db.QueueAdapter(self.qdb)
        self.qq = q_query.QueueQuery(self.qa)

    def build_gui(self, container):
        vbox = Widgets.VBox()
        vbox.set_border_width(4)
        vbox.set_spacing(2)
        vbox.cfg_expand(8, 8)

        sw = Widgets.ScrollArea()
        sw.set_widget(vbox)

        fr = Widgets.Frame("Files")

        captions = (('Inputs:', 'label', 'Input dir', 'entry'),
                    ('Load Info', 'button'),
                    ('Update Current Conditions', 'button'),
                    ('Update Database from Files', 'button'),
                    ('Build Schedule', 'button', 'Use QDB', 'checkbutton'))
        w, b = Widgets.build_info(captions, orientation='vertical')
        self.w = b

        b.input_dir.set_length(128)
        b.input_dir.set_text(self.controller.input_dir)
        b.load_info.set_tooltip("Load data from phase 2 files")
        b.load_info.add_callback('activated', self.initialize_model_cb)
        b.update_current_conditions.set_tooltip("Update time, current pointing, env conditions and active filter")
        b.update_database_from_files.set_tooltip("Update Gen2 database from changes to phase 2 files")

        if have_gen2:
            b.update_current_conditions.add_callback('activated',
                                                 self.update_current_conditions_cb)
            b.update_database_from_files.add_callback('activated',
                                                      self.update_db_cb)
        else:
            b.update_current_conditions.set_enabled(False)
            b.update_database_from_files.set_enabled(False)

        b.build_schedule.set_tooltip("Schedule all periods defined in schedule tab")
        b.build_schedule.add_callback('activated', self.build_schedule_cb)

        b.use_qdb.set_tooltip("Use Gen2 queue database when scheduling")
        if not have_qdb:
            b.use_qdb.set_enabled(False)

        fr.set_widget(w)
        vbox.add_widget(fr, stretch=0)

        spacer = Widgets.Label('')
        vbox.add_widget(spacer, stretch=1)

        hbox = Widgets.HBox()

        adj = Widgets.Slider(orientation='horizontal', track=True)
        adj.set_limits(0, 100, incr_value=1)
        idx = self.controller.idx_tgt_plots
        adj.set_value(idx)
        #adj.resize(200, -1)
        adj.set_tooltip("Choose subset of targets plotted")
        #self.w.plotgrp = adj
        adj.add_callback('value-changed', self.set_plot_pct_cb)
        hbox.add_widget(adj, stretch=1)

        sb = Widgets.SpinBox()
        sb.set_limits(1, 100)
        num = self.controller.num_tgt_plots
        sb.set_value(num)
        sb.set_tooltip("Adjust size of subset of targets plotted")
        sb.add_callback('value-changed', self.set_plot_limit_cb)
        hbox.add_widget(sb, stretch=0)

        vbox.add_widget(hbox, stretch=0)

        ## btns = Widgets.HBox()
        ## btns.set_spacing(3)

        ## btn = Widgets.Button("Close")
        ## #btn.add_callback('activated', lambda w: self.close())
        ## btns.add_widget(btn, stretch=0)
        ## btns.add_widget(Widgets.Label(''), stretch=1)
        ## vbox.add_widget(btns, stretch=0)

        self.sw = sw
        container.add_widget(sw, stretch=1)

    def initialize_model_cb(self, widget):
        self.input_dir = self.w.input_dir.get_text().strip()
        self.input_fmt = self.controller.input_fmt

        try:
            # read weights
            self.weights_qf = filetypes.WeightsFile(self.input_dir, self.logger, file_ext=self.input_fmt)
            # Load "Weights" Tab
            if 'weightstab' not in self.view.plugins:
                self.view.load_plugin('weightstab', 'WeightsTab', 'WeightsTab', 'report', 'Weights')
            self.model.set_weights_qf(self.weights_qf)

            # read schedule
            self.schedule_qf = filetypes.ScheduleFile(self.input_dir, self.logger, file_ext=self.input_fmt)
            # Load "Schedule" Tab
            if 'scheduletab' not in self.view.plugins:
                self.view.load_plugin('scheduletab', 'ScheduleTab', 'ScheduleTab', 'report', 'Schedule')
            self.model.set_schedule_qf(self.schedule_qf)

            # read proposals
            self.programs_qf = filetypes.ProgramsFile(self.input_dir, self.logger, file_ext=self.input_fmt)
            if 'programstab' not in self.view.plugins:
                self.view.load_plugin('programstab', 'ProgramsTab', 'ProgramsTab', 'report', 'Programs')
            self.model.set_programs_qf(self.programs_qf)

            # read observing blocks
            self.ob_qf_dict = {}
            self.tgtcfg_qf_dict = {}
            self.envcfg_qf_dict = {}
            self.inscfg_qf_dict = {}
            self.telcfg_qf_dict = {}
            self.oblist_info = []

            propnames = list(self.programs_qf.programs_info.keys())
            propnames.sort()

            for propname in propnames:
                pf = filetypes.ProgramFile(self.input_dir, self.logger, propname, self.programs_qf.programs_info, file_ext=self.input_fmt)

                # Set telcfg
                telcfg_qf = pf.cfg['telcfg']
                self.telcfg_qf_dict[propname] = telcfg_qf
                self.model.set_telcfg_qf_dict(self.telcfg_qf_dict)

                # Set inscfg
                inscfg_qf = pf.cfg['inscfg']
                self.inscfg_qf_dict[propname] = inscfg_qf
                self.model.set_inscfg_qf_dict(self.inscfg_qf_dict)

                # Set envcfg
                envcfg_qf = pf.cfg['envcfg']
                self.envcfg_qf_dict[propname] = envcfg_qf
                self.model.set_envcfg_qf_dict(self.envcfg_qf_dict)

                # Set targets
                tgtcfg_qf = pf.cfg['targets']
                self.tgtcfg_qf_dict[propname] = tgtcfg_qf
                self.model.set_tgtcfg_qf_dict(self.tgtcfg_qf_dict)

                # Finally, set OBs
                self.ob_qf_dict[propname] = pf.cfg['ob']
                #self.oblist_info.extend(self.oblist[propname].obs_info)
                self.model.set_ob_qf_dict(self.ob_qf_dict)

        except Exception as e:
            self.logger.error("Error initializing: %s" % (str(e)))


    def update_scheduler(self, use_db=False, ignore_pgm_skip_flag=False):
        sdlr = self.model.get_scheduler()
        try:
            sdlr.set_weights(self.weights_qf.weights)
            sdlr.set_schedule_info(self.schedule_qf.schedule_info)
            pgms = self.programs_qf.programs_info
            sdlr.set_programs_info(pgms, ignore_pgm_skip_flag)
            self.logger.info('list of programs to be scheduled %s' % sdlr.programs.keys())

            # TODO: this maybe should be done in the Model
            ob_keys = set([])
            propnames = list(self.programs_qf.programs_info.keys())
            okprops = []
            ob_dict = {}
            # Note: if the ignore_pgm_skip_flag is set to True, then
            # we don't pay attention to the "skip" flag in the
            # Programs sheet and thus consider all OB's in all
            # Programs. Otherwise, we do pay attention to the "skip"
            # flag and ignore all OB's in "skipped" programs.
            for propname in propnames:
                if not ignore_pgm_skip_flag and pgms[propname].skip:
                    self.logger.info('skip flag for program %s is set - skipping all OB in this program' % propname)
                    continue
                okprops.append(propname)

                # get all OB keys for this program
                for ob in self.ob_qf_dict[propname].obs_info:
                    key = (propname, ob.name)
                    ob_keys.add(key)
                    ob_dict[key] = ob

            self.logger.info("%s OBs after excluding skipped programs." % (
                len(ob_keys)))

            # TODO: remove keys for OBs that are already executed
            if use_db:
                self.connect_qdb()

                do_not_execute = set(self.qq.get_do_not_execute_ob_keys())
                ob_keys -= do_not_execute
                self.logger.info("%s OBs after removing executed OBs." % (
                    len(ob_keys)))

            elif self.model.completed_keys is not None:
                do_not_execute = set(self.model.completed_keys)
                ob_keys -= do_not_execute
                self.logger.info("%s OBs after removing executed OBs." % (
                    len(ob_keys)))

            # for a deterministic result
            ob_keys = list(ob_keys)
            ob_keys.sort()

            # Now turn the keys back into actual OB list
            oblist_info = []
            for key in ob_keys:
                oblist_info.append(ob_dict[key])

            self.oblist_info = oblist_info

            # TODO: only needed if we ADD or REMOVE programs
            sdlr.set_oblist_info(self.oblist_info)

        except Exception as e:
            self.logger.error("Error storing into scheduler: %s" % (str(e)))

        self.logger.info("scheduler initialized")

    def update_current_conditions_cb(self, widget):
        # Fetch current filter, Az, El from Gen2 status service and
        # update first row in schedule sheet. Also, update start time.
        self.logger.debug('update_current_conditions_cb')
        try:
            ro.init()
            stobj = ro.remoteObjectProxy('status')
            result = stobj.fetch({'FITS.HSC.FILTER': 0, 'TSCS.AZ': 0, 'TSCS.EL': 0})
        except ro.remoteObjectError as e:
            self.logger.error('Unexpected error in update_current_conditions_cb: %s' % str(e))
            return

        self.logger.info('From Gen2 current HSC filter %s Az %f El %f' % (result['FITS.HSC.FILTER'], result['TSCS.AZ'], result['TSCS.EL']))
        if self.schedule_qf is None:
            self.logger.error('Unexpected error in update_current_conditions_cb: schedule_qf is None')
            return

        self.logger.debug('Before update, schedule_qf.rows:%s' % self.schedule_qf.rows)
        rownum = 0 # Update only the first row

        cur_filter = result['FITS.HSC.FILTER']
        if cur_filter not in (STATNONE, STATERROR, '0'):
            # Filter name special cases
            if 'HSC-' in cur_filter:
                cur_filter = cur_filter.replace('HSC-', '')
            if cur_filter == 'i2':
                cur_filter = 'i'
            if cur_filter == 'Y':
                cur_filter = 'y'
            if 'NB0' in cur_filter:
                cur_filter = cur_filter.replace('NB0', 'NB')
            # Set all 'NB' flters to lower-case
            if 'NB' in cur_filter:
                cur_filter = cur_filter.lower()
            self.logger.info('Current filter %s' % (cur_filter))
            self.schedule_qf.update(rownum, 'Cur Filter', cur_filter, False)

        if result['TSCS.AZ'] not in (STATNONE, STATERROR):
            cur_az = '%8.2f' % result['TSCS.AZ']
            cur_az = cur_az.strip()
            self.schedule_qf.update(rownum, 'Cur Az', cur_az, False)

        if result['TSCS.EL'] not in (STATNONE, STATERROR):
            cur_el = '%8.2f' % result['TSCS.EL']
            cur_el = cur_el.strip()
            self.schedule_qf.update(rownum, 'Cur El', cur_el, False)

        now = datetime.datetime.now().strftime('%H:%M:%S')
        self.schedule_qf.update(rownum, 'start time', now, True)

        self.logger.debug('After update, schedule_qf.rows: %s' % self.schedule_qf.rows)
        self.model.set_schedule_qf(self.schedule_qf)

    def build_schedule_cb(self, widget):
        # update the model with any changes from GUI
        use_db = self.w.use_qdb.get_state()
        self.update_scheduler(use_db=use_db)

        sdlr = self.model.get_scheduler()
        self.view.nongui_do(sdlr.schedule_all)

    def update_db_cb(self, widget):

        self.update_scheduler(use_db=True, ignore_pgm_skip_flag=True)

        sdlr = self.model.get_scheduler()

        # store programs into db
        try:
            programs = self.qa.get_table('program')
            for key in sdlr.programs:
                self.logger.info("adding record for program '%s'" % (str(key)))
                programs[key] = sdlr.programs[key]
            transaction.commit()
        except Exception as e:
            self.logger.error('Unexpected error while updating program table in database: %s' % str(e))

        # store OBs into db
        try:
            ob_db = self.qa.get_table('ob')
            for ob in sdlr.oblist:
                key = (ob.program.proposal, ob.name)
                self.logger.info("adding record for OB '%s'" % (str(key)))
                ob_db[key] = ob
            transaction.commit()
        except Exception as e:
            self.logger.error('Unexpected error while updating ob table in database: %s' % str(e))

    def set_plot_pct_cb(self, w, val):
        #print(('pct', val))
        self.controller.idx_tgt_plots = val
        self.model.select_schedule(self.model.selected_schedule)
        return True

    def set_plot_limit_cb(self, w, val):
        #print(('limit', val))
        self.controller.num_tgt_plots = val
        self.model.select_schedule(self.model.selected_schedule)
        return True

#END
