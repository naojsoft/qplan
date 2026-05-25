#
# InsCfgTab.py -- Plugin to display/edit the instrument configuration in a table GUI
#

from qplan.plugins import QueueFileTab


class InsCfgTab(QueueFileTab.QueueCfgFileTab):

    def validate_cell(self, row, col, col_key, new_value):
        # Update the inscfg data structure in the QueueModel.
        self.model.update_inscfg(self.proposal, row, col_key, new_value,
                                 self.parse_flag)
        self.enable_save_item()
        return True
