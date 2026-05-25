#
# ProgramsTab.py -- Plugin to display/edit the programs in a table GUI
#
import yaml

from ginga.misc.Bunch import Bunch
from ginga.gw import Widgets

from qplan.plugins import QueueFileTab


class ProgramsTab(QueueFileTab.QueueFileTab):

    def __init__(self, controller):
        super().__init__(controller)

        # Register a callback function for when the QueueModel loads
        # the programs file.
        self.model.add_callback('programs-file-loaded', self.populate_cb)
        # Register a callback function for when the user updates the
        # Programs, so the "Save" item gets enabled.
        self.model.add_callback('programs-updated', self.enable_save_item_cb)

    def build_gui(self, container):
        super().build_gui(container)

        # Open the proposal detail tab on double-click of a row.
        # qtw/gtk pass the clicked col_key as a 4th arg; pgw passes
        # None (pgwidgets-js doesn't yet carry the column through),
        # so treat None as "any column" — clicks on editable cells
        # under pgw open the editor instead of firing 'activated'.
        self.tableview.add_callback('activated', self._on_activated)

        load_plan = self.filemenu.add_name('Load Plan')
        load_plan.set_enabled(True)
        load_plan.add_callback('activated', self.load_plan_cb)

        save_plan = self.filemenu.add_name('Save As Plan')
        save_plan.set_enabled(True)
        save_plan.add_callback('activated', self.save_plan_cb)

        # Built lazily on first invocation.  Both are non-modal —
        # the chosen path comes back through their 'activated'
        # callback.
        self._container = container
        self._save_dlg = None
        self._load_dlg = None

    def build_table(self, module_name=None, class_name=None):
        super().build_table()
        # Pin the proposal column read-only — double-clicking it
        # then triggers 'activated' rather than opening an editor,
        # which is how we drill into the per-program detail tab.
        if self.columnNames and 'proposal' in self.columnNames:
            self.tableview.set_column_editable(
                self.columnNames.index('proposal'), False)

    def _on_activated(self, table, row_dict, path, col_key):
        # Only act when the click landed on the proposal column
        # (or when the backend can't report a column — pgw).
        if col_key is not None and col_key.lower() != 'proposal':
            return
        proposal = row_dict.get('proposal')
        if not proposal:
            return
        if proposal not in self.model.ob_qf_dict:
            # We haven't read in this program file.  Get the
            # ControlPanel plugin so it can load the program file.
            control_panel_plugin = self.view.get_plugin('cp')
            instruments = (self.model.programs_qf
                           .programs_info[proposal].instruments)
            if 'PFS' in instruments:
                control_panel_plugin.load_ppcfile(proposal)
            else:
                control_panel_plugin.load_program(proposal)

        # Set the QueueModel.proposalForPropTab attribute so the
        # ProposalTab object knows which proposal to display.
        self.model.setProposalForPropTab(proposal)
        self.view.gui_do(self.createTab)

    def createTab(self):
        # If we have already created (and possibly closed) this
        # proposal tab before, just reload it.  Otherwise create
        # it from scratch.
        proposal = self.model.proposalForPropTab
        self.logger.info('Creating tab for proposal %s' % proposal)
        if self.view.gpmon.has_plugin(proposal):
            self.view.reload_plugin(proposal)
        else:
            spec = Bunch(module='ProposalTab', klass='ProposalTab',
                         workspace='report', tab=proposal, name=proposal,
                         start=False, ptype='global', hidden=True,
                         enabled=True)
            self.view.load_plugin(proposal, spec)

        self.view.start_plugin(proposal)

        # Raise the tab we just created.
        self.view.ds.raise_tab(proposal)

    def save_plan_cb(self, w):
        if self.inputData is None:
            self.logger.error("No table data defined yet")
            return
        if self._save_dlg is None:
            self._save_dlg = Widgets.FileDialog(title='Save Plan As',
                                                parent=self._container)
            self._save_dlg.set_mode('save')
            self._save_dlg.add_ext_filter('YAML files', '.yml')
            self._save_dlg.add_callback('activated', self._save_plan_chosen)
        self._save_dlg.popup()

    def _save_plan_chosen(self, dlg, paths):
        if not paths:
            return
        plan_file = paths[0]
        try:
            plan_dct = {d['proposal']: dict(qc_priority=d['qcp'],
                                            skip=d['skip'])
                        for d in self.inputData.rows}
            plan_dct = dict(programs=plan_dct)

            with open(plan_file, 'w') as out_f:
                out_f.write(yaml.dump(plan_dct))

            self.logger.info(f"wrote plan {plan_file}")

        except Exception as e:
            errmsg = f"error writing plan file: {e}"
            self.logger.error(errmsg, exc_info=True)
            self.view.gui_do(self.view.show_error, errmsg, raisetab=True)

    def load_plan_cb(self, w):
        if self.inputData is None:
            self.logger.error("No table data defined yet")
            return
        if self._load_dlg is None:
            self._load_dlg = Widgets.FileDialog(title='Load Plan',
                                                parent=self._container)
            self._load_dlg.set_mode('file')
            self._load_dlg.add_ext_filter('YAML files', '.yml')
            self._load_dlg.add_callback('activated', self._load_plan_chosen)
        self._load_dlg.popup()

    def _load_plan_chosen(self, dlg, paths):
        if not paths:
            return
        try:
            self.model.load_qc_plan(paths[0])
        except Exception as e:
            errmsg = f"error reading QC plan file: {e}"
            self.logger.error(errmsg, exc_info=True)
            self.view.gui_do(self.view.show_error, errmsg, raisetab=True)

    def validate_cell(self, row, col, col_key, new_value):
        value2 = new_value

        if col_key in ('rank', 'hours'):
            try:
                value2 = float(new_value)
            except ValueError:
                self.logger.error(
                    'Error in column %s: cannot convert %s to float'
                    % (col_key, new_value))
                return False
        elif col_key == 'band':
            try:
                value2 = int(new_value)
            except ValueError:
                self.logger.error(
                    'Error in column %s: cannot convert %s to int'
                    % (col_key, new_value))
                return False

        self.model.update_programs(row, col_key, new_value, self.parse_flag)
        return value2 if value2 != new_value else True
