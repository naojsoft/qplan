#
# OBListTab.py -- Plugin to display/edit the observing blocks in a table GUI
#

import datetime
from PyQt4 import QtGui, QtCore
import PlBase

import entity
import QueueFileTab

class OBListTab(QueueFileTab.QueueFileTab):

    def __init__(self, model, view, controller, logger):
        super(OBListTab, self).__init__(model, view, controller, logger)
        # Register a callback function for when the we want to show
        # the ObListTab
        self.model.add_callback('show-oblist', self.populate_cb)
        # Register a callback function for when the user updates the
        # OBList. The callback will enable the "Save" item so that
        # the user can save the OBList to the output file.
        self.model.add_callback('oblist-updated', self.enable_save_item)

    def build_table(self):
        super(OBListTab, self).build_table('OBListTab', 'TableModel')
        self.table_model.proposal = self.proposal

    def setProposal(self, proposal):
        self.proposal = proposal

    def populate_cb(self, qmodel, proposal, inputData):
        self.logger.debug('proposal %s inputData %s self.proposal %s' % (proposal, inputData, self.proposal))
        if proposal == self.proposal:
            super(OBListTab, self).populate_cb(qmodel, inputData)

    def enable_save_item(self, qmodel, proposal):
        # This method will be called when the user changes something
        # in the table. Enable the "Save" item so that the user can
        # save the updated data to the output file.
        if proposal == self.proposal:
            self.file_save_item.setEnabled(True)

class TableModel(QueueFileTab.TableModel):

    def __init__(self, inputData, columns, data, qmodel, logger):
        super(TableModel, self).__init__(inputData, columns, data, qmodel, logger)
        self.parse_flag = True

        # Moon can only be one of bright, grey, or dark
        self.moon_values =  ('bright', 'grey', 'dark')

        # Sky can only be one of clear, cirrus, or any
        self.sky_values =  ('clear', 'cirrus', 'any')

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
            value2 = None
            if colHeader in ('Priority', 'Seeing', 'Airmass'):
                # Make sure we can parse the supplied value as a float
                try:
                    value2 = float(value)
                except ValueError:
                    self.logger.error('Error in column %s: cannot convert %s to float' % (colHeader, value))
                    return False
            elif colHeader == 'Moon':
                # Moon can only be one of bright, grey, or dark
                if value in self.moon_values:
                    value2 = value
                else:
                    self.logger.error('Error in column %s: invalid moon condition %s- allowable: %s' % (colHeader, value, self.moon_values))
                    return False
            elif colHeader == 'Sky':
                # Sky can only be one of clear, cirrus, or any
                if value in self.sky_values:
                    value2 = value
                else:
                    self.logger.error('Error in column %s: invalid sky condition %s- allowable: %s' % (colHeader, value, self.sky_values))
                    return False
            else:
                value2 = value

            # Update the value in the table
            self.logger.debug('Setting model_data row %d col %d to %s' % (row,col,value2))
            self.model_data[row][col] = value2

            # Update the programs data structure in the QueueModel.
            self.qmodel.update_oblist(self.proposal, row, colHeader, value, self.parse_flag)

            # Emit the dataChanged signal, as required by PyQt4 for
            # implementations of the setData method.
            self.emit(QtCore.SIGNAL('dataChanged()'))
            return True
        else:
            return False
