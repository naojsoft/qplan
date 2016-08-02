#! /usr/bin/env python
#
# Model.py -- Observing Queue Planner Model
#
#  Eric Jeschke (eric@naoj.org)
#
import os
import time
from datetime import timedelta
import pytz
import numpy

# 3rd party imports
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
        self.ob_qf_dict = {}
        self.tgtcfg_qf_dict = {}
        self.envcfg_qf_dict = {}
        self.inscfg_qf_dict = {}
        self.telcfg_qf_dict = {}
        self.completed_keys = None

        # For callbacks
        for name in ('schedule-selected',
                     'programs-file-loaded', 'schedule-file-loaded',
                     'weights-file-loaded',
                     'show-oblist', 'show-tgtcfg', 'show-envcfg', 'show-inscfg',
                     'show-telcfg', 'programs-updated',
                     'schedule-updated', 'oblist-updated',
                     'tgtcfg-updated', 'envcfg-updated', 'inscfg-updated',
                     'telcfg-updated', 'weights-updated', 'show-proposal'):
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

    def update_ob_qf_dict(self, proposal):
        filepath = self.ob_qf_dict[proposal].filepath
        self.ob_qf_dict[proposal] = filetypes.OBListFile(filepath,
                                                         self.logger,
                                                         proposal,
                                                         self.programs_qf.programs_info,
                                                         self.telcfg_qf_dict[proposal].tel_cfgs,
                                                         self.tgtcfg_qf_dict[proposal].tgt_cfgs,
                                                         self.inscfg_qf_dict[proposal].ins_cfgs,
                                                         self.envcfg_qf_dict[proposal].env_cfgs)

    def update_oblist(self, proposal, row, colHeader, value, parse_flag):
        self.ob_qf_dict[proposal].update(row, colHeader, value, parse_flag)
        self.make_callback('oblist-updated', proposal)

    def update_tgtcfg(self, proposal, row, colHeader, value, parse_flag):
        self.tgtcfg_qf_dict[proposal].update(row, colHeader, value, parse_flag)
        self.update_ob_qf_dict(proposal)
        self.make_callback('tgtcfg-updated', proposal)

    def update_envcfg(self, proposal, row, colHeader, value, parse_flag):
        self.envcfg_qf_dict[proposal].update(row, colHeader, value, parse_flag)
        self.update_ob_qf_dict(proposal)
        self.make_callback('envcfg-updated', proposal)

    def update_inscfg(self, proposal, row, colHeader, value, parse_flag):
        self.inscfg_qf_dict[proposal].update(row, colHeader, value, parse_flag)
        filepath = self.ob_qf_dict[proposal].filepath
        self.update_ob_qf_dict(proposal)
        self.make_callback('inscfg-updated', proposal)

    def update_telcfg(self, proposal, row, colHeader, value, parse_flag):
        self.telcfg_qf_dict[proposal].update(row, colHeader, value, parse_flag)
        self.update_ob_qf_dict(proposal)
        self.make_callback('telcfg-updated', proposal)

    def show_proposal(self, req_proposal, obListTab):
        self.logger.debug('req_proposal %s OBListFile %s ' % (req_proposal, self.ob_qf_dict[req_proposal]))
        self.make_callback('show-oblist', req_proposal, self.ob_qf_dict[req_proposal])
        self.make_callback('show-tgtcfg', req_proposal, self.tgtcfg_qf_dict[req_proposal])
        self.make_callback('show-envcfg', req_proposal, self.envcfg_qf_dict[req_proposal])
        self.make_callback('show-inscfg', req_proposal, self.inscfg_qf_dict[req_proposal])
        self.make_callback('show-telcfg', req_proposal, self.telcfg_qf_dict[req_proposal])

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

    ## def schedule_all(self):

    ##     #self.make_callback('schedule-cleared')

    ##     self.sdlr.schedule_all()

    ##     #self.make_callback('schedule-completed', completed, uncompleted, self.schedules)

    def select_schedule(self, schedule):
        self.selected_schedule = schedule
        self.make_callback('schedule-selected', schedule)

# END
