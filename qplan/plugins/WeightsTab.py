#
# WeightsTab.py -- Plugin to display/edit the weights in a table GUI
#

from qplan.plugins import QueueFileTab


class WeightsTab(QueueFileTab.QueueFileTab):

    def __init__(self, controller):
        super().__init__(controller)

        # Register a callback function for when the QueueModel loads
        # the weights file.
        self.model.add_callback('weights-file-loaded', self.populate_cb)
        # Register a callback function for when the user updates the
        # weights, so the "Save" item gets enabled.
        self.model.add_callback('weights-updated', self.enable_save_item_cb)

    def validate_cell(self, row, col, col_key, new_value):
        # Weights are always floats.  Reject the edit if the typed
        # value won't parse.
        try:
            value2 = float(new_value)
        except ValueError:
            self.logger.error(
                'Error in column %s: cannot convert %s to float'
                % (col_key, new_value))
            return False
        self.model.update_weights(row, col_key, new_value, self.parse_flag)
        # Substitute the parsed float for the typed string so the
        # shadow + visible cell carry the canonical type.
        return value2
