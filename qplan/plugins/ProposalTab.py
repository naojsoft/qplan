#
# ProposalTab.py -- Plugin to create a widget to display the
#                   configuration files related to a proposal
#

from . import PlBase

import entity
from ginga.misc import ModuleManager
from ginga.gw import Widgets

class ProposalTab(PlBase.Plugin):

    def __init__(self, model, view, controller, logger):
        super(ProposalTab, self).__init__(model, view, controller, logger)

        self.mm = ModuleManager.ModuleManager(logger)

        # Register a callback function for when the we want to show
        # the ProposalTab
        self.model.add_callback('show-proposal', self.build_gui)
        self.tabs = ['OB', 'Targets', 'Environment', 'Instrument', 'Telescope']
        self.tabInfo = {'OB':          {'mod': 'OBListTab', 'obj': None, 'inputDataDict': self.model.ob_qf_dict},
                        'Targets':     {'mod': 'TgtCfgTab', 'obj': None, 'inputDataDict': self.model.tgtcfg_qf_dict},
                        'Environment': {'mod': 'EnvCfgTab', 'obj': None, 'inputDataDict': self.model.envcfg_qf_dict},
                        'Instrument':  {'mod': 'InsCfgTab', 'obj': None, 'inputDataDict': self.model.inscfg_qf_dict},
                        'Telescope':   {'mod': 'TelCfgTab', 'obj': None, 'inputDataDict': self.model.telcfg_qf_dict}}

        # From the QueueModel object, get the proposal number that we
        # need to display. That value was set by the
        # ProgramsTab.doubleClicked method when the user selected the
        # proposal they wanted to display.
        self.proposal = self.model.proposalForPropTab

    def build_gui(self, container):

        container.set_margins(2, 2, 2, 2)
        container.set_spacing(4)

        self.tabWidget = Widgets.TabWidget()

        for name in self.tabs:
            modName = self.tabInfo[name]['mod']
            self.mm.loadModule(modName)
            module = self.mm.getModule(modName)
            klass = getattr(module, modName)
            self.tabInfo[name]['obj'] = klass(self.model, self.view, self.controller, self.logger)

            widget = Widgets.VBox()
            self.tabInfo[name]['obj'].build_gui(widget)
            self.tabInfo[name]['obj'].setProposal(self.proposal)
            self.tabWidget.add_widget(widget, title=name)
            self.tabInfo[name]['obj'].populate_cb(self.model, self.tabInfo[name]['inputDataDict'][self.proposal])

        container.add_widget(self.tabWidget)

        # Create a "Close" button so the user can easily close the
        # ProposalTab
        hbox = Widgets.HBox()
        closeTabButton = Widgets.Button('Close %s' % self.proposal)
        closeTabButton.add_callback('activated', self.close_tab_cb)
        closeTabButton.set_tooltip("Close proposal %s tab" % self.proposal)
        hbox.add_widget(closeTabButton, stretch=1)

        container.add_widget(hbox)

    def close_tab_cb(self, widget):
        self.logger.info('Closing tab for proposal %s' % self.proposal)
        self.view.close_plugin(self.proposal)
