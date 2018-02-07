#
# This is open-source software licensed under a BSD license.
# Please see the file LICENSE.txt for details.
#
import sys, os
import threading

from ginga.misc import Callback

class ControlError(Exception):
    pass

class Controller(Callback.Callbacks):

    def __init__(self, logger, threadPool, module_manager, preferences,
                 ev_quit, model):
        Callback.Callbacks.__init__(self)

        self.logger = logger
        self.threadPool = threadPool
        self.mm = module_manager
        self.prefs = preferences
        # event for controlling termination of threads executing in this
        # object
        self.ev_quit = ev_quit
        self.model = model

        self.settings = self.prefs.create_category('general')

        # For asynchronous tasks on the thread pool
        self.tag = 'master'
        self.shares = ['threadPool', 'logger']

        self.input_dir = self.settings.get('input_dir', '.')
        self.output_dir = self.settings.get('output_dir', None)

        self.idx_tgt_plots = 0
        self.num_tgt_plots = 100

    def set_input_dir(self, path):
        self.input_dir = path

    def set_output_dir(self, path):
        self.output_dir = path

    def set_input_fmt(self, fmt):
        self.input_fmt = fmt

    def get_logger(self):
        return self.logger

    def get_model(self):
        return self.model

    def set_loglevel(self, level):
        handlers = self.logger.handlers
        for hdlr in handlers:
            hdlr.setLevel(level)

# END
