#
# Schedule.py -- Schedule plugin
#
#  E. Jeschke
#

from ginga.gw import Widgets

from qplan.plugins import PlBase


class Schedule(PlBase.Plugin):

    def __init__(self, controller):
        super().__init__(controller)

        self.schedules = []

        sdlr = self.model.get_scheduler()
        sdlr.add_callback('schedule-cleared', self.clear_schedule_cb)
        sdlr.add_callback('schedule-added', self.new_schedule_cb)

    def build_gui(self, container):
        container.set_margins(4, 4, 4, 4)
        container.set_spacing(4)

        self.table = Widgets.TableView(
            columns=[{'label': 'Schedule', 'key': 'Schedule',
                      'type': 'string'}],
            selection_mode='single',
            show_row_numbers=False,
            sortable=False,
        )
        self.table.add_callback('selected', self.select_row_cb)
        container.add_widget(self.table, stretch=1)

    def build_table(self, schedules):
        rows = [{'Schedule': str(sched)} for sched in schedules]
        self.table.set_rows(rows)

    def clear_table(self):
        self.schedules = []
        self.table.clear()

    def new_schedule_cb(self, sdlr, schedule):
        if schedule not in self.schedules:
            self.schedules.append(schedule)
        self.view.gui_do(self.build_table, self.schedules)
        return True

    def clear_schedule_cb(self, sdlr):
        # NOTE: this needs to be a gui_call!
        self.view.gui_call(self.clear_table)
        return True

    def select_row_cb(self, table, sel_rows):
        """Called when the user selects a row from the schedule list.

        ``sel_rows`` is a list of row dicts; for a single-selection
        TableView it is empty or holds one entry.  We map the
        selected row's index back to ``self.schedules`` and notify
        the QueueModel.
        """
        if not sel_rows:
            return True
        paths = table.get_selected_paths()
        if not paths:
            return True
        row = paths[0][0]
        if 0 <= row < len(self.schedules):
            self.model.select_schedule(self.schedules[row])
        return True


#END
