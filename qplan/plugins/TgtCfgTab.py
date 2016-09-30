#
# TgtCfgTab.py -- Plugin to display/edit the target configuration in a table GUI
#

import datetime
from PyQt4 import QtGui, QtCore
import PlBase

import entity
import QueueFileTab

class TgtCfgTab(QueueFileTab.QueueCfgFileTab):

    def build_table(self):
        super(TgtCfgTab, self).build_table('TgtCfgTab', 'TableModel')
        self.table_model.proposal = self.proposal
        self.table_model.tgtCfgTab = self

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
            self.qmodel.update_tgtcfg(self.proposal, row, colHeader, value,
                                      self.parse_flag)
            # tgtcfg data has changed, so enable the File->Save menu
            # item
            self.tgtCfgTab.enable_save_item()

            # Emit the dataChanged signal, as required by PyQt4 for
            # implementations of the setData method.
            self.emit(QtCore.SIGNAL('dataChanged()'))
            return True
        else:
            return False
