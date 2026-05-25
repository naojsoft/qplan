#
# TgtCfgTab.py -- Plugin to display/edit the target configuration in a table GUI
#

from qplan.plugins import QueueFileTab


class TgtCfgTab(QueueFileTab.QueueCfgFileTab):

    def validate_cell(self, row, col, col_key, new_value):
        # Update the tgtcfg data structure in the QueueModel.
        self.model.update_tgtcfg(self.proposal, row, col_key, new_value,
                                 self.parse_flag)
        self.enable_save_item()
        return True
