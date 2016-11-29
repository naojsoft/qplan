#
# InsCfgTab.py -- Plugin to display/edit the instrument configuration in a table GUI
#

import datetime
from qtpy import QtCore
from qtpy import QtWidgets as QtGui
from . import PlBase

import entity
from . import QueueFileTab

class InsCfgTab(QueueFileTab.QueueCfgFileTab):

    def build_table(self):
        super(InsCfgTab, self).build_table('InsCfgTab', 'TableModel')
        self.table_model.proposal = self.proposal
        self.table_model.insCfgTab = self

class TableModel(QueueFileTab.TableModel):

    def __init__(self, inputData, columns, data, qmodel, logger):
        super(TableModel, self).__init__(inputData, columns, data, qmodel,
                                         logger)
        self.parse_flag = True
        self.proposal = None

    def setData(self, index, value, role = QtCore.Qt.EditRole):
        # We implement the setData method so that the ObsList table
        # can be editable. If we are called with
        # role=QtCore.Qt.EditRole, that means the user has changed a
        # value in the table. Check to make sure the new value is
        # acceptable. If not, reset the cell to the original value.
        if role == QtCore.Qt.EditRole:
            row, col = index.row(), index.column()
            colHeader = self.columns[col]

            # Update the value in the table
            self.logger.debug("Setting model_data row %d col %d to %s" % (
                row, col, value))
            self.model_data[row][col] = value

            # Update the programs data structure in the QueueModel.
            self.qmodel.update_inscfg(self.proposal, row, colHeader, value,
                                      self.parse_flag)

            # inscfg data has changed, so enable the File->Save menu
            # item
            self.insCfgTab.enable_save_item()

            # Emit the dataChanged signal, as required by PyQt4 for
            # implementations of the setData method.
            self.emit(QtCore.SIGNAL('dataChanged()'))
            return True
        else:
            return False
