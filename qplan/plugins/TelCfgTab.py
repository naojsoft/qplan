#
# TelCfgTab.py -- Plugin to display/edit the telescope configuration in a table GUI
#

from qplan.plugins import QueueFileTab


class TelCfgTab(QueueFileTab.QueueCfgFileTab):

    def validate_cell(self, row, col, col_key, new_value):
        # Update the telcfg data structure in the QueueModel.
        self.model.update_telcfg(self.proposal, row, col_key, new_value,
                                 self.parse_flag)
        self.enable_save_item()
        return True
