#
# ProgramsTab.py -- Plugin to display/edit the programs in a table GUI
#

from ginga.misc.Bunch import Bunch

from qtpy import QtCore
from qtpy import QtWidgets as QtGui

from qplan.plugins import PlBase
from qplan.plugins import QueueFileTab

class ProgramsTab(QueueFileTab.QueueFileTab):

    def __init__(self, controller):
        super(ProgramsTab, self).__init__(controller)

        # Register a callback function for when the QueueModel loads
        # the programs file
        self.model.add_callback('programs-file-loaded', self.populate_cb)
        # Register a callback function for when the user updates the
        # Programs. The callback will enable the "Save" item so that
        # the user can save the programs to the output file.
        self.model.add_callback('programs-updated', self.enable_save_item_cb)

    def build_gui(self, container):
        super(ProgramsTab, self).build_gui(container)

        self.tableview.doubleClicked.connect(self.doubleClicked)

    def build_table(self):
        super(ProgramsTab, self).build_table('ProgramsTab', 'TableModel')

    def doubleClicked(self, index):
        # When a user double-clicks on a program in the first column,
        # send that information to the QueueModel so the observing
        # blocks from that program can be displayed in the ObsBlock
        # tab.
        row, col = index.row(), index.column()
        if self.columnNames[col].lower() == 'proposal':
            proposal = self.dataForTableModel[row][col]
            if proposal not in self.model.ob_qf_dict:
                # We haven't read in this program file. Get the
                # ControlPanel plugin so that we can call the
                # load_program method to read in the program file.
                control_panel_plugin = self.view.get_plugin('cp')
                control_panel_plugin.load_program(proposal)

            # Set the QueueModel.proposalForPropTab attribute so
            # that the ProposalTab object can get that value and
            # know which proposal it should display.
            self.model.setProposalForPropTab(proposal)
            self.view.gui_do(self.createTab)

    def createTab(self):
        # If we have already created (and possibly closed) this
        # proposal tab before, just reload it. Otherwise, we have to
        # create it from scratch.
        proposal = self.model.proposalForPropTab
        self.logger.info('Creating tab for proposal %s' % proposal)
        if self.view.gpmon.has_plugin(proposal):
            self.view.reload_plugin(proposal)
        else:
            spec = Bunch(module='ProposalTab', klass='ProposalTab',
                         ws='report', tab=proposal, name=proposal,
                         start=False, ptype='global', hidden=True)
            self.view.load_plugin(proposal, spec)

        self.view.start_plugin(proposal)

        # Raise the tab we just created
        self.view.ds.raise_tab(proposal)

class TableModel(QueueFileTab.TableModel):

    def __init__(self, inputData, columns, data, qmodel, logger):
        super(TableModel, self).__init__(inputData, columns, data, qmodel, logger)
        self.parse_flag = True

    def setData(self, index, value, role = QtCore.Qt.EditRole):
        # We implement the setData method so that the Programs table
        # can be editable. If we are called with
        # role=QtCore.Qt.EditRole, that means the user has changed a
        # value in the table. Check to make sure the new value is
        # acceptable. If not, reset the cell to the original value.
        if role == QtCore.Qt.EditRole:
            row, col = index.row(), index.column()
            key = self.model_data[row][0]
            colHeader = self.columns[col]
            value2 = None
            if colHeader in ('rank', 'hours'):
                # Make sure we can parse the supplied Rank or Hours
                # value as a float
                try:
                    value2 = float(value)
                except ValueError:
                    self.logger.error('Error in column %s: cannot convert %s to float' % (colHeader, value))
                    return False
            elif colHeader == 'band':
                # Make sure we can parse the supplied band value as
                # a float
                try:
                    value2 = int(value)
                except ValueError:
                    self.logger.error('Error in column %s: cannot convert %s to int' % (colHeader, value))
                    return False
            else:
                value2 = value

            # Update the value in the table
            self.logger.debug('Setting model_data row %d col %d to %s' % (row,col,value2))
            self.model_data[row][col] = value2

            # Update the programs data structure in the QueueModel.
            self.qmodel.update_programs(row, colHeader, value, self.parse_flag)

            # Emit the dataChanged signal, as required by PyQt4 for
            # implementations of the setData method.
            self.dataChanged.emit(index, index)
            return True
        else:
            return False
