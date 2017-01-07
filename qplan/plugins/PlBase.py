#
# PlBase.py -- Base class for QueueMon plugins
#
# Eric Jeschke (eric@naoj.org)
#
"""
This class implements the base class for StatMon plugins.  You can add any
convenience methods or classes that would be generally useful across
different plugins.
"""

class PluginError(Exception):
    pass

class Plugin(object):

    def __init__(self, controller):
        super(Plugin, self).__init__()

        # setup MVC refs
        self.model = controller.get_model()
        self.view = controller
        self.controller = controller

        # and establish a logger
        self.logger = controller.get_logger()

    def build_gui(self, container):
        # Subclass can override this method, but doesn't have to
        pass

    def start(self):
        # Subclass can override this method, but doesn't have to
        pass

    def stop(self):
        # Subclass can override this method, but doesn't have to
        pass

#END
