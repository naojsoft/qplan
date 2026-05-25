#
# ScheduleTab.py -- Plugin to display/edit the schedule in a table GUI
#

import datetime
import dateutil.parser

from qplan.plugins import QueueFileTab


# Sky can only be one of these values.
SKY_VALUES = ('clear', 'cirrus', 'any')


class ScheduleTab(QueueFileTab.QueueFileTab):

    def __init__(self, controller):
        super().__init__(controller)

        # Register a callback function for when the QueueModel loads
        # the schedule file.
        self.model.add_callback('schedule-file-loaded', self.populate_cb)
        # Register a callback function for when the user updates the
        # Schedule, so the "Save" item gets enabled.
        self.model.add_callback('schedule-updated', self.enable_save_item_cb)

    def validate_cell(self, row, col, col_key, new_value):
        value2 = new_value

        if col_key == 'date':
            try:
                value2 = dateutil.parser.parse(new_value).strftime('%Y-%m-%d')
            except ValueError:
                self.logger.error(
                    'Error in column %s: invalid date format for %s — '
                    'allowable YY-MM-DD' % (col_key, new_value))
                return False

        elif col_key in ('start time', 'end time'):
            try:
                datetime.datetime.strptime(new_value, '%H:%M:%S')
            except ValueError:
                self.logger.error(
                    'Error in column %s: invalid time format for %s — '
                    'allowable HH:MM:SS' % (col_key, new_value))
                return False

        elif col_key == 'sky':
            if new_value not in SKY_VALUES:
                self.logger.error(
                    'Error in column %s: invalid sky condition %s — '
                    'allowable: %s' % (col_key, new_value, SKY_VALUES))
                return False

        elif col_key == 'avg seeing':
            try:
                value2 = float(new_value)
            except ValueError:
                self.logger.error(
                    'Error in column %s: cannot convert %s to float'
                    % (col_key, new_value))
                return False

        self.model.update_schedule(row, col_key, new_value, self.parse_flag)
        return value2 if value2 != new_value else True
