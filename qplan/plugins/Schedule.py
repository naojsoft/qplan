#
# Schedule.py -- Schedule plugin
#
#  E. Jeschke
#

from ginga.gw import Widgets
from qtpy import QtCore
from qtpy import QtWidgets as QtGui

from qplan.plugins import PlBase


class Schedule(PlBase.Plugin):

    def __init__(self, controller):
        super(Schedule, self).__init__(controller)

        self.schedules = []

        sdlr = self.model.get_scheduler()
        sdlr.add_callback('schedule-cleared', self.clear_schedule_cb)
        sdlr.add_callback('schedule-added', self.new_schedule_cb)

    def build_gui(self, container):

        container.set_margins(4, 4, 4, 4)
        container.set_spacing(4)

        # create the table
        # TODO: replace with Widgets.TreeView
        table = QtGui.QTableView()
        self.table = table
        table.setSelectionBehavior(QtGui.QAbstractItemView.SelectRows)
        table.setSelectionMode(QtGui.QAbstractItemView.SingleSelection)
        #table.setShowGrid(False)
        vh = table.verticalHeader()
        # Hack to make the rows in a TableView all have a
        # reasonable height for the data
        ## if QtHelp.have_pyqt5:
        ##     vh.setSectionResizeMode(QtGui.QHeaderView.ResizeToContents)
        ## else:
        #vh.setResizeMode(QtGui.QHeaderView.ResizeToContents)
        # Hide vertical header
        #vh.setVisible(False)
        vh.setVisible(True)

        table.resizeColumnsToContents()

        w = Widgets.wrap(table)
        container.add_widget(w, stretch=1)

    def build_table(self, schedules):

        columns = ['Schedule']

        table = self.table
        model = ScheduleTableModel(columns, schedules)
        table.setModel(model)
        selectionModel = QtCore.QItemSelectionModel(model, table)
        table.setSelectionModel(selectionModel)
        selectionModel.currentRowChanged.connect(self.select_row_cb)
        #model.layoutChanged.connect(self.sort_cb)

        # set column width to fit contents
        table.resizeColumnsToContents()
        table.resizeRowsToContents()

        #table.setSortingEnabled(True)

    def clear_table(self):
        table = self.table
        model = table.model()
        # TODO
        self.schedules = []
        if model is not None:
            model.clear()

    def new_schedule_cb(self, sdlr, schedule):
        if not schedule in self.schedules:
            self.schedules.append(schedule)
        self.view.gui_do(self.build_table, self.schedules)
        return True

    def clear_schedule_cb(self, sdlr):
        # NOTE: this needs to be a gui_call!
        self.view.gui_call(self.clear_table)
        return True

    def select_row_cb(self, midx_to, midx_from):
        """This method is called when the user selects a row(s) from the table.
        """
        # First make sure that the supplied index is valid. This
        # callback gets called when a user clicks on a row. However,
        # it also gets called when the user clicks on "Build Schedule"
        # and the self.schedules data structure gets set to an empty
        # list and the TableModel gets cleared out (see the
        # clear_table method above and the GenericTableModel.clear
        # method below). In that case, the index will be invalid, and
        # trying to select the supplied row from self.schedules will
        # result in an error.
        if midx_to.isValid():
            row = midx_to.row()
            schedule = self.schedules[row]
            self.model.select_schedule(schedule)
        return True


class GenericTableModel(QtCore.QAbstractTableModel):

    def __init__(self, columns, data):
        super(GenericTableModel, self).__init__(None)

        self.columns = columns
        self.model_data = data

    def rowCount(self, parent):
        return len(self.model_data)

    def columnCount(self, parent):
        return len(self.columns)

    def get_data(self, row, col):
        """Subclass should override this as necessary."""
        return self.model_data[row][col]

    def mksort(self, col):
        """Subclass should override this as necessary."""
        def sortfn(item):
            return item[col]
        return sortfn

    def data(self, index, role):
        if not index.isValid():
            return None
        elif role != QtCore.Qt.DisplayRole:
            return None

        row, col = index.row(), index.column()
        value = self.get_data(row, col)
        return str(value)

    def headerData(self, col, orientation, role):
        if (orientation == QtCore.Qt.Horizontal) and \
               (role == QtCore.Qt.DisplayRole):
            #return self.columns[col][0]
            return self.columns[col]

        # Hack to make the rows in a TableView all have a
        # reasonable height for the data
        elif (role == QtCore.Qt.SizeHintRole) and \
                 (orientation == QtCore.Qt.Vertical):
            return 1
        return None

    def sort(self, Ncol, order):
        """Sort table by given column number.
        """
        self.layoutAboutToBeChanged.emit()

        self.model_data = sorted(self.model_data, key=self.mksort(Ncol))

        if order == QtCore.Qt.DescendingOrder:
            self.model_data.reverse()

        self.layoutChanged.emit()

    def clear(self, index=QtCore.QModelIndex()):
        n_rows = len(self.model_data)
        if n_rows > 0:
            self.beginRemoveRows(index, 0, n_rows-1)

            self.model_data = []

            self.endRemoveRows()

class ScheduleTableModel(GenericTableModel):

    def get_data(self, row, col):
        return self.model_data[row]

    def mksort(self, col):
        """Subclass should override this as necessary."""
        def sortfn(item):
            return str(item)
        return sortfn



#END
