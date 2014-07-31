#
# Schedule.py -- Schedule plugin
# 
# Eric Jeschke (eric@naoj.org)
#

from PyQt4 import QtGui, QtCore
import PlBase

class Schedule(PlBase.Plugin):

    def __init__(self, model, view, controller, logger):
        super(Schedule, self).__init__(model, view, controller, logger)

        self.schedules = []
        
        model.add_callback('schedule-cleared', self.clear_schedule_cb)
        model.add_callback('schedule-added', self.new_schedule_cb)

    def build_gui(self, container):

        layout = QtGui.QVBoxLayout()
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)
        container.setLayout(layout)

        # create the table
        table = QtGui.QTableView()
        self.table = table
        table.setSelectionBehavior(QtGui.QAbstractItemView.SelectRows)
        table.setSelectionMode(QtGui.QAbstractItemView.SingleSelection)
        table.setShowGrid(False)
        vh = table.verticalHeader()
        # Hack to make the rows in a TableView all have a
        # reasonable height for the data
        ## if QtHelp.have_pyqt5:
        ##     vh.setSectionResizeMode(QtGui.QHeaderView.ResizeToContents)
        ## else:
        vh.setResizeMode(QtGui.QHeaderView.ResizeToContents)
        # Hide vertical header
        vh.setVisible(False)

        layout.addWidget(self.table, stretch=1)

    def build_table(self, schedules):

        columns = ['Schedule']
        
        table = self.table
        model = ScheduleTableModel(columns, schedules)
        table.setModel(model)
        selectionModel = QtGui.QItemSelectionModel(model, table)
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
        #model.clear()
        
    def new_schedule_cb(self, qmodel, schedule):
        if not schedule in self.schedules:
            self.schedules.append(schedule)
        self.view.gui_do(self.build_table, self.schedules)
        return True

    def clear_schedule_cb(self, qmodel):
        self.view.gui_do(self.clear_table)
        return True

    def select_row_cb(self, midx_to, midx_from):
        """This method is called when the user selects a row(s) from the table.
        """
        row = midx_to.row()
        schedule = self.schedules[row]
        self.model.select_schedule(schedule)
        return True
    

class GenericTableModel(QtCore.QAbstractTableModel):

    def __init__(self, columns, data):
        super(GenericTableModel, self).__init__(None)

        self.columns = columns
        self.data = data

    def rowCount(self, parent): 
        return len(self.data) 
 
    def columnCount(self, parent): 
        return len(self.columns) 

    def get_data(self, row, col):
        """Subclass should override this as necessary."""
        return self.data[row][col]
        
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
        schedule = self.get_data(row, col)
        return str(schedule)

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
        #if QtHelp.have_pyqt4:
        self.emit(QtCore.SIGNAL("layoutAboutToBeChanged()"))

        self.data = sorted(self.data, key=self.mksort(Ncol))

        if order == QtCore.Qt.DescendingOrder:
            self.data.reverse()

        #if QtHelp.have_pyqt4:
        self.emit(QtCore.SIGNAL("layoutChanged()"))
        
    
class ScheduleTableModel(GenericTableModel):

    def get_data(self, row, col):
        return self.data[row]
        
    def mksort(self, col):
        """Subclass should override this as necessary."""
        def sortfn(item):
            return str(item)
        return sortfn
        
    

#END
