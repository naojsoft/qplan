#
# ProposalTab.py -- Plugin to create a widget to display the
#                   configuration files related to a proposal
#

import PlBase

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
        self.tabInfo = {'OB':          {'mod': 'OBListTab', 'obj': None},
                        'Targets':     {'mod': 'TgtCfgTab', 'obj': None},
                        'Environment': {'mod': 'EnvCfgTab', 'obj': None},
                        'Instrument':  {'mod': 'InsCfgTab', 'obj': None},
                        'Telescope':   {'mod': 'TelCfgTab', 'obj': None}}

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
            self.tabWidget.add_widget(widget, title=name)

        container.add_widget(self.tabWidget)

    def setProposal(self, proposal):
        self.proposal = proposal
        for name, d in self.tabInfo.iteritems():
            d['obj'].setProposal(proposal)
