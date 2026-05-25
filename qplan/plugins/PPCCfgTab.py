#
# PPCCfgTab.py -- Plugin to display the PPC configuration in a table GUI
#

from qplan.plugins import QueueFileTab


class PPCCfgTab(QueueFileTab.QueueCfgFileTab):

    def validate_cell(self, row, col, col_key, new_value):
        # Update the ppccfg data structure in the QueueModel.
        self.model.update_ppccfg(self.proposal, row, col_key, new_value,
                                 self.parse_flag)
        self.enable_save_item()
        return True
