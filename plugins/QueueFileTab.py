#
# QueueFileTable.py -- Base class for the GUI's that display the Queue
# Schedule, Program, and Observation Block files.
#

from PyQt4 import QtGui, QtCore
from ginga.gw import Widgets
import PlBase

from Schedule import GenericTableModel

class QueueFileTab(PlBase.Plugin):

    def __init__(self, model, view, controller, logger):
        super(QueueFileTab, self).__init__(model, view, controller, logger)
        self.inputData = None
        self.dataForTableModel = None
        self.columnNames = None
        self.copySelectionRange = None

    def build_gui(self, container):
        # Make a top-level layout to which we will add the Toolbar and
        # the TableView.
        top_layout = container
        top_layout.set_margins(0, 0, 0, 0)

        # Create a toolbar and add it to the top_layout
        toolbar = Widgets.Toolbar()
        top_layout.add_widget(toolbar)

        # Create a "File" menu
        filemenu = toolbar.add_menu(text='File')
        self.file_save_item = filemenu.add_name('Save')
        self.file_save_item.set_enabled(False)
        self.file_save_item.add_callback('activated', self.save_item_clicked)

        # Create an "Edit" menu
        editmenu = toolbar.add_menu('Edit')
        copy_item = editmenu.add_name('Copy')
        copy_item.get_widget().setShortcut("Ctrl+C")
        copy_item.add_callback('activated', lambda w: self.copy_clicked())
        paste_item = editmenu.add_name('Paste')
        paste_item.get_widget().setShortcut("Ctrl+V")
        paste_item.add_callback('activated', lambda w: self.paste_clicked())

        insert_row_item = editmenu.add_name('Insert Rows')
        insert_row_item.add_callback('activated',
                                     lambda w: self.insert_row_clicked())
        delete_row_item = editmenu.add_name('Delete Rows')
        delete_row_item.add_callback('activated',
                                     lambda w: self.delete_row_clicked())

        # Create the table view
        tableview = QtGui.QTableView()
        self.tableview = tableview
        # Set the selection behavior
        tableview.setSelectionBehavior(QtGui.QAbstractItemView.SelectItems)
        tableview.setSelectionMode(QtGui.QAbstractItemView.ExtendedSelection)

        # Set up the vertical header
        vh = tableview.verticalHeader()
        vh.setResizeMode(QtGui.QHeaderView.ResizeToContents)

        # Add the table view to the top_layout
        w = Widgets.wrap(tableview)
        top_layout.add_widget(w, stretch=1)

    def build_table(self, module_name, class_name):
        # Set our QTableView widget to point to the supplied table
        # model.
        tableview = self.tableview
        module = __import__(module_name)
        self.table_model = getattr(module, class_name)(self.inputData, self.columnNames, self.dataForTableModel, self.model, self.logger)
        tableview.setModel(self.table_model)

        # set column width to fit contents
        tableview.resizeColumnsToContents()
        tableview.resizeRowsToContents()

    def populate_cb(self, qmodel, inputData):
        # Callback for when the schedule file gets loaded
        self.inputData = inputData
        self.columnNames = inputData.columnNames
        # Copy the data from the supplied input data structure into a
        # row/column form that can be used by QueueFileTabTableModel.
        self.dataForTableModel = [];
        for row in self.inputData.rows:
            tableRow = [row[colName] for colName in self.columnNames]
            self.dataForTableModel.append(tableRow)
        self.view.gui_do(self.update_table)
        return True

    def update_table(self):
        self.build_table()

    def save_item_clicked(self):
        # This method gets called when the "Save" item gets clicked on
        # by the user. Write the data to the output file and disable
        # the save item.
        if self.inputData:
            self.inputData.write_output()
            self.file_save_item.setEnabled(False)
        else:
            self.logger.error('Input data file has not been loaded')

    def copy_clicked_gui_do(self):
        if len(self.tableview.selectedIndexes()) > 0:
            selModel = self.tableview.selectionModel()
            if selModel:
                sel = selModel.selection()
                for index in sel.indexes():
                    row = index.row()
                    col = index.column()
                    self.logger.debug('row %d col %d %s' % (row, col, self.dataForTableModel[row][col]))

                selRangeFirst = sel.first()
                self.logger.debug('after selRangeFirst %s'%selRangeFirst)
                self.logger.debug('after selRangeFirst isEmpty? %s'%selRangeFirst.isEmpty())
                if not selRangeFirst.isEmpty():
                    self.logger.debug('after selRangeFirst isValid? %s'%selRangeFirst.isValid())
                    self.logger.debug('first.height %d' %selRangeFirst.height())
                    self.logger.debug('first.width  %d' %selRangeFirst.width())
                    self.logger.debug('first.top    %d' %selRangeFirst.top())
                    self.logger.debug('first.left   %d' %selRangeFirst.left())
                    self.logger.debug('first.bottom %d' %selRangeFirst.bottom())
                    self.logger.debug('first.right  %d' %selRangeFirst.right())
        self.rows = []
        self.logger.debug('before loop')
        for index in self.tableview.selectedIndexes():
            row = index.row()
            col = index.column()
            self.logger.debug('row %d col %d %s' % (row, col, self.dataForTableModel[row][col]))
        self.logger.debug('after loop')

    def copy_clicked(self):
        self.logger.debug('clipboard %s'%self.view.app.clipboard().text())
        #self.view.app.clipboard().setText('something here')
        self.logger.debug('selectedIndexes %s'%self.tableview.selectedIndexes())
        #self.view.gui_do(self.copy_clicked_gui_do)
        selection = self.tableview.selectionModel().selection()
        if selection.count() > 0:
            selRangeFirst = selection.first()
            self.logger.debug('first.height %d' %selRangeFirst.height())
            self.logger.debug('first.width  %d' %selRangeFirst.width())
            height = selRangeFirst.height()
            width = selRangeFirst.width()
            string = ''
            for i in range(height):
                for j in range(width):
                    k = i + j * height
                    index = selection.indexes()[k]
                    row = index.row()
                    col = index.column()
                    string += ' ' + str(self.dataForTableModel[row][col])
                    self.logger.debug('row %d col %d %s' % (row, col, self.dataForTableModel[row][col]))
                string += '\n'
            self.logger.debug(string)
            self.view.app.clipboard().setText(string)
            self.copySelectionRange = QtGui.QItemSelectionRange(selRangeFirst)

    def paste_clicked_gui_do(self, selRow, selCol):
        startRow = self.copySelectionRange.indexes()[0].row()
        startCol = self.copySelectionRange.indexes()[0].column()
        self.table_model.parse_flag = False
        for index in self.copySelectionRange.indexes():
            row = index.row()
            col = index.column()
            copied_value = self.table_model.data(index, QtCore.Qt.EditRole)
            self.logger.debug('row %d col %d %s' % (row, col, copied_value))
            newIndex = self.table_model.createIndex(selRow + row - startRow, selCol + col - startCol)
            self.table_model.setData(newIndex, copied_value)
            self.table_model.layoutChanged()
        self.table_model.parse_flag = True
        self.inputData.parse()

    def paste_clicked(self):
        selection = self.tableview.selectionModel().selection()
        selRow = selection.indexes()[0].row()
        selCol = selection.indexes()[0].column()
        self.logger.debug('selRow %d selCol %d %s' % (selRow, selCol, self.dataForTableModel[selRow][selCol]))
        if self.copySelectionRange:
            self.view.gui_do(self.paste_clicked_gui_do, selRow, selCol)

    def insert_row_clicked(self):
        selectedRows = self.tableview.selectionModel().selectedRows()
        if selectedRows:
            row = selectedRows[0].row()
            count = len(selectedRows)
            self.table_model.insertRows(row, count)
            for i in range(count):
                newRow = {}
                for colName in self.columnNames:
                    newRow[colName] = ' '
                self.inputData.rows.insert(row, newRow)

    def delete_row_clicked(self):
        selectedRows = self.tableview.selectionModel().selectedRows()
        if selectedRows:
            row = selectedRows[0].row()
            count = len(selectedRows)
            self.table_model.removeRows(row, count)
            for i in range(count):
                self.inputData.rows.pop(row)
            self.inputData.parse()
            self.enable_save_item(self.model)

    def enable_save_item(self, qmodel):
        # This method will be called when the user changes something
        # in the table. Enable the "Save" item so that the user can
        # save the updated data to the output file. Currently, we
        # cannot preserve formulas in an Excel file, so we only enable
        # the menu item if the inputData is *not* an Excel file.
        if not self.inputData.is_excel_file():
            self.file_save_item.setEnabled(True)

class TableModel(GenericTableModel):

    # Subclass GenericTableModel and implement the flags, data, and
    # setData methods so that we can make the columns editable.

    def __init__(self, inputData, columns, data, qmodel, logger):
        super(TableModel, self).__init__(columns, data)
        self.inputData = inputData
        self.qmodel = qmodel
        self.logger = logger

    def flags(self, index):
        # All columns are enabled, selectable, and editable
        return QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEditable

    def data(self, index, role):
        # Returns requested data from table model, depending on which
        # role is requested.
        if not index.isValid():
            return None
        elif role == QtCore.Qt.DisplayRole:
            # Return the stringified value when role is DisplayRole
            row, col = index.row(), index.column()
            value = self.get_data(row, col)
            return str(value)
        elif role == QtCore.Qt.EditRole:
            # Return the value when role is EditRole
            row, col = index.row(), index.column()
            value = self.get_data(row, col)
            return value
        else:
            return None

    def headerData(self, section, orientation, role):
        #print 'headerData called with col', col, 'orientation',orientation,'role',role
        if (orientation == QtCore.Qt.Horizontal) and \
               (role == QtCore.Qt.DisplayRole):
            return self.columns[section]

        elif (orientation == QtCore.Qt.Vertical) and \
               (role == QtCore.Qt.DisplayRole):
            return str(section + 1)

        # Hack to make the rows in a TableView all have a
        # reasonable height for the data
        #elif (role == QtCore.Qt.SizeHintRole) and \
        #         (orientation == QtCore.Qt.Vertical):
        #    return 1
        return None

    def insertRows(self, row, count, index=QtCore.QModelIndex()):
        self.beginInsertRows(index, row, row + count - 1)
        self.logger.debug('QueueFileTabTableModel insertRows called row %d count %d'%(row,count))
        for i in range(count):
            newRow = [' ' for j in range(self.columnCount(QtCore.QModelIndex()))]
            self.model_data.insert(row, newRow)
        self.endInsertRows()

    def removeRows(self, row, count, index=QtCore.QModelIndex()):
        self.beginRemoveRows(index, row, row + count - 1)
        self.logger.debug('QueueFileTabTableModel removeRows called row %d count %d'%(row,count))
        for i in range(count):
            self.model_data.pop(row)
        self.endRemoveRows()

    def layoutChanged(self):
        self.emit(QtCore.SIGNAL("layoutChanged()"))
