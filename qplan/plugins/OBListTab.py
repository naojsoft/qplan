#
# OBListTab.py -- Plugin to display/edit the observing blocks in a table GUI
#

from qplan.plugins import QueueFileTab


class OBListTab(QueueFileTab.QueueCfgFileTab):

    def validate_cell(self, row, col, col_key, new_value):
        # Update the OB list data structure in the QueueModel.
        self.model.update_oblist(self.proposal, row, col_key, new_value,
                                 self.parse_flag)
        self.enable_save_item()
        return True
