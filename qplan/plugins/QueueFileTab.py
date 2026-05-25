#
# QueueFileTab.py -- Base class for the GUIs that display the Queue
# Schedule, Program, and Observation Block files.
#

from ginga.gw import Widgets

from . import PlBase


class QueueFileTab(PlBase.Plugin):

    def __init__(self, controller):
        super().__init__(controller)

        self.inputData = None
        self.dataForTableModel = None
        self.columnNames = None
        # If False, ``inputData.parse()`` is suppressed during a
        # batch of cell updates (e.g. paste) and re-run once at the
        # end.  Subclasses' ``validate_cell`` consult this when
        # deciding whether to ask the QueueModel to re-parse.
        self.parse_flag = True

    def build_gui(self, container):
        top_layout = container
        top_layout.set_margins(0, 0, 0, 0)

        # Toolbar with File and Edit menus.
        toolbar = Widgets.Toolbar()
        top_layout.add_widget(toolbar)

        filemenu = toolbar.add_menu(text='File')
        self.file_save_item = filemenu.add_name('Save')
        self.file_save_item.set_enabled(False)
        self.file_save_item.add_callback('activated', self.save_item_clicked)
        self.filemenu = filemenu

        editmenu = toolbar.add_menu('Edit')
        # The Edit-menu items just forward to the widget's public
        # copy/cut/paste methods.  Keyboard Ctrl/Cmd+C/X/V wired on
        # the widget itself does the same job — the menu items are
        # there for discoverability.
        editmenu.add_name('Copy').add_callback(
            'activated', lambda w: self.tableview.copy_selection())
        editmenu.add_name('Cut').add_callback(
            'activated', lambda w: self.tableview.cut_selection())
        editmenu.add_name('Paste').add_callback(
            'activated', lambda w: self.tableview.paste_selection())
        editmenu.add_name('Insert Rows').add_callback(
            'activated', lambda w: self.insert_row_clicked())
        editmenu.add_name('Delete Rows').add_callback(
            'activated', lambda w: self.delete_row_clicked())

        # Cross-backend Ginga TableView in cell-selection mode.
        # qtw + pgw get full rectangular-cell + dispersed Ctrl-click
        # selection; gtk degrades to whole-row selection.  Either
        # way the widget owns Ctrl/Cmd + C/X/V and fires per-cell
        # cell_edited callbacks for paste, so the plugin's
        # validate_cell flow drives the QueueModel updates
        # uniformly whether the user typed or pasted.
        self.tableview = Widgets.TableView(
            selection_mode='multiple-cell',
            show_row_numbers=True,
            show_grid=True,
            sortable=False,
            alternate_row_colors=True,
        )
        self.tableview.add_callback('cell_edited', self._on_cell_edited)
        # After a batch paste, fire ``inputData.parse()`` once so
        # validators that need a cross-row pass see the full new
        # state.  ``cut`` doesn't need this — its cell_edited
        # callbacks already invoke validate_cell, which already
        # calls qmodel.update_*.
        self.tableview.add_callback('paste', self._on_paste_finished)
        top_layout.add_widget(self.tableview, stretch=1)

    # ----- Table population --------------------------------------

    def build_table(self, module_name=None, class_name=None):
        """Push the current ``dataForTableModel`` into the TableView.

        ``module_name`` / ``class_name`` are kept as positional
        arguments so the existing per-plugin
        ``super().build_table('EnvCfgTab', 'TableModel')`` calls
        keep working unchanged — they're ignored now that the
        per-plugin ``TableModel`` classes are gone.
        """
        # Bake ``editable: True`` into the column descriptors so
        # the flag ships with set_columns().  Subclasses can flip
        # individual columns read-only in their own ``build_table``
        # via ``self.tableview.set_column_editable(idx, False)``
        # (e.g. ProgramsTab pins the ``proposal`` column read-only
        # so a double-click activates the row instead of opening
        # the editor).
        cols = [{'label': c, 'key': c, 'type': 'string',
                 'editable': True}
                for c in self.columnNames]
        self.tableview.set_columns(cols)
        rows = [dict(zip(self.columnNames, row))
                for row in self.dataForTableModel]
        self.tableview.set_rows(rows)
        self.tableview.set_optimal_column_widths()

    def populate_cb(self, qmodel, inputData):
        # Callback for when the queue file gets loaded.
        self.inputData = inputData
        self.columnNames = inputData.columnNames
        # Snapshot the parsed data into a row-major list-of-lists
        # for fast in-process access (avoids a per-cell dict lookup
        # during paste / validate).  Kept in sync with the TableView.
        self.dataForTableModel = []
        for row in self.inputData.rows:
            self.dataForTableModel.append(
                [row[colName] for colName in self.columnNames])
        self.view.gui_do(self.update_table)
        return True

    def update_table(self):
        self.build_table()


    # ----- Cell-edited validation -------------------------------

    def _on_cell_edited(self, table, path, col_key, old_value, new_value):
        row = path[0]
        if col_key is None or col_key not in self.columnNames:
            return
        col = self.columnNames.index(col_key)
        result = self.validate_cell(row, col, col_key, new_value)
        if result is False:
            # Validation rejected — revert the visible cell so the
            # table stays consistent with our shadow.
            table.set_cell(row, col, old_value)
            return
        # ``True`` means "accept as-is"; any other return value is
        # treated as a transformed value (e.g. a string parsed to
        # a float) and used in place of ``new_value``.
        stored = new_value if result is True else result
        self.dataForTableModel[row][col] = stored
        if stored != new_value:
            table.set_cell(row, col, stored)

    def validate_cell(self, row, col, col_key, new_value):
        """Subclass hook — validate an edit and propagate to the
        ``QueueModel`` as needed.  Return value semantics:

        * ``True``  — accept the new value as-is.
        * ``False`` — reject; the TableView cell is reverted to the
          previous value.
        * anything else — accept, but substitute the returned value
          for ``new_value`` (useful when the string the user typed
          needs to be parsed/normalised, e.g. to a float).
        """
        return True

    # ----- File-menu actions ------------------------------------

    def save_item_clicked(self, w):
        if self.inputData:
            self.inputData.write_output()
            self.file_save_item.set_enabled(False)
        else:
            self.logger.error('Input data file has not been loaded')

    # ----- Edit-menu actions ------------------------------------

    def _on_paste_finished(self, table, text):
        # The widget fires per-cell ``cell_edited`` callbacks during
        # the paste (which route through validate_cell and call
        # qmodel.update_* one cell at a time).  Once the batch is
        # done, give inputData one chance to re-parse the full
        # post-paste state and refresh the Save item.
        if self.inputData is not None:
            try:
                self.inputData.parse()
            except Exception:
                self.logger.error('inputData.parse() failed after paste',
                                  exc_info=True)
        self.enable_save_item()

    def insert_row_clicked(self):
        paths = self.tableview.get_selected_paths()
        if not paths:
            return
        row = sorted(paths)[0][0]
        count = len(paths)
        for _ in range(count):
            blank = {col: ' ' for col in self.columnNames}
            self.tableview.insert_row(row, blank)
            self.inputData.rows.insert(row, dict(blank))
            self.dataForTableModel.insert(row, [' '] * len(self.columnNames))
        self.enable_save_item()

    def delete_row_clicked(self):
        paths = self.tableview.get_selected_paths()
        if not paths:
            return
        # Delete from highest-indexed row downward so earlier row
        # indices remain stable through the loop.
        for path in sorted(paths, key=lambda p: -p[0]):
            row = path[0]
            self.tableview.delete_row(row)
            if 0 <= row < len(self.inputData.rows):
                self.inputData.rows.pop(row)
            if 0 <= row < len(self.dataForTableModel):
                self.dataForTableModel.pop(row)
        self.inputData.parse()
        self.enable_save_item()

    # ----- Save-item enable -------------------------------------

    def enable_save_item_cb(self, qmodel):
        self.enable_save_item()

    def enable_save_item(self):
        # Currently we cannot preserve formulas in an Excel file,
        # so only enable the menu item when the inputData is *not*
        # an Excel file.
        if self.inputData and not self.inputData.is_excel_file():
            self.file_save_item.set_enabled(True)


class QueueCfgFileTab(QueueFileTab):

    def setProposal(self, proposal):
        self.proposal = proposal
