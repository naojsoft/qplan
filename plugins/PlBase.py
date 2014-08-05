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

    def __init__(self, model, view, controller, logger):
        super(Plugin, self).__init__()
        self.model = model
        self.view = view
        self.controller = controller
        self.logger = logger

    def build_gui(self, widget):
        # Subclass can override this method, but doesn't have to
        pass

    def start(self):
        # Subclass can override this method, but doesn't have to
        pass
        
    def stop(self):
        # Subclass can override this method, but doesn't have to
        pass

#END
