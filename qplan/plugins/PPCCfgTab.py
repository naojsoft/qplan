#
# PPCCfgTab.py -- Plugin to display the PPC configuration in a table GUI
#

import datetime
from qtpy import QtCore
from qtpy import QtWidgets as QtGui

from qplan import entity
from qplan.plugins import QueueFileTab

class PPCCfgTab(QueueFileTab.QueueCfgFileTab):

    def build_table(self):
        super(PPCCfgTab, self).build_table('PPCCfgTab', 'TableModel')
        self.table_model.proposal = self.proposal
        self.table_model.ppcCfgTab = self

class TableModel(QueueFileTab.TableModel):

    def __init__(self, inputData, columns, data, qmodel, logger):
        super(TableModel, self).__init__(inputData, columns, data, qmodel,
                                         logger)
        self.parse_flag = True
        self.proposal = None

    def setData(self, index, value, role = QtCore.Qt.EditRole):
        # We implement the setData method so that the table can be
        # editable. If we are called with role=QtCore.Qt.EditRole,
        # that means the user has changed a value in the table. Check
        # to make sure the new value is acceptable. If not, reset the
        # cell to the original value.
        if role == QtCore.Qt.EditRole:
            row, col = index.row(), index.column()
            colHeader = self.columns[col]

            # Update the value in the table
            self.logger.debug("Setting model_data row %d col %d to %s" % (
                row, col, value))
            self.model_data[row][col] = value

            # Update the ppccfg data structure in the QueueModel.
            self.qmodel.update_ppccfg(self.proposal, row, colHeader, value,
                                      self.parse_flag)
            # ppccfg data has changed, so enable the File->Save menu
            # item
            self.ppcCfgTab.enable_save_item()

            # Emit the dataChanged signal, as required by PyQt4 for
            # implementations of the setData method.
            self.dataChanged.emit(index, index)
            return True
        else:
            return False
