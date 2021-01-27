#
# ControlPanel.py -- Controller plugin for operating scheduler
#
# Eric Jeschke (eric@naoj.org)
#

# stdlib imports
import sys, traceback
import os
import datetime
import dateutil

# ginga imports
from ginga.misc.Bunch import Bunch
from ginga.gw import Widgets

# Gen2 imports
have_gen2 = False
try:
    from g2cam.status.client import StatusClient
    from g2cam.status.common import STATNONE, STATERROR
    have_gen2 = True

except ImportError:
    pass

# local imports
from qplan.plugins import PlBase
from qplan import filetypes, misc, entity, common

have_qdb = False
try:
    from qplan import q_db, q_query
    have_qdb = True

except ImportError:
    pass


class ControlPanel(PlBase.Plugin):

    def __init__(self, controller):
        super(ControlPanel, self).__init__(controller)

        self.input_dir = "inputs"

        self.weights_qf = None
        self.schedule_qf = None
        self.programs_qf = None
        self.ob_qf_dict = None
        self.tgtcfg_qf_dict = None
        self.envcfg_qf_dict = None
        self.inscfg_qf_dict = None
        self.telcfg_qf_dict = None

        self.ob_info = {}
        self.ob_list = []

        self.qdb = None
        self.qa = None
        self.qq = None
        prefs = self.controller.get_preferences()
        self.cfg_path = os.path.join(prefs.folder, 'qdb.yml')

        self.spec_weights = Bunch(name='weightstab', module='WeightsTab',
                                  klass='WeightsTab', ptype='global',
                                  hidden=True,
                                  ws='report', tab='Weights', start=True)
        self.spec_schedule = Bunch(name='scheduletab', module='ScheduleTab',
                                   klass='ScheduleTab', ptype='global',
                                   hidden=True,
                                   ws='report', tab='Schedule', start=True)
        self.spec_programs = Bunch(name='programstab', module='ProgramsTab',
                                   klass='ProgramsTab', ptype='global',
                                   hidden=True,
                                   ws='report', tab='Programs', start=True)


    def connect_qdb(self):

        if not os.path.exists(self.cfg_path):
            raise ValueError("No queue database configuration in '{}'".format(self.cfg_path))
        self.qdb = q_db.QueueDatabase(self.logger)

        # Set up Queue database access
        try:
            self.qdb.read_config(self.cfg_path)
            self.qdb.connect()
        except Exception as e:
            errmsg = "Exception connecting to queue db: {}".format(e)
            self.logger.error(errmsg, exc_info=True)
            self.controller.gui_do(self.controller.show_error, errmsg,
                                   raisetab=True)
            self.qdb = None
            return

        self.qa = q_db.QueueAdapter(self.qdb)
        self.qq = q_query.QueueQuery(self.qa)

    def build_gui(self, container):
        vbox = Widgets.VBox()
        vbox.set_border_width(4)
        vbox.set_spacing(2)
        #vbox.cfg_expand(8, 8)

        sw = Widgets.ScrollArea()
        sw.set_widget(vbox)

        fr = Widgets.Frame("Files")

        captions = (('Inputs:', 'label', 'Input dir', 'entry'),
                    ('Load Info', 'button'),
                    ('Update Database from Files', 'button'),
                    ('Check Database against Files', 'button'),
                    ('Build Schedule', 'button', 'Use QDB', 'checkbutton'),
                    ("Remove scheduled OBs", 'checkbutton'))
        w, b = Widgets.build_info(captions, orientation='vertical')
        self.w = b

        sdlr = self.model.get_scheduler()
        b.input_dir.set_length(128)
        b.input_dir.set_text(self.controller.input_dir)
        b.load_info.set_tooltip("Load data from phase 2 files")
        b.load_info.add_callback('activated', self.initialize_model_cb)
        b.update_database_from_files.set_tooltip("Update Gen2 database from changes to phase 2 files")
        b.remove_scheduled_obs.set_state(sdlr.remove_scheduled_obs)
        def toggle_sdled_obs(w, tf):
            #print(('setting sdled obs', tf))
            sdlr.remove_scheduled_obs = tf
        b.remove_scheduled_obs.add_callback('activated', toggle_sdled_obs)

        if have_qdb and os.path.exists(self.cfg_path):
            b.update_database_from_files.add_callback('activated',
                                                      self.update_db_cb)
            b.check_database_against_files.add_callback('activated',
                                                        self.check_db_cb)
            b.use_qdb.set_state(True)
        else:
            b.update_database_from_files.set_enabled(False)
            b.check_database_against_files.set_enabled(False)
            b.use_qdb.set_state(False)
            b.use_qdb.set_enabled(False)

        b.build_schedule.set_tooltip("Schedule all periods defined in schedule tab")
        b.build_schedule.add_callback('activated', self.build_schedule_cb)

        b.use_qdb.set_tooltip("Use Gen2 queue database when scheduling")

        fr.set_widget(w)
        vbox.add_widget(fr, stretch=0)

        spacer = Widgets.Label('')
        vbox.add_widget(spacer, stretch=1)

        hbox = Widgets.HBox()

        adj = Widgets.Slider(orientation='horizontal', track=False)
        adj.set_limits(0, 100, incr_value=1)
        idx = self.controller.idx_tgt_plots
        adj.set_value(idx)
        #adj.resize(200, -1)
        adj.set_tooltip("Choose subset of targets plotted")
        #self.w.plotgrp = adj
        adj.add_callback('value-changed', self.set_plot_pct_cb)
        hbox.add_widget(adj, stretch=1)

        sb = Widgets.TextEntrySet()
        num = self.controller.num_tgt_plots
        sb.set_text(str(num))
        sb.set_tooltip("Adjust size of subset of targets plotted")
        sb.add_callback('activated', self.set_plot_limit_cb)
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
        self.controller.error_wrap(self.initialize_model)

    def initialize_model(self):
        self.input_dir = self.w.input_dir.get_text().strip()
        self.input_fmt = self.controller.input_fmt

        # read weights
        self.weights_qf = filetypes.WeightsFile(self.input_dir, self.logger,
                                                file_ext=self.input_fmt)
        # Load "Weights" Tab
        if not self.view.gpmon.has_plugin('weightstab'):
            self.view.load_plugin('weightstab', self.spec_weights)
            self.view.start_plugin('weightstab')
        self.model.set_weights_qf(self.weights_qf)

        # read schedule
        self.schedule_qf = filetypes.ScheduleFile(self.input_dir, self.logger,
                                                  file_ext=self.input_fmt)
        # Load "Schedule" Tab
        if not self.view.gpmon.has_plugin('scheduletab'):
            self.view.load_plugin('scheduletab', self.spec_schedule)
            self.view.start_plugin('scheduletab')
        self.model.set_schedule_qf(self.schedule_qf)

        # read proposals
        self.programs_qf = filetypes.ProgramsFile(self.input_dir, self.logger,
                                                  file_ext=self.input_fmt)
        if not self.view.gpmon.has_plugin('programstab'):
            self.view.load_plugin('programstab', self.spec_programs)
            self.view.start_plugin('programstab')
        self.model.set_programs_qf(self.programs_qf)

        # read observing blocks
        self.ob_qf_dict = {}
        self.tgtcfg_qf_dict = {}
        self.envcfg_qf_dict = {}
        self.inscfg_qf_dict = {}
        self.telcfg_qf_dict = {}

        self.ob_info = {}
        self.ob_list = []


    def load_program(self, propname):
        self.logger.info("attempting to read phase 2 info for '%s'" % (
            propname))
        try:
            pf = filetypes.ProgramFile(self.input_dir, self.logger,
                                       propname,
                                       self.programs_qf.programs_info,
                                       file_ext=self.input_fmt)

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
            self.model.set_ob_qf_dict(self.ob_qf_dict)

            return True

        except Exception as e:
            errmsg = "error attempting to read phase 2 info for '%s'\n" % (
                propname)
            errmsg += "\n".join([e.__class__.__name__, str(e)])
            try:
                (type, value, tb) = sys.exc_info()
                tb_str = "\n".join(traceback.format_tb(tb))
            except Exception as e:
                tb_str = "Traceback information unavailable."
            errmsg += tb_str
            self.logger.error(errmsg)
            self.controller.gui_do(self.controller.show_error, errmsg,
                                   raisetab=True)
            return False

    def update_scheduler(self, use_db=False, ignore_pgm_skip_flag=False):
        sdlr = self.model.get_scheduler()
        try:
            if use_db:
                if self.qdb is None:
                    self.connect_qdb()

            sdlr.set_weights(self.weights_qf.weights)
            sdlr.set_schedule_info(self.schedule_qf.schedule_info)
            pgms = self.programs_qf.programs_info
            sdlr.set_programs_info(pgms, ignore_pgm_skip_flag)
            self.logger.info('list of programs to be scheduled %s' % sdlr.programs.keys())

            # TODO: this maybe should be done in the Model
            ob_keys = set([])
            ob_dict = {}
            propnames = list(self.programs_qf.programs_info.keys())
            okprops = []
            # Note: if the ignore_pgm_skip_flag is set to True, then
            # we don't pay attention to the "skip" flag in the
            # Programs sheet and thus consider all OB's in all
            # Programs. Otherwise, we do pay attention to the "skip"
            # flag and ignore all OB's in "skipped" programs.
            for propname in propnames:
                if not ignore_pgm_skip_flag and pgms[propname].skip:
                    self.logger.info('skip flag for program %s is set - skipping all OB in this program' % propname)
                    continue

                if propname not in self.ob_info:
                    # If we haven't read these OBs in already, read them now
                    if use_db:
                        oblist = list(self.qq.get_obs_by_proposal(propname))

                    else:
                        if propname not in self.ob_qf_dict:
                            if not self.load_program(propname):
                                continue
                        oblist = self.ob_qf_dict[propname].obs_info

                    # cache the information about the OBs so we don't have
                    # to reconstruct it over and over
                    _key_lst = [(propname, ob.name) for ob in oblist]
                    _key_dct = dict(zip(_key_lst, oblist))

                    info = Bunch(oblist=oblist, obkeys=_key_lst, obdict=_key_dct)
                    self.ob_info[propname] = info

                info = self.ob_info[propname]

                okprops.append(propname)

                ob_keys = ob_keys.union(set(info.obkeys))
                ob_dict.update(info.obdict)

            self.logger.info("%s OBs after excluding skipped programs." % (
                len(ob_keys)))

            do_not_execute = set([])
            props = {}

            # Remove keys for OBs that are already executed
            if use_db:
                self.logger.info("getting do not execute OB info")
                dne_obs, props = self.qq.get_do_not_execute_ob_info(okprops)

                do_not_execute = set(dne_obs)

            elif self.model.completed_obs is not None:
                do_not_execute = set(list(self.model.completed_obs.keys()))

                # Painful reconstruction of time already accumulated running the
                # programs for executed OBs.  Needed to inform scheduler so that
                # it can correctly calculate when to stop allocating OBs for a
                # program that has reached its time limit.
                props = {}
                for ob_key in do_not_execute:
                    (propid, obcode) = ob_key[:2]
                    bnch = props.setdefault(propid, Bunch(obcount=0,
                                                          sched_time=0.0))
                    info = self.model.completed_obs[ob_key]
                    # 2021-01-11 EJ
                    # Added extra overhead charge
                    bnch.sched_time += (info['acct_time'] *
                                        common.extra_overhead_factor)
                    bnch.obcount += 1

            sdlr.set_apriori_program_info(props)

            ob_keys -= do_not_execute
            self.logger.info("%s OBs after removing executed OBs." % (
                len(ob_keys)))

            # for a deterministic result
            ob_keys = list(ob_keys)
            ob_keys.sort()

            # Now turn the keys back into actual OB list
            sdlr_oblist = [ob_dict[key] for key in ob_keys]

            # TODO: only needed if we ADD or REMOVE programs
            sdlr.set_oblist_info(sdlr_oblist)

        except Exception as e:
            errmsg = 'Error storing into scheduler: {}\n'.format(str(e))
            #self.logger.error("Error storing into scheduler: %s" % (str(e)))
            errmsg += "\n".join([e.__class__.__name__, str(e)])
            self.logger.error(errmsg)
            self.controller.gui_do(self.controller.show_error, errmsg, raisetab=True)
            raise e

        self.logger.info("scheduler initialized")

    def build_schedule_cb(self, widget):
        # update the model with any changes from GUI
        use_db = self.w.use_qdb.get_state()
        self.update_scheduler(use_db=use_db)

        sdlr = self.model.get_scheduler()
        self.view.nongui_do(sdlr.schedule_all)

    def update_db_cb(self, widget):

        self.update_scheduler(use_db=False, ignore_pgm_skip_flag=True)

        sdlr = self.model.get_scheduler()

        try:
            if self.qdb is None:
                self.connect_qdb()
        except Exception as e:
            self.logger.error('Unexpected error while connecting to queue database: %s' % str(e), exc_info=True)

        # store programs into db
        try:
            qt = self.qa.get_table('program')
            for key in sdlr.programs:
                self.logger.info("adding record for program '%s'" % (str(key)))
                qt.put(sdlr.programs[key])

        except Exception as e:
            self.logger.error('Unexpected error while updating program table in database: %s' % str(e), exc_info=True)

        # store OBs into db
        try:
            qt = self.qa.get_table('ob')
            for ob in sdlr.oblist:
                self.logger.info("adding record for OB '%s'" % (str(ob)))
                qt.put(ob)

        except Exception as e:
            self.logger.error('Unexpected error while updating ob table in database: %s' % str(e), exc_info=True)

        self.logger.info("done updating database")

    def check_db_cb(self, widget):

        self.update_scheduler(use_db=False, ignore_pgm_skip_flag=True)

        sdlr = self.model.get_scheduler()

        try:
            if self.qdb is None:
                self.connect_qdb()

        except Exception as e:
            self.logger.error("Unexpected error while connecting to queue database: %s" % str(e), exc_info=True)
            return

        # Now check that we have everything in the database
        self.logger.info("Checking consistency of queue database to files")
        self.qq.clear_cache()

        # check programs in db
        self.logger.info("checking programs...")
        try:
            for key in sdlr.programs:
                pgm_f = sdlr.programs[key]
                pgm_d = self.qq.get_program(pgm_f.proposal)
                if pgm_d is None:
                    self.logger.error("No program '%s' in database" % (str(key)))
                    continue

                if pgm_d != pgm_f:
                    errmsg = "program '%s' in database and files differ" % (str(key))
                    self.logger.error(errmsg)
                    self.controller.gui_do(self.controller.show_error, errmsg,
                                           raisetab=True)
                    print("-- FILE --")
                    print(pgm_f.__dict__)
                    print("-- DB --")
                    print(pgm_d.__dict__)
                    print("")
                    print("-------------------------------")
                else:
                    self.logger.debug("program '%s' is a match" % (str(key)))
                    continue
        except Exception as e:
            self.logger.error("Unexpected error while checking program table in database: %s" % str(e), exc_info=True)
            return
        self.logger.info("done checking programs")

        # check OBs in db
        self.logger.info("checking OBs...")
        try:
            for ob_f in sdlr.oblist:
                ob_key = (ob_f.key['program'], ob_f.key['name'])
                ob_d = self.qq.get_ob(ob_key)
                if ob_d is None:
                    self.logger.error("No OB matching '%s' in database" % (str(ob_key)))
                    continue

                if ob_d != ob_f:
                    errmsg = "OB '%s' in database and files differ" % (str(ob_key))
                    self.logger.error(errmsg)
                    self.controller.gui_do(self.controller.show_error, errmsg,
                                           raisetab=True)
                else:
                    self.logger.debug("OB '%s' is a match" % (str(ob_key)))
                    continue
        except Exception as e:
            self.logger.error("Unexpected error while checking ob table in database: %s" % str(e), exc_info=True)
            return
        self.logger.info("done checking OBs")

    def set_plot_pct_cb(self, w, val):
        #print(('pct', val))
        self.controller.idx_tgt_plots = val
        self.model.select_schedule(self.model.selected_schedule)
        return True

    def set_plot_limit_cb(self, w):
        #print(('limit', val))
        val = int(w.get_text())
        self.controller.num_tgt_plots = val
        self.model.select_schedule(self.model.selected_schedule)
        return True

#END
