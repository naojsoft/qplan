#
# WeightsTab.py -- Plugin to display/edit the schedule in a table GUI
#

import datetime
from PyQt4 import QtGui, QtCore

import PlBase

import QueueFileTab

class WeightsTab(QueueFileTab.QueueFileTab):

    def __init__(self, model, view, controller, logger):
        super(WeightsTab, self).__init__(model, view, controller, logger)

        # Register a callback function for when the QueueModel loads
        # the weights file
        self.model.add_callback('weights-file-loaded', self.populate_cb)
        # Register a callback function for when the user updates the
        # weights. The callback will enable the "Save" item so that
        # the user can save the weights to the output file.
        self.model.add_callback('weights-updated', self.enable_save_item_cb)

    def build_table(self):
        super(WeightsTab, self).build_table('WeightsTab', 'TableModel')

class TableModel(QueueFileTab.TableModel):

    def __init__(self, inputData, columns, data, qmodel, logger):
        super(TableModel, self).__init__(inputData, columns, data, qmodel, logger)
        self.parse_flag = True

    def setData(self, index, value, role = QtCore.Qt.EditRole):
        # We implement the setData method so that the weights table
        # can be editable. If we are called with
        # role=QtCore.Qt.EditRole, that means the user has changed a
        # value in the table. Check to make sure the new value is
        # acceptable. If not, reset the cell to the original value.
        if role == QtCore.Qt.EditRole:
            row, col = index.row(), index.column()
            colHeader = self.columns[col]
            # Make sure we can parse the supplied value as a float
            try:
                value2 = float(value)
            except ValueError:
                self.logger.error('Error in column %s: cannot convert %s to float' % (colHeader, value))
                return False

            # Update the value in the table
            self.logger.debug('Setting model_data row %d col %d to %s' % (row, col, value2))
            self.model_data[row][col] = value2

            # Update the weights data structure in the QueueModel.
            self.qmodel.update_weights(row, colHeader, value, self.parse_flag)

            # Emit the dataChanged signal, as required by PyQt4 for
            # implementations of the setData method.
            self.emit(QtCore.SIGNAL('dataChanged()'))
            return True
        else:
            return False
