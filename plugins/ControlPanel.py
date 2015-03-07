#
# ControlPanel.py -- AirMass chart plugin
# 
# Eric Jeschke (eric@naoj.org)
#
import os.path

from ginga.misc import Bunch
from ginga.misc import Widgets
from PyQt4 import QtGui, QtCore

import PlBase
import filetypes
import misc

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

    def build_gui(self, container):
        vbox = Widgets.VBox()
        vbox.set_border_width(4)
        vbox.set_spacing(2)

        sw = Widgets.ScrollArea()
        sw.set_widget(vbox)

        fr = Widgets.Frame("Files")

        captions = (('Inputs:', 'label', 'Input dir', 'entry'),
                    ('Load Info', 'button'),
                    ('Build Schedule', 'button'))
        w, b = Widgets.build_info(captions, orientation='vertical')
        self.w = b

        b.input_dir.set_length(128)
        b.input_dir.set_text(self.controller.input_dir)
        b.load_info.add_callback('activated', self.initialize_model_cb)
        b.build_schedule.add_callback('activated', self.build_schedule_cb)

        fr.set_widget(w)
        vbox.add_widget(fr, stretch=0)

        spacer = Widgets.Label('')
        vbox.add_widget(spacer, stretch=1)
        
        ## btns = Widgets.HBox()
        ## btns.set_spacing(3)

        ## btn = Widgets.Button("Close")
        ## #btn.add_callback('activated', lambda w: self.close())
        ## btns.add_widget(btn, stretch=0)
        ## btns.add_widget(Widgets.Label(''), stretch=1)
        ## vbox.add_widget(btns, stretch=0)

        self.sw = sw
        top_w = sw.get_widget()

        layout = QtGui.QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        container.setLayout(layout)

        layout.addWidget(top_w, stretch=1)

    def initialize_model_cb(self, widget):
        self.input_dir = self.w.input_dir.get_text().strip()

        try:
            # read weights
            weights_file = os.path.join(self.input_dir, "weights.csv")
            if not os.path.exists(weights_file):
                self.logger.error("File not readable: %s" % (weights_file))
                return
            self.logger.info("reading weights from %s" % (weights_file))
            self.weights_qf = filetypes.WeightsFile(weights_file, self.logger)
            # Load "Weights" Tab
            if 'weightstab' not in self.view.plugins:
                self.view.load_plugin('weightstab', 'WeightsTab', 'WeightsTab', 'report', 'Weights')
            self.model.set_weights_qf(self.weights_qf)

            # read schedule
            schedule_file = os.path.join(self.input_dir, "schedule.csv")
            if not os.path.exists(schedule_file):
                self.logger.error("File not readable: %s" % (schedule_file))
                return
            self.logger.info("reading schedule from %s" % (schedule_file))
            self.schedule_qf = filetypes.ScheduleFile(schedule_file, self.logger)
            # Load "Schedule" Tab
            if 'scheduletab' not in self.view.plugins:
                self.view.load_plugin('scheduletab', 'ScheduleTab', 'ScheduleTab', 'report', 'Schedule')
            self.model.set_schedule_qf(self.schedule_qf)

            # read proposals
            proposal_file = os.path.join(self.input_dir, "programs.csv")
            if not os.path.exists(proposal_file):
                self.logger.error("File not readable: %s" % (proposal_file))
                return
            self.logger.info("reading proposals from %s" % (proposal_file))
            self.programs_qf = filetypes.ProgramsFile(proposal_file, self.logger)
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
                obdir = os.path.join(self.input_dir, propname)
                if not os.path.isdir(obdir):
                    self.logger.error("Directory not readable: %s" % (obdir))
                    continue

                # Read telcfg
                csvfile = os.path.join(obdir, "telcfg.csv")
                if not os.path.exists(csvfile):
                    self.logger.error("File not readable: %s" % (csvfile))
                    continue
                self.logger.info("loading telescope configuration file %s" % (csvfile))
                telcfg_qf = filetypes.TelCfgFile(csvfile, self.logger)
                self.telcfg_qf_dict[propname] = telcfg_qf
                self.model.set_telcfg_qf_dict(self.telcfg_qf_dict)
                
                # Read inscfg
                csvfile = os.path.join(obdir, "inscfg.csv")
                if not os.path.exists(csvfile):
                    self.logger.error("File not readable: %s" % (csvfile))
                    continue
                self.logger.info("loading instrument configuration file %s" % (csvfile))
                inscfg_qf = filetypes.InsCfgFile(csvfile, self.logger)
                self.inscfg_qf_dict[propname] = inscfg_qf
                self.model.set_inscfg_qf_dict(self.inscfg_qf_dict)
                
                # Read envcfg
                csvfile = os.path.join(obdir, "envcfg.csv")
                if not os.path.exists(csvfile):
                    self.logger.error("File not readable: %s" % (csvfile))
                    continue
                self.logger.info("loading environment configuration file %s" % (csvfile))
                envcfg_qf = filetypes.EnvCfgFile(csvfile, self.logger)
                self.envcfg_qf_dict[propname] = envcfg_qf
                self.model.set_envcfg_qf_dict(self.envcfg_qf_dict)

                # Read targets
                csvfile = os.path.join(obdir, "targets.csv")
                if not os.path.exists(csvfile):
                    self.logger.error("File not readable: %s" % (csvfile))
                    continue
                self.logger.info("loading targets configuration file %s" % (csvfile))
                tgtcfg_qf = filetypes.TgtCfgFile(csvfile, self.logger)
                self.tgtcfg_qf_dict[propname] = tgtcfg_qf
                self.model.set_tgtcfg_qf_dict(self.tgtcfg_qf_dict)
                
                # Finally, read OBs
                obfile = os.path.join(obdir, "ob.csv")
                if not os.path.exists(obfile):
                    self.logger.error("File not readable: %s" % (obfile))
                    continue
                self.ob_qf_dict[propname] = filetypes.OBListFile(obfile,
                                                                 self.logger,
                                                                 propname,
                                                                 self.programs_qf.programs_info,
                                                                 telcfg_qf.tel_cfgs,
                                                                 tgtcfg_qf.tgt_cfgs,
                                                                 inscfg_qf.ins_cfgs,
                                                                 envcfg_qf.env_cfgs)
                #self.oblist_info.extend(self.oblist[propname].obs_info)
            self.model.set_ob_qf_dict(self.ob_qf_dict)

        except Exception as e:
            self.logger.error("Error initializing: %s" % (str(e)))


    def update_model(self):
        try:
            self.model.set_weights(self.weights_qf.weights)
            self.model.set_schedule_info(self.schedule_qf.schedule_info)
            self.model.set_programs_info(self.programs_qf.programs_info)

            # TODO: this maybe should be done in the Model
            self.oblist_info = []
            propnames = list(self.programs_qf.programs_info.keys())
            propnames.sort()
            #for propname in self.programs_qf.programs_info:
            for propname in propnames:
                self.oblist_info.extend(self.ob_qf_dict[propname].obs_info)
            # TODO: only needed if we ADD or REMOVE programs
            self.model.set_oblist_info(self.oblist_info)

        except Exception as e:
            self.logger.error("Error storing into model: %s" % (str(e)))

        self.logger.info("model initialized")

    def build_schedule_cb(self, widget):
        # update the model with any changes from GUI
        self.update_model()
        
        self.view.nongui_do(self.model.schedule_all)
        
#END
