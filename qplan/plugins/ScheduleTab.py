#
# ScheduleTab.py -- Plugin to display/edit the schedule in a table GUI
#

import datetime
import dateutil.parser

from qtpy import QtCore

from qplan.plugins import QueueFileTab

class ScheduleTab(QueueFileTab.QueueFileTab):

    def __init__(self, controller):
        super(ScheduleTab, self).__init__(controller)

        # Register a callback function for when the QueueModel loads
        # the schedule file
        self.model.add_callback('schedule-file-loaded', self.populate_cb)
        # Register a callback function for when the user updates the
        # Schedule. The callback will enable the "Save" item so that
        # the user can save the schedule to the output file.
        self.model.add_callback('schedule-updated', self.enable_save_item_cb)

    def build_table(self):
        super(ScheduleTab, self).build_table('ScheduleTab', 'TableModel')

class TableModel(QueueFileTab.TableModel):

    def __init__(self, inputData, columns, data, qmodel, logger):
        super(TableModel, self).__init__(inputData, columns, data, qmodel, logger)
        self.parse_flag = True
        # Sky can only be one of clear, cirrus, or any
        self.sky_values =  ('clear', 'cirrus', 'any')

    def setData(self, index, value, role = QtCore.Qt.EditRole):
        # We implement the setData method so that the schedule table
        # can be editable. If we are called with
        # role=QtCore.Qt.EditRole, that means the user has changed a
        # value in the table. Check to make sure the new value is
        # acceptable. If not, reset the cell to the original value.
        if role == QtCore.Qt.EditRole:
            row, col = index.row(), index.column()
            colHeader = self.columns[col]
            value2 = None
            if colHeader == 'date':
                # Date has to be in a form acceptable to Python's
                # datetime module.
                try:
                    value2 = dateutil.parser.parse(value).strftime('%Y-%m-%d')
                except ValueError:
                    self.logger.error('Error in column %s: invalid date format for %s - allowable YY-MM-DD' % (colHeader, value))
                    return False

            elif colHeader in ('start time', 'end time'):
                # Start Time and End Time have to be in a form
                # acceptable to Python's datetime module.
                try:
                    datetime.datetime.strptime(value, '%H:%M:%S')
                    value2 = value
                except ValueError:
                    self.logger.error('Error in column %s: invalid time format for %s - allowable HH:MM:SS' % (colHeader, value))
                    return False
            elif colHeader == 'sky':
                # Sky can only be one of clear, cirrus, or any
                if value in self.sky_values:
                    value2 = value
                else:
                    self.logger.error('Error in column %s: invalid sky condition %s - allowable: %s' % (colHeader, value, self.sky_values))
                    return False
            elif colHeader == 'avg seeing':
                # Make sure we can parse the supplied seeing value as
                # a float
                try:
                    value2 = float(value)
                except ValueError:
                    self.logger.error('Error in column %s: cannot convert %s to float' % (colHeader, value))
                    return False

            else:
                value2 = value

            # Update the value in the table
            self.logger.debug('Setting model_data row %d col %d to %s' % (row, col, value2))
            self.model_data[row][col] = value2

            # Update the schedule data structure in the QueueModel.
            self.qmodel.update_schedule(row, colHeader, value, self.parse_flag)

            # Emit the dataChanged signal, as required by PyQt4 for
            # implementations of the setData method.
            self.dataChanged.emit(index, index)
            return True
        else:
            return False
