#! /usr/bin/env python
#
# Model.py -- Observing Queue Planner Model
#
#  E. Jeschke
#
import os
import time
from datetime import timedelta

# 3rd party imports
import yaml
import numpy
from ginga.misc import Callback, Bunch

# local imports
from . import filetypes

class QueueModel(Callback.Callbacks):

    def __init__(self, logger, scheduler):
        Callback.Callbacks.__init__(self)

        self.logger = logger
        self.sdlr = scheduler

        self.weights_qf = None
        self.programs_qf = None
        self.schedule_qf = None
        self.proposal_tab_names = {}
        self.ppccfg_qf_dict = {}
        self.ob_qf_dict = {}
        self.tgtcfg_qf_dict = {}
        self.envcfg_qf_dict = {}
        self.inscfg_qf_dict = {}
        self.telcfg_qf_dict = {}
        self.completed_obs = None

        # For callbacks
        for name in ('schedule-selected',
                     'programs-file-loaded', 'schedule-file-loaded',
                     'weights-file-loaded', 'programs-updated',
                     'schedule-updated', 'weights-updated', 'show-proposal',
                     'qc-plan-loaded'):
            self.enable_callback(name)

    def get_scheduler(self):
        return self.sdlr

    def set_weights_qf(self, weights_qf):
        self.weights_qf = weights_qf
        self.make_callback('weights-file-loaded', self.weights_qf)

    def update_weights(self, row, colHeader, value, parse_flag):
        self.logger.debug('row %d colHeader %s value %s' % (row, colHeader, value))
        self.weights_qf.update(row, colHeader, value, parse_flag)
        self.make_callback('weights-updated')

    def set_programs_qf(self, programs_qf):
        self.programs_qf = programs_qf
        self.make_callback('programs-file-loaded', self.programs_qf)

    def update_programs(self, row, colHeader, value, parse_flag):
        self.logger.debug('row %d colHeader %s value %s' % (row, colHeader, value))
        self.programs_qf.update(row, colHeader, value, parse_flag)
        #self.set_programs(self.programs_qf.programs_info)
        self.make_callback('programs-updated')

    def set_ppccfg_qf_dict(self, ppccfg_dict):
        self.ppccfg_qf_dict = ppccfg_dict

    def set_tgtcfg_qf_dict(self, tgtcfg_dict):
        self.tgtcfg_qf_dict = tgtcfg_dict

    def set_envcfg_qf_dict(self, envcfg_dict):
        self.envcfg_qf_dict = envcfg_dict

    def set_inscfg_qf_dict(self, inscfg_dict):
        self.inscfg_qf_dict = inscfg_dict

    def set_telcfg_qf_dict(self, telcfg_dict):
        self.telcfg_qf_dict = telcfg_dict

    def set_ob_qf_dict(self, obdict):
        self.ob_qf_dict = obdict

    def update_ppccfg(self, proposal, row, colHeader, value, parse_flag):
        self.ppccfg_qf_dict[proposal].update(row, colHeader, value, parse_flag)

    def update_oblist(self, proposal, row, colHeader, value, parse_flag):
        self.ob_qf_dict[proposal].update(row, colHeader, value, parse_flag)

    def update_tgtcfg(self, proposal, row, colHeader, value, parse_flag):
        self.tgtcfg_qf_dict[proposal].update(row, colHeader, value, parse_flag)

    def update_envcfg(self, proposal, row, colHeader, value, parse_flag):
        self.envcfg_qf_dict[proposal].update(row, colHeader, value, parse_flag)

    def update_inscfg(self, proposal, row, colHeader, value, parse_flag):
        self.inscfg_qf_dict[proposal].update(row, colHeader, value, parse_flag)

    def update_telcfg(self, proposal, row, colHeader, value, parse_flag):
        self.telcfg_qf_dict[proposal].update(row, colHeader, value, parse_flag)

    def setProposalForPropTab(self, proposal):
        # This method is called by the ProgramsTab.doubleClicked
        # method. That method loads a ProposalTab widget for the
        # proposal on which the user double-clicked. This method sets
        # the proposalForTab attribute so that the PropsalTab can
        # figure out which proposal it is supposed to display.
        self.proposalForPropTab = proposal

    def set_schedule_qf(self, schedule_qf):
        # This method gets called when a Schedule is loaded from an
        # input data file. Set our schedule attribute and invoke the
        # method attached to the schedule-file-loaded callback.
        self.schedule_qf = schedule_qf
        self.make_callback('schedule-file-loaded', self.schedule_qf)

    def update_schedule(self, row, colHeader, value, parse_flag):
        # This method gets called when the user updates a value in the
        # ScheduleTab GUI. Update our schedule and schedule_recs
        # attributes. Finally, invoke the method attached to the
        # schedule-updated callback.
        self.logger.debug('row %d colHeader %s value %s' % (row, colHeader, value))
        self.schedule_qf.update(row, colHeader, value, parse_flag)
        #self.set_schedule_info(self.schedule.schedule_info)
        self.make_callback('schedule-updated')

    def select_schedule(self, schedule):
        self.selected_schedule = schedule
        self.make_callback('schedule-selected', schedule)

    def load_qc_plan(self, plan_file):
        if self.programs_qf is None:
            raise ValueError("No programs table defined yet")

        with open(plan_file, 'r') as in_f:
            buf = in_f.read()
        pgms_changes_dct = yaml.safe_load(buf)

        # send changes to the rows and reparse the data
        self.programs_qf.update_table(pgms_changes_dct['programs'],
                                      parse_flag=True)

        # to force update by the GUI to the table widget
        self.make_callback('programs-file-loaded', self.programs_qf)

        _dir, plan_name = os.path.split(plan_file)
        plan_name, _ext = os.path.splitext(plan_name)
        self.make_callback('qc-plan-loaded', plan_name)


# END
