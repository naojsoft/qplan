#
# EnvCfgTab.py -- Plugin to display/edit the environment configuration in a table GUI
#

from qplan.plugins import QueueFileTab


class EnvCfgTab(QueueFileTab.QueueCfgFileTab):

    def validate_cell(self, row, col, col_key, new_value):
        # Update the envcfg data structure in the QueueModel.
        self.model.update_envcfg(self.proposal, row, col_key, new_value,
                                 self.parse_flag)
        self.enable_save_item()
        return True
