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
import entity
import misc

class ControlPanel(PlBase.Plugin):

    def __init__(self, model, view, controller, logger):
        super(ControlPanel, self).__init__(model, view, controller, logger)

        self.input_dir = "inputs"
        
    def build_gui(self, container):
        vbox = Widgets.VBox()
        vbox.set_border_width(4)
        vbox.set_spacing(2)

        sw = Widgets.ScrollArea()
        sw.set_widget(vbox)

        fr = Widgets.Frame("Factors")

        captions = (('Slew weight:', 'label', 'Slew weight', 'entry'),
                    ('Delay weight:', 'label', 'Delay weight', 'entry'),
                    ('Filter weight:', 'label', 'Filter weight', 'entry'),
                    ('Rank weight:', 'label', 'Rank weight', 'entry'),
                    ('Priority weight:', 'label', 'Priority weight', 'entry'),
                    ('Build Schedule', 'button'),
                    )
        w, b = Widgets.build_info(captions, orientation='vertical')
        self.w = b

        b.slew_weight.set_text(str(self.model.w_slew))
        b.delay_weight.set_text(str(self.model.w_delay))
        b.filter_weight.set_text(str(self.model.w_filterchange))
        b.rank_weight.set_text(str(self.model.w_rank))
        b.priority_weight.set_text(str(self.model.w_priority))
        b.build_schedule.add_callback('activated', self.build_schedule_cb)

        fr.set_widget(w)
        vbox.add_widget(fr, stretch=0)

        fr = Widgets.Frame("Files")

        captions = (('Inputs:', 'label', 'Input dir', 'entry'),
                    ('Load Info', 'button'),
                    )
        w, b = Widgets.build_info(captions, orientation='vertical')
        self.w.update(b)

        b.load_info.add_callback('activated', self.initialize_model_cb)

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
            # read schedule
            schedule_file = os.path.join(self.input_dir, "schedule.csv")
            if not os.path.exists(schedule_file):
                self.logger.error("File not readable: %s" % (schedule_file))
                return
            self.logger.info("reading schedule from %s" % (schedule_file))
            schedule = entity.ScheduleFile(schedule_file, self.logger)
            # Set the appropriate "schedule" attributes in the
            # QueueModel
            if 'scheduletab' not in self.view.plugins:
                self.view.load_plugin('scheduletab', 'ScheduleTab', 'ScheduleTab', 'report', 'Schedule')
            self.model.set_schedule(schedule)
            self.model.set_schedule_info(schedule.schedule_info)

            # read proposals
            proposal_file = os.path.join(self.input_dir, "programs.csv")
            if not os.path.exists(proposal_file):
                self.logger.error("File not readable: %s" % (proposal_file))
                return
            self.logger.info("reading proposals from %s" % (proposal_file))
            programs = entity.ProgramsFile(proposal_file, self.logger)
            if 'programstab' not in self.view.plugins:
                self.view.load_plugin('programstab', 'ProgramsTab', 'ProgramsTab', 'report', 'Programs')
            self.model.set_programs(programs)
            self.model.set_programs_info(programs.programs_info)

            # read observing blocks
            oblist = {}
            oblist_info = []
            for propname in programs.programs_info:
                obfile = os.path.join(self.input_dir, propname+".csv")
                if not os.path.exists(obfile):
                    self.logger.error("File not readable: %s" % (obfile))
                    continue
                self.logger.info("loading observing blocks from file %s" % obfile)
                oblist[propname] = entity.OBListFile(obfile, self.logger, propname, programs.programs_info)
                oblist_info.extend(oblist[propname].obs_info)
            self.model.set_oblist(oblist)
            self.model.set_oblist_info(oblist_info)

        except Exception as e:
            self.logger.error("Error initializing: %s" % (str(e)))

        self.logger.info("model initialized")

    def build_schedule_cb(self, widget):
        # validate and make changes to model from gui
        self.model.w_slew = float(self.w.slew_weight.get_text())
        self.model.w_delay = float(self.w.delay_weight.get_text())
        self.model.w_filterchange = float(self.w.filter_weight.get_text())
        self.model.w_rank = float(self.w.rank_weight.get_text())
        
        self.view.nongui_do(self.model.schedule_all)
        
#END
