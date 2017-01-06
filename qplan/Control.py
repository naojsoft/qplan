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

        self.settings = self.prefs.createCategory('general')

        # For asynchronous tasks on the thread pool
        self.tag = 'master'
        self.shares = ['threadPool', 'logger']

        self.input_dir = '.'

        self.idx_tgt_plots = 0
        self.num_tgt_plots = 10

    def set_input_dir(self, path):
        self.input_dir = path

    def set_input_fmt(self, fmt):
        self.input_fmt = fmt

#END
