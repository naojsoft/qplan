#
# ProposalTab.py -- Plugin to create a widget to display the
#                   configuration files related to a proposal
#
from ginga.misc import ModuleManager
from ginga.gw import Widgets

from qplan import entity
from qplan.plugins import PlBase

class ProposalTab(PlBase.Plugin):

    def __init__(self, controller):
        super(ProposalTab, self).__init__(controller)

        # Hmm.. Should this share MM of view?
        self.mm = ModuleManager.ModuleManager(self.logger)
        #self.mm = self.controller.mm

        # Register a callback function for when the we want to show
        # the ProposalTab
        self.model.add_callback('show-proposal', self.build_gui)

        # From the QueueModel object, get the proposal number that we
        # need to display. That value was set by the
        # ProgramsTab.doubleClicked method when the user selected the
        # proposal they wanted to display.
        self.proposal = self.model.proposalForPropTab

        self.tabs = self.model.proposal_tab_names[self.proposal]
        self.tabInfo = {'OB':          {'mod': 'OBListTab', 'obj': None, 'inputDataDict': self.model.ob_qf_dict},
                        'Targets':     {'mod': 'TgtCfgTab', 'obj': None, 'inputDataDict': self.model.tgtcfg_qf_dict},
                        'Environment': {'mod': 'EnvCfgTab', 'obj': None, 'inputDataDict': self.model.envcfg_qf_dict},
                        'Instrument':  {'mod': 'InsCfgTab', 'obj': None, 'inputDataDict': self.model.inscfg_qf_dict},
                        'Telescope':   {'mod': 'TelCfgTab', 'obj': None, 'inputDataDict': self.model.telcfg_qf_dict},
                        'PPC':         {'mod': 'PPCCfgTab', 'obj': None, 'inputDataDict': self.model.ppccfg_qf_dict}}

    def build_gui(self, container):

        container.set_margins(2, 2, 2, 2)
        container.set_spacing(4)

        self.tabWidget = Widgets.TabWidget()

        for name in self.tabs:
            modName = self.tabInfo[name]['mod']
            self.mm.load_module(modName)
            module = self.mm.get_module(modName)
            klass = getattr(module, modName)
            self.tabInfo[name]['obj'] = klass(self.controller)

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
        hbox.add_widget(closeTabButton)
        hbox.add_widget(Widgets.Label(''), stretch=1)

        container.add_widget(hbox)

    def close_tab_cb(self, widget):
        self.logger.info('Closing tab for proposal %s' % self.proposal)
        self.view.stop_plugin(self.proposal)
